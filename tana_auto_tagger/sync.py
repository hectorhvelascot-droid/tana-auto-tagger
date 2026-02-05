"""Automated synchronization for Tana cache."""

import json
from pathlib import Path
import httpx
from rich.console import Console

from .config import config
from .tana_client import TanaDataProvider
from .models import Tag, Note

console = Console()

class TanaSyncer:
    """
    Handles automated synchronization between Tana and local cache.
    Uses the Tana Input API (local server) directly.
    """
    
    def __init__(self):
        self.base_url = config.tana_local_url
        self.workspace_id = config.workspace_id
        self.cache_dir = Path(__file__).parent.parent / ".cache"
    
    async def sync_all(self, days_back: int = 7):
        """Sync both tags and untagged notes."""
        self.cache_dir.mkdir(exist_ok=True)
        
        console.print(f"[bold blue]Sincronizando con Tana ({self.base_url})...[/bold blue]")
        
        try:
            # 1. Sync Tags
            tags_data = await self.fetch_tags()
            tags_file = self.cache_dir / "tags.json"
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(tags_data, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓[/green] Tags sincronizados: {len(tags_data)}")
            
            # 2. Sync Untagged Notes
            notes_data = await self.fetch_untagged_notes(days_back)
            notes_file = self.cache_dir / "notes.json"
            with open(notes_file, "w", encoding="utf-8") as f:
                json.dump(notes_data, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓[/green] Notas sin tags sincronizadas: {len(notes_data)}")
            
            return True
        except Exception as e:
            console.print(f"[red]Error durante la sincronización: {str(e)}[/red]")
            console.print("[yellow]Asegúrate de que Tana (Emphasis) esté abierto y el Input API activo.[/yellow]")
            return False

    async def fetch_tags(self) -> list[dict]:
        """Fetch all supertags from Tana."""
        async with httpx.AsyncClient(timeout=config.request_timeout) as client:
            # The Tana Input API often exposes tags via a specific endpoint
            # or we might need to use a general search/list command.
            # Assuming the local server follows common patterns:
            response = await client.post(
                f"{self.base_url}/listTags",
                json={"workspaceId": self.workspace_id}
            )
            response.raise_for_status()
            return response.json()

    async def fetch_untagged_notes(self, days_back: int) -> list[dict]:
        """Search for untagged notes in Tana."""
        provider = TanaDataProvider()
        query = provider.get_search_query(days_back)
        
        async with httpx.AsyncClient(timeout=config.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/search",
                json={
                    "workspaceIds": [self.workspace_id],
                    "query": query,
                    "limit": 100
                }
            )
            response.raise_for_status()
            return response.json()

async def run_sync(days_back: int = 7):
    """Entry point for sync operation."""
    syncer = TanaSyncer()
    return await syncer.sync_all(days_back)
