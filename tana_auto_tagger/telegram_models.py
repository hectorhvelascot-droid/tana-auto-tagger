"""Models for Telegram Bot integration."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from .models import Note, TagSuggestion


class SessionState(Enum):
    """Finite state machine states for user sessions."""
    IDLE = "idle"
    SYNCING = "syncing"
    CLASSIFYING = "classifying"
    REVIEWING = "reviewing"
    APPLYING = "applying"


@dataclass
class TelegramSession:
    """User session data for Telegram bot workflow."""
    
    user_id: int
    username: str
    state: SessionState = SessionState.IDLE
    date_range: Optional[tuple[Optional[date], Optional[date]]] = None
    notes: List[Note] = field(default_factory=list)
    suggestions: Dict[str, List[TagSuggestion]] = field(default_factory=dict)
    approved: Dict[str, str] = field(default_factory=dict)  # note_id -> tag_id
    message_id: Optional[int] = None
    
    # Identifiers
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Set expiration time (30 minutes from creation)."""
        if self.expires_at is None:
            from datetime import timedelta
            self.expires_at = self.created_at + timedelta(minutes=30)
    
    def touch(self):
        """Update last activity timestamp and extend expiration."""
        self.updated_at = datetime.now()
        from datetime import timedelta
        self.expires_at = self.updated_at + timedelta(minutes=30)
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def set_state(self, state: SessionState):
        """Update session state and touch timestamp."""
        self.state = state
        self.touch()
    
    def approve_suggestion(self, note_id: str, tag_id: str):
        """Mark a suggestion as approved."""
        self.approved[note_id] = tag_id
        self.touch()
    
    def unapprove_note(self, note_id: str):
        """Remove approval for a note."""
        if note_id in self.approved:
            del self.approved[note_id]
        self.touch()
    
    def is_approved(self, note_id: str) -> bool:
        """Check if a note has an approved tag."""
        return note_id in self.approved
    
    def get_approved_count(self) -> int:
        """Get number of approved suggestions."""
        return len(self.approved)
    
    def to_dict(self) -> dict:
        """Convert session to dictionary (for serialization)."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "state": self.state.value,
            "date_range": (
                (self.date_range[0].isoformat(), self.date_range[1].isoformat())
                if self.date_range else None
            ),
            "notes_count": len(self.notes),
            "approved_count": len(self.approved),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class DateParseResult:
    """Result of parsing a natural language date expression."""
    
    success: bool
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    error_message: Optional[str] = None
    
    @property
    def days_back(self) -> int:
        """Calculate days back from end_date to start_date."""
        if not self.start_date or not self.end_date:
            return 7  # Default
        delta = self.end_date - self.start_date
        return delta.days + 1
