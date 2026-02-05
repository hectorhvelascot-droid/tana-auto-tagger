"""Natural language date parsing for Spanish."""

import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import dateparser

from .telegram_models import DateParseResult

logger = logging.getLogger(__name__)


class DateParser:
    """Parse natural language date expressions in Spanish."""
    
    def __init__(self):
        """Initialize date parser with Spanish settings."""
        self.today = date.today()
    
    def parse(self, text: str) -> DateParseResult:
        """
        Parse a natural language date expression.
        
        Supports:
        - "hoy" → today
        - "ayer" → yesterday  
        - "últimos 3 días" → last 3 days
        - "esta semana" → from Monday to today
        - Fechas ISO: "2024-02-01 2024-02-05"
        - Naturales: "desde el 1 de febrero hasta el 5"
        """
        text_lower = text.lower().strip()
        
        # Handle special cases first
        result = self._parse_special_cases(text_lower)
        if result:
            return result
        
        # Try regex patterns for ranges
        result = self._parse_patterns(text_lower)
        if result:
            return result
        
        # Try dateparser for natural language
        result = self._parse_with_dateparser(text_lower)
        if result:
            return result
        
        return DateParseResult(
            success=False,
            error_message=f"No pude entender '{text}'. Prueba con: hoy, ayer, últimos 3 días, 2024-02-01 2024-02-05"
        )
    
    def _parse_special_cases(self, text: str) -> Optional[DateParseResult]:
        """Parse special keywords like 'hoy', 'ayer'."""
        
        if text in ["hoy", "today"]:
            return DateParseResult(
                success=True,
                start_date=self.today,
                end_date=self.today
            )
        
        if text in ["ayer", "yesterday"]:
            yesterday = self.today - timedelta(days=1)
            return DateParseResult(
                success=True,
                start_date=yesterday,
                end_date=yesterday
            )
        
        if text in ["esta semana", "this week"]:
            # From Monday to today
            monday = self.today - timedelta(days=self.today.weekday())
            return DateParseResult(
                success=True,
                start_date=monday,
                end_date=self.today
            )
        
        if text in ["semana pasada", "last week"]:
            # Previous week (Monday to Sunday)
            last_monday = self.today - timedelta(days=self.today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)
            return DateParseResult(
                success=True,
                start_date=last_monday,
                end_date=last_sunday
            )
        
        return None
    
    def _parse_patterns(self, text: str) -> Optional[DateParseResult]:
        """Parse regex patterns for common expressions."""
        
        # "últimos X días" / "last X days"
        pattern = r"(?:últimos?|last)\s+(\d+)\s+(?:días?|days?)"
        match = re.search(pattern, text)
        if match:
            days = int(match.group(1))
            start_date = self.today - timedelta(days=days-1)
            return DateParseResult(
                success=True,
                start_date=start_date,
                end_date=self.today
            )
        
        # "desde X hasta Y"
        pattern = r"desde\s+(.+?)\s+hasta\s+(.+)"
        match = re.search(pattern, text)
        if match:
            start_text = match.group(1)
            end_text = match.group(2)
            
            start_date = self._parse_single_date(start_text)
            end_date = self._parse_single_date(end_text)
            
            if start_date and end_date:
                return DateParseResult(
                    success=True,
                    start_date=start_date,
                    end_date=end_date
                )
        
        # ISO format: "2024-02-01 2024-02-05"
        pattern = r"(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})"
        match = re.search(pattern, text)
        if match:
            try:
                start_date = date.fromisoformat(match.group(1))
                end_date = date.fromisoformat(match.group(2))
                return DateParseResult(
                    success=True,
                    start_date=start_date,
                    end_date=end_date
                )
            except ValueError:
                pass
        
        return None
    
    def _parse_with_dateparser(self, text: str) -> Optional[DateParseResult]:
        """Use dateparser library for complex natural language."""
        
        # Try to parse as a single date
        parsed = dateparser.parse(
            text,
            languages=['es', 'en'],
            settings={
                'PREFER_DATES_FROM': 'past',
                'RETURN_AS_TIMEZONE_AWARE': False,
            }
        )
        
        if parsed:
            parsed_date = parsed.date()
            return DateParseResult(
                success=True,
                start_date=parsed_date,
                end_date=parsed_date
            )
        
        return None
    
    def _parse_single_date(self, text: str) -> Optional[date]:
        """Parse a single date string."""
        text = text.strip()
        
        # Try ISO format
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
        
        # Try dateparser
        parsed = dateparser.parse(
            text,
            languages=['es', 'en'],
            settings={'RETURN_AS_TIMEZONE_AWARE': False}
        )
        
        if parsed:
            return parsed.date()
        
        return None


# Global parser instance
date_parser = DateParser()


def parse_date_range(text: str) -> DateParseResult:
    """Convenience function to parse a date range."""
    return date_parser.parse(text)
