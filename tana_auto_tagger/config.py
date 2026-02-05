"""Configuration management for Tana Auto-Tagger."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


@dataclass
class Config:
    """Application configuration."""
    
    # Tana configuration
    workspace_id: str
    mcp_server_url: str
    tana_local_url: str
    embedding_model: str
    excluded_tag_ids: set[str]
    
    # Telegram Bot configuration
    telegram_bot_token: str
    telegram_allowed_username: str
    
    # Optional settings with defaults
    request_timeout: float = 30.0
    telegram_webhook_url: Optional[str] = None
    telegram_use_webhook: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        excluded_ids = os.getenv("EXCLUDED_TAG_IDS", "")
        
        # Parse excluded tag IDs
        excluded_tag_ids = set(id.strip() for id in excluded_ids.split(",") if id.strip())
        
        # Parse webhook setting
        use_webhook = os.getenv("TELEGRAM_USE_WEBHOOK", "true").lower() == "true"
        
        return cls(
            workspace_id=os.getenv("TANA_WORKSPACE_ID", "8YR1337hvC"),
            mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:3000"),
            tana_local_url=os.getenv("TANA_LOCAL_URL", "http://localhost:1111"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            excluded_tag_ids=excluded_tag_ids,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_allowed_username=os.getenv("TELEGRAM_ALLOWED_USERNAME", ""),
            telegram_webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
            telegram_use_webhook=use_webhook,
        )
    
    @property
    def telegram_enabled(self) -> bool:
        """Check if Telegram bot is properly configured."""
        return bool(self.telegram_bot_token and self.telegram_allowed_username)


# Global config instance
config = Config.from_env()
