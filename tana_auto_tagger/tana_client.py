"""HTTP client for Tana MCP Server communication."""

import json
import subprocess
from datetime import datetime
from typing import Any

from .config import config
from .models import Note, Tag


class TanaClient:
    """Client to interact with Tana via MCP server tools."""
    
    def __init__(self):
        self.workspace_id = config.workspace_id
        self.excluded_tag_ids = config.excluded_tag_ids
    
    def _call_mcp_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        """
        Call a Tana MCP tool.
        
        Note: This assumes the MCP server is running and accessible.
        In a real implementation, this would use the MCP protocol.
        For now, we'll use a subprocess approach or direct HTTP.
        """
        # This is a placeholder - the actual implementation depends on
        # how the MCP server exposes its tools (HTTP, stdio, etc.)
        raise NotImplementedError(
            "Direct MCP tool calls require the MCP server integration. "
            "Use the standalone functions that work with cached data instead."
        )
    
    def list_tags(self) -> list[Tag]:
        """
        Fetch all tags from Tana, excluding system tags.
        
        Returns filtered list of Tag objects.
        """
        # For now, this returns a placeholder
        # In practice, this would call mcp_tana-local_list_tags
        raise NotImplementedError("Use TanaDataProvider instead")
    
    def search_untagged_notes(self, days_back: int = 7) -> list[Note]:
        """
        Search for notes without tags created in the last N days.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of Note objects without tags
        """
        raise NotImplementedError("Use TanaDataProvider instead")
    
    def read_note(self, node_id: str, max_depth: int = 2) -> str:
        """
        Read the full content of a note.
        
        Args:
            node_id: The node ID to read
            max_depth: How deep to traverse children
            
        Returns:
            Markdown-formatted content
        """
        raise NotImplementedError("Use TanaDataProvider instead")
    
    def assign_tag(self, node_id: str, tag_id: str) -> bool:
        """
        Assign a tag to a node.
        
        Args:
            node_id: The node to tag
            tag_id: The tag to apply
            
        Returns:
            True if successful
        """
        raise NotImplementedError("Use TanaDataProvider instead")


class TanaDataProvider:
    """
    Data provider that works with Tana MCP via Antigravity.
    
    This class provides methods to prepare queries that can be executed
    via the Antigravity MCP tools.
    """
    
    def __init__(self):
        self.workspace_id = config.workspace_id
        self.excluded_tag_ids = config.excluded_tag_ids
    
    @staticmethod
    def parse_tags_response(raw_tags: list[dict]) -> list[Tag]:
        """Parse raw tag data from MCP response."""
        return [
            Tag(
                id=t.get("id", ""),
                name=t.get("name", "").replace("&amp;", "&"),
            )
            for t in raw_tags
        ]
    
    @staticmethod
    def parse_notes_response(raw_notes: list[dict]) -> list[Note]:
        """Parse raw note data from MCP search response."""
        notes = []
        for n in raw_notes:
            created = None
            if n.get("created"):
                try:
                    created = datetime.fromisoformat(n["created"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            
            notes.append(Note(
                id=n.get("id", ""),
                name=n.get("name", "").replace("&amp;", "&"),
                breadcrumb=n.get("breadcrumb", []),
                created=created,
            ))
        return notes
    
    def filter_excluded_tags(self, tags: list[Tag]) -> list[Tag]:
        """Remove system/excluded tags from the list."""
        return [t for t in tags if t.id not in self.excluded_tag_ids]
    
    @staticmethod
    def is_parent_note(note: Note) -> bool:
        """
        Check if a note is a parent note (not a child of another user-created note).
        
        A note is considered a parent if its breadcrumb ends at a calendar day node,
        meaning the last element matches the pattern "YYYY-MM-DD - Weekday".
        
        Child notes have longer breadcrumbs that include the parent note title.
        """
        if not note.breadcrumb:
            return False
        
        # Structural headers to ignore (treat notes inside these as parents)
        IGNORED_HEADERS = {
            "Daily Preparation",
            "Action: Plan for Today",
            "Inbox",
            "Agenda",
            "Tasks",
            "Notes"
        }
        
        import re
        day_pattern = r'^\d{4}-\d{2}-\d{2} - \w+$'
        
        # Check if any of the recent parents is a day node, skipping structural headers
        # We look from the bottom up (end of breadcrumb)
        for parent in reversed(note.breadcrumb):
            # If we hit a day node, this is a valid parent note
            if re.match(day_pattern, parent):
                return True
                
            # If we hit a normal parent note (not in our ignore list), 
            # then our note is a child of that note -> return False
            # Clean parent name of HTML/formatting if needed (basic check)
            clean_parent = parent.replace("<u>", "").replace("</u>", "").strip()
            if clean_parent not in IGNORED_HEADERS:
                return False
                
        return False
    
    def filter_parent_notes_only(self, notes: list[Note]) -> list[Note]:
        """Filter to keep only parent notes (exclude children)."""
        return [n for n in notes if self.is_parent_note(n)]

    
    def get_search_query(self, days_back: int = 7) -> dict:
        """
        Generate the search query for untagged notes.
        
        Returns a query dict compatible with mcp_tana-local_search_nodes.
        """
        return {
            "and": [
                {"created": {"last": days_back}},
                {"not": {"has": "tag"}}
            ]
        }
