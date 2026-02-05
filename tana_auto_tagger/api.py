"""FastAPI webhook endpoint for Tana Auto-Tagger."""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from .config import config
from .models import Note, Tag, TagSuggestion
from .classifier import get_classifier
from .tana_client import TanaDataProvider
from .session_manager import session_manager
from .telegram_models import SessionState, TelegramSession
from .sync import TanaSyncer
from .date_parser import parse_date_range

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Tana Auto-Tagger API",
    description="Webhook endpoint for automated tag classification",
    version="0.1.0"
)

# Cache paths
CACHE_DIR = Path(__file__).parent.parent / ".cache"
TAGS_CACHE = CACHE_DIR / "tags.json"
NOTES_CACHE = CACHE_DIR / "notes.json"


class ProcessRequest(BaseModel):
    """Request body for process endpoint."""
    days_back: int = 7
    top_k: int = 3
    min_score: float = 0.25


class TagSuggestionResponse(BaseModel):
    """Single tag suggestion."""
    tag_id: str
    tag_name: str
    score: float
    confidence: str


class NoteWithSuggestions(BaseModel):
    """Note with its tag suggestions."""
    note_id: str
    note_name: str
    breadcrumb: str
    suggestions: list[TagSuggestionResponse]


class ProcessResponse(BaseModel):
    """Response from process endpoint."""
    status: str
    notes_processed: int
    results: list[NoteWithSuggestions]


class ApplyRequest(BaseModel):
    """Request to apply a tag to a note."""
    note_id: str
    tag_id: str


class ApplyResponse(BaseModel):
    """Response from apply endpoint."""
    status: str
    message: str
    mcp_command: dict


def load_tags() -> list[Tag]:
    """Load tags from cache."""
    if not TAGS_CACHE.exists():
        raise HTTPException(status_code=404, detail="Tags cache not found. Refresh cache first.")
    
    with open(TAGS_CACHE, "r", encoding="utf-8") as f:
        raw_tags = json.load(f)
    
    provider = TanaDataProvider()
    tags = provider.parse_tags_response(raw_tags)
    return provider.filter_excluded_tags(tags)


def load_notes() -> list[Note]:
    """Load notes from cache."""
    if not NOTES_CACHE.exists():
        raise HTTPException(status_code=404, detail="Notes cache not found. Refresh cache first.")
    
    with open(NOTES_CACHE, "r", encoding="utf-8") as f:
        raw_notes = json.load(f)
    
    return TanaDataProvider.parse_notes_response(raw_notes)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Tana Auto-Tagger",
        "status": "running",
        "workspace_id": config.workspace_id
    }


@app.get("/status")
async def status():
    """Get current cache status."""
    result = {
        "workspace_id": config.workspace_id,
        "embedding_model": config.embedding_model,
        "excluded_tags": len(config.excluded_tag_ids),
        "cache": {
            "tags": None,
            "notes": None,
            "pending": None
        }
    }
    
    if TAGS_CACHE.exists():
        with open(TAGS_CACHE) as f:
            result["cache"]["tags"] = len(json.load(f))
    
    if NOTES_CACHE.exists():
        with open(NOTES_CACHE) as f:
            result["cache"]["notes"] = len(json.load(f))
    
    pending = CACHE_DIR / "pending_assignments.json"
    if pending.exists():
        with open(pending) as f:
            result["cache"]["pending"] = len(json.load(f))
    
    return result


@app.post("/process", response_model=ProcessResponse)
async def process_notes(request: ProcessRequest):
    """
    Process all cached untagged notes and return suggestions.
    
    This does NOT apply tags automatically - it returns suggestions
    that can be reviewed and applied later via /apply.
    """
    # Load data
    tags = load_tags()
    notes = load_notes()
    
    if not notes:
        return ProcessResponse(
            status="no_notes",
            notes_processed=0,
            results=[]
        )
    
    # Initialize classifier
    classifier = get_classifier()
    classifier.load_tags(tags)
    
    # Process each note
    results: list[NoteWithSuggestions] = []
    
    for note in notes:
        suggestions = classifier.classify(
            note,
            top_k=request.top_k,
            min_score=request.min_score
        )
        
        results.append(NoteWithSuggestions(
            note_id=note.id,
            note_name=note.name or "(Sin nombre)",
            breadcrumb=note.full_path,
            suggestions=[
                TagSuggestionResponse(
                    tag_id=s.tag.id,
                    tag_name=s.tag.name,
                    score=s.score,
                    confidence=s.confidence_label
                )
                for s in suggestions
            ]
        ))
    
    return ProcessResponse(
        status="success",
        notes_processed=len(notes),
        results=results
    )


