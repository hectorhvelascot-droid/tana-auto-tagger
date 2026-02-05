"""In-memory session manager for Telegram bot."""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .telegram_models import TelegramSession, SessionState

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions in memory."""
    
    def __init__(self):
        """Initialize empty session store."""
        self._sessions: Dict[str, TelegramSession] = {}
        self._user_sessions: Dict[int, str] = {}  # user_id -> session_id
        logger.info("SessionManager initialized")
    
    def create_session(self, user_id: int, username: str) -> TelegramSession:
        """Create a new session for a user."""
        # Clean up any existing session for this user
        self.cleanup_user_sessions(user_id)
        
        session = TelegramSession(
            user_id=user_id,
            username=username
        )
        
        self._sessions[session.session_id] = session
        self._user_sessions[user_id] = session.session_id
        
        logger.info(f"Created session {session.session_id} for user {username} ({user_id})")
        return session
    
    def get_session(self, session_id: str) -> Optional[TelegramSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            logger.info(f"Session {session_id} expired, removing")
            self.delete_session(session_id)
            return None
        return session
    
    def get_user_session(self, user_id: int) -> Optional[TelegramSession]:
        """Get the current active session for a user."""
        session_id = self._user_sessions.get(user_id)
        if not session_id:
            return None
        return self.get_session(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session = self._sessions.get(session_id)
        if session:
            del self._sessions[session_id]
            # Remove from user index
            if self._user_sessions.get(session.user_id) == session_id:
                del self._user_sessions[session.user_id]
            logger.info(f"Deleted session {session_id}")
            return True
        return False
    
    def cleanup_user_sessions(self, user_id: int):
        """Remove all sessions for a user."""
        # Find all sessions for this user
        to_delete = [
            sid for sid, session in self._sessions.items()
            if session.user_id == user_id
        ]
        for sid in to_delete:
            self.delete_session(sid)
        
        if user_id in self._user_sessions:
            del self._user_sessions[user_id]
    
    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            self.delete_session(sid)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)
    
    def get_all_sessions(self) -> List[TelegramSession]:
        """Get all active sessions."""
        # Clean expired first
        self.cleanup_expired()
        return list(self._sessions.values())
    
    def get_stats(self) -> dict:
        """Get session statistics."""
        self.cleanup_expired()
        
        state_counts = {}
        for session in self._sessions.values():
            state = session.state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return {
            "total_sessions": len(self._sessions),
            "unique_users": len(self._user_sessions),
            "by_state": state_counts,
        }


# Global session manager instance
session_manager = SessionManager()
