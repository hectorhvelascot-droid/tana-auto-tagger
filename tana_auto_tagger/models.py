"""Data models for Tana entities."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Tag:
    """Represents a Tana super tag."""
    
    id: str
    name: str
    description: str = ""
    embedding: list[float] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class Note:
    """Represents a Tana note/node."""
    
    id: str
    name: str
    content: str = ""
    breadcrumb: list[str] = field(default_factory=list)
    created: datetime | None = None
    tags: list[Tag] = field(default_factory=list)
    
    @property
    def full_path(self) -> str:
        """Return breadcrumb as path string."""
        return " > ".join(self.breadcrumb) if self.breadcrumb else ""


@dataclass
class TagSuggestion:
    """A suggested tag with confidence score."""
    
    tag: Tag
    score: float  # 0.0 to 1.0
    
    @property
    def confidence_label(self) -> str:
        """Human-readable confidence level."""
        if self.score >= 0.7:
            return "High"
        elif self.score >= 0.4:
            return "Medium"
        return "Low"