@app.post("/apply", response_model=ApplyResponse)
async def apply_tag(request: ApplyRequest):
    """
    Return the MCP command to apply a tag to a note.
    
    Since we can't directly call MCP from here, this returns
    the command that should be executed via Antigravity.
    """
    mcp_command = {
        "tool": "mcp_tana-local_tag",
        "params": {
            "nodeId": request.note_id,
            "action": "add",
            "tagIds": [request.tag_id]
        }
    }
    
    return ApplyResponse(
        status="pending",
        message=f"Execute this MCP command to apply the tag",
        mcp_command=mcp_command
    )


@app.post("/cache/tags")
async def update_tags_cache(tags: list[dict]):
    """
    Update the tags cache with new data.
    
    Call this endpoint with the output from mcp_tana-local_list_tags.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    with open(TAGS_CACHE, "w", encoding="utf-8") as f:
        json.dump(tags, f, indent=2, ensure_ascii=False)
    
    return {"status": "success", "tags_cached": len(tags)}


@app.post("/cache/notes")
async def update_notes_cache(notes: list[dict]):
    """
    Update the notes cache with new data.
    
    Call this endpoint with the output from mcp_tana-local_search_nodes.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    with open(NOTES_CACHE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)
    
    return {"status": "success", "notes_cached": len(notes)}


# ==================== TELEGRAM BOT ENDPOINTS ====================

class TelegramSyncRequest(BaseModel):
    """Request to start sync from Telegram."""
    user_id: int
    username: str
    date_text: str
    chat_id: int


class TelegramSyncResponse(BaseModel):
    """Response from sync request."""
    success: bool
    session_id: str
    message: str
    notes_found: int = 0


class TelegramSuggestionsResponse(BaseModel):
    """Suggestions for a session."""
    session_id: str
    notes_count: int
    suggestions: list[dict]


class TelegramApplyRequest(BaseModel):
    """Request to apply tags."""
    approved: dict[str, str]  # note_id -> tag_id


class TelegramApplyResponse(BaseModel):
    """Response from apply request."""
    success: bool
    applied_count: int
    errors: list[str]


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive updates from Telegram webhook."""
    from telegram import Update
    
    if not config.telegram_enabled:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")
    
    try:
        data = await request.json()
        update = Update.de_json(data, None)
        
        # Process update through bot application
        # This would be handled by the bot application in a real scenario
        # For now, we just acknowledge receipt
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/telegram/sync", response_model=TelegramSyncResponse)
async def telegram_sync(
    request: TelegramSyncRequest,
    background_tasks: BackgroundTasks
):
    """
    Start sync process for Telegram user.
    
    This runs sync and classification in the background.
    """
    # Parse date range
    date_result = parse_date_range(request.date_text)
    if not date_result.success:
        return TelegramSyncResponse(
            success=False,
            session_id="",
            message=f"❌ Error: {date_result.error_message}",
            notes_found=0
        )
    
    # Create session
    session = session_manager.create_session(request.user_id, request.username)
    session.date_range = (date_result.start_date, date_result.end_date)
    session.set_state(SessionState.SYNCING)
    
    # Start background processing
    background_tasks.add_task(
        _process_telegram_sync,
        session.session_id,
        date_result.days_back
    )
    
    return TelegramSyncResponse(
        success=True,
        session_id=session.session_id,
        message=f"⏳ Procesando {date_result.start_date} → {date_result.end_date}...",
        notes_found=0
    )


async def _process_telegram_sync(session_id: str, days_back: int):
    """Background task to sync and classify notes."""
    session = session_manager.get_session(session_id)
    if not session:
        logger.error(f"Session {session_id} not found")
        return
    
    try:
        # Step 1: Sync with Tana
        syncer = TanaSyncer()
        await syncer.sync_all(days_back=days_back)
        
        # Step 2: Load data
        tags = load_tags()
        notes = load_notes()
        
        if not notes:
            session.set_state(SessionState.IDLE)
            await _notify_user(session, "📭 No se encontraron notas sin etiquetar.")
            return
        
        session.notes = notes
        session.set_state(SessionState.CLASSIFYING)
        
        # Step 3: Classify
        classifier = get_classifier()
        classifier.load_tags(tags)
        
        for note in notes:
            suggestions = classifier.classify(note, top_k=3, min_score=0.25)
            session.suggestions[note.id] = suggestions
        
        session.set_state(SessionState.REVIEWING)
        
        # Step 4: Notify user
        suggestions_count = sum(1 for s in session.suggestions.values() if s)
        message = (
            f"✅ *Listo!*\n\n"
            f"📋 {len(notes)} notas encontradas\n"
            f"🏷️ {suggestions_count} con sugerencias\n\n"
            f"Usa /status para ver el progreso."
        )
        await _notify_user(session, message)
        
    except Exception as e:
        logger.error(f"Error in background sync: {e}")
        session.set_state(SessionState.IDLE)
        await _notify_user(session, f"❌ Error: {str(e)}")


async def _notify_user(session: TelegramSession, message: str):
    """Send notification to user via Telegram."""
    # This would integrate with the actual bot
    # For now, we just log it
    logger.info(f"Notify user {session.username}: {message}")


@app.get("/telegram/suggestions/{session_id}")
async def get_telegram_suggestions(session_id: str):
    """Get suggestions for a session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    suggestions_list = []
    for note in session.notes:
        note_suggestions = session.suggestions.get(note.id, [])
        top = note_suggestions[0] if note_suggestions else None
        
        suggestions_list.append({
            "note_id": note.id,
            "note_name": note.name,
            "breadcrumb": note.full_path,
            "top_tag": {
                "id": top.tag.id,
                "name": top.tag.name,
                "score": top.score,
                "confidence": top.confidence_label
            } if top else None,
            "is_approved": session.is_approved(note.id)
        })
    
    return TelegramSuggestionsResponse(
        session_id=session_id,
        notes_count=len(session.notes),
        suggestions=suggestions_list
    )


@app.post("/telegram/apply/{session_id}", response_model=TelegramApplyResponse)
async def apply_telegram_suggestions(
    session_id: str,
    request: TelegramApplyRequest
):
    """Apply approved tags to notes."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    session.set_state(SessionState.APPLYING)
    
    errors = []
    applied = 0
    
    try:
        # Here you would integrate with Tana API to actually apply tags
        # For now, we just track what would be applied
        for note_id, tag_id in request.approved.items():
            # Apply tag logic would go here
            applied += 1
        
        # Clear session after successful apply
        session_manager.delete_session(session_id)
        
        return TelegramApplyResponse(
            success=True,
            applied_count=applied,
            errors=errors
        )
        
    except Exception as e:
        session.set_state(SessionState.REVIEWING)
        return TelegramApplyResponse(
            success=False,
            applied_count=applied,
            errors=[str(e)]
        )


@app.post("/telegram/cleanup")
async def cleanup_telegram_sessions():
    """Clean up expired sessions. Called by cron job."""
    removed = session_manager.cleanup_expired()
    stats = session_manager.get_stats()
    
    return {
        "removed": removed,
        "stats": stats
    }


@app.get("/telegram/stats")
async def get_telegram_stats():
    """Get Telegram bot statistics."""
    if not config.telegram_enabled:
        return {"enabled": False}
    
    return {
        "enabled": True,
        "allowed_username": config.telegram_allowed_username,
        "sessions": session_manager.get_stats()
    }
