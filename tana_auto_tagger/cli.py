"""Command-line interface for Tana Auto-Tagger."""

import json
from pathlib import Path
from datetime import datetime

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel

from .config import config
from .models import Note, Tag, TagSuggestion
from .classifier import get_classifier, LocalClassifier
from .tana_client import TanaDataProvider
from .reviewer import ReviewSession
from .sync import run_sync

app = typer.Typer(
    name="tana-tagger",
    help="Auto-tag untagged Tana notes using local AI classification."
)
console = Console()


import asyncio

def _run_async(func, *args, **kwargs):
    """Helper to run async functions from synchronous Typer commands."""
    return asyncio.run(func(*args, **kwargs))


@app.command()
def sync(
    days: int = typer.Option(7, "--days", "-d", help="Días hacia atrás para buscar notas"),
):
    """
    Sincronizar automáticamente tags y notas desde Tana.
    Requiere que Tana (Emphasis) esté abierto y el Input API activo.
    """
    success = _run_async(run_sync, days_back=days)
    if not success:
        raise typer.Exit(1)


# Cache file paths
CACHE_DIR = Path(__file__).parent.parent / ".cache"
TAGS_CACHE = CACHE_DIR / "tags.json"
NOTES_CACHE = CACHE_DIR / "notes.json"


def load_cached_tags() -> list[Tag]:
    """Load tags from cache file."""
    if not TAGS_CACHE.exists():
        console.print("[red]No hay tags en caché. Usa --refresh-tags primero.[/red]")
        raise typer.Exit(1)
    
    with open(TAGS_CACHE, "r", encoding="utf-8") as f:
        raw_tags = json.load(f)
    
    provider = TanaDataProvider()
    tags = provider.parse_tags_response(raw_tags)
    return provider.filter_excluded_tags(tags)


def load_cached_notes() -> list[Note]:
    """Load notes from cache file."""
    if not NOTES_CACHE.exists():
        console.print("[red]No hay notas en caché. Usa --refresh-notes primero.[/red]")
        raise typer.Exit(1)
    
    with open(NOTES_CACHE, "r", encoding="utf-8") as f:
        raw_notes = json.load(f)
    
    return TanaDataProvider.parse_notes_response(raw_notes)


def save_tags_cache(tags: list[dict]) -> None:
    """Save raw tags to cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(TAGS_CACHE, "w", encoding="utf-8") as f:
        json.dump(tags, f, indent=2, ensure_ascii=False)


def save_notes_cache(notes: list[dict]) -> None:
    """Save raw notes to cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(NOTES_CACHE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)


@app.command()
def process(
    days: int = typer.Option(7, "--days", "-d", help="Días hacia atrás para buscar notas"),
    interactive: bool = typer.Option(True, "--interactive/--auto", "-i/-a", help="Modo interactivo vs automático"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo mostrar sugerencias sin asignar"),
    top_k: int = typer.Option(3, "--top", "-k", help="Número de sugerencias por nota"),
    min_score: float = typer.Option(0.25, "--min-score", help="Score mínimo para sugerir"),
):
    """
    Procesar notas sin tags y sugerir/asignar tags.
    
    Requiere que los datos estén en caché. Usa 'refresh' primero.
    """
    console.print(Panel(
        f"[bold]Tana Auto-Tagger[/bold]\n\n"
        f"Modo: {'Interactivo' if interactive else 'Automático'}\n"
        f"Días: {days} | Top-K: {top_k} | Min Score: {min_score:.0%}",
        border_style="green"
    ))
    
    # Load cached data
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Cargando tags...", total=None)
        tags = load_cached_tags()
        
        progress.add_task("Cargando notas...", total=None)
        all_notes = load_cached_notes()
        
        # Filter to parent notes only
        provider = TanaDataProvider()
        notes = provider.filter_parent_notes_only(all_notes)
        
        progress.add_task("Inicializando clasificador AI...", total=None)
        classifier = get_classifier()
        classifier.load_tags(tags)
    
    console.print(f"\n[green]✓[/green] {len(tags)} tags cargados")
    console.print(f"[green]✓[/green] {len(notes)} notas padre sin tags (de {len(all_notes)} total)")

    
    if not notes:
        console.print("[yellow]No hay notas para procesar.[/yellow]")
        raise typer.Exit(0)
    
    # Process notes
    results: list[tuple[Note, list[TagSuggestion]]] = []
    
    with Progress(console=console) as progress:
        task = progress.add_task("Clasificando notas...", total=len(notes))
        
        for note in notes:
            suggestions = classifier.classify(note, top_k=top_k, min_score=min_score)
            results.append((note, suggestions))
            progress.advance(task)
    
    # Show results or start review
    if dry_run:
        _show_dry_run_report(results)
    elif interactive:
        _interactive_review(results, tags)
    else:
        console.print("[yellow]Modo automático no implementado aún.[/yellow]")


def _show_dry_run_report(results: list[tuple[Note, list[TagSuggestion]]]) -> None:
    """Display suggestions report without making changes."""
    console.print("\n[bold]📋 Reporte de Sugerencias (Dry Run)[/bold]\n")
    
    for note, suggestions in results:
        console.print(f"[blue]•[/blue] [bold]{note.name or '(Sin nombre)'}[/bold]")
        console.print(f"  [dim]{note.full_path}[/dim]")
        
        if suggestions:
            for s in suggestions:
                color = "green" if s.score >= 0.5 else "yellow" if s.score >= 0.3 else "red"
                console.print(f"    [{color}]→ {s.tag.name}[/] ({s.score:.1%})")
        else:
            console.print("    [dim]Sin sugerencias[/dim]")
        console.print()


def _interactive_review(
    results: list[tuple[Note, list[TagSuggestion]]],
    all_tags: list[Tag]
) -> None:
    """Run interactive review session."""
    session = ReviewSession(all_tags)
    assignments: list[tuple[Note, Tag]] = []
    
    try:
        for i, (note, suggestions) in enumerate(results):
            console.print(f"\n[dim]Nota {i+1} de {len(results)}[/dim]")
            
            selected = session.review_note(note, suggestions)
            if selected:
                assignments.append((note, selected))
                console.print(f"[green]✓ Seleccionado: {selected.name}[/green]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Revisión cancelada.[/yellow]")
    
    # Summary
    console.print("\n")
    session.show_summary()
    
    # Export assignments for later use
    if assignments:
        CACHE_DIR.mkdir(exist_ok=True)
        assignments_file = CACHE_DIR / "pending_assignments.json"
        
        data = [
            {"note_id": n.id, "note_name": n.name, "tag_id": t.id, "tag_name": t.name}
            for n, t in assignments
        ]
        
        with open(assignments_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        console.print(f"\n[green]Asignaciones guardadas en:[/green] {assignments_file}")
        console.print("[dim]Usa 'apply' para aplicar las asignaciones a Tana.[/dim]")


@app.command()
def refresh_tags():
    """
    Mostrar instrucciones para actualizar el caché de tags.
    
    Los tags deben obtenerse via Antigravity MCP.
    """
    console.print(Panel(
        "[bold]Actualizar Caché de Tags[/bold]\n\n"
        "Ejecuta este comando en Antigravity:\n\n"
        f"[cyan]mcp_tana-local_list_tags[/cyan]\n"
        f"  workspaceId: {config.workspace_id}\n"
        f"  limit: 200\n\n"
        "Luego guarda el resultado JSON en:\n"
        f"[green]{TAGS_CACHE}[/green]",
        border_style="blue"
    ))


@app.command()
def refresh_notes(
    days: int = typer.Option(7, "--days", "-d", help="Días hacia atrás")
):
    """
    Mostrar instrucciones para actualizar el caché de notas.
    
    Las notas deben obtenerse via Antigravity MCP.
    """
    provider = TanaDataProvider()
    query = provider.get_search_query(days)
    
    console.print(Panel(
        "[bold]Actualizar Caché de Notas[/bold]\n\n"
        "Ejecuta este comando en Antigravity:\n\n"
        "[cyan]mcp_tana-local_search_nodes[/cyan]\n"
        f"  workspaceIds: [\"{config.workspace_id}\"]\n"
        f"  limit: 100\n"
        f"  query: {json.dumps(query)}\n\n"
        "Luego guarda el resultado JSON en:\n"
        f"[green]{NOTES_CACHE}[/green]",
        border_style="blue"
    ))


@app.command()
def apply():
    """
    Aplicar asignaciones pendientes a Tana.
    
    Lee pending_assignments.json y muestra instrucciones para aplicar.
    """
    assignments_file = CACHE_DIR / "pending_assignments.json"
    
    if not assignments_file.exists():
        console.print("[red]No hay asignaciones pendientes.[/red]")
        raise typer.Exit(1)
    
    with open(assignments_file, "r", encoding="utf-8") as f:
        assignments = json.load(f)
    
    console.print(Panel(
        "[bold]Aplicar Asignaciones[/bold]\n\n"
        f"Hay {len(assignments)} asignaciones pendientes.\n\n"
        "Para cada una, ejecuta en Antigravity:\n\n"
        "[cyan]mcp_tana-local_tag[/cyan]\n"
        "  nodeId: <note_id>\n"
        "  action: add\n"
        "  tagIds: [<tag_id>]",
        border_style="green"
    ))
    
    table = Table(title="Asignaciones Pendientes")
    table.add_column("Nota", max_width=40)
    table.add_column("Tag")
    table.add_column("IDs", style="dim")
    
    for a in assignments:
        table.add_row(
            a["note_name"][:40],
            a["tag_name"],
            f"{a['note_id']} → {a['tag_id']}"
        )
    
    console.print(table)


@app.command()
def status():
    """Mostrar estado actual del caché y configuración."""
    console.print(Panel("[bold]Tana Auto-Tagger - Estado[/bold]", border_style="blue"))
    
    console.print(f"\n[bold]Configuración:[/bold]")
    console.print(f"  Workspace: {config.workspace_id}")
    console.print(f"  Modelo: {config.embedding_model}")
    console.print(f"  Tags excluidos: {len(config.excluded_tag_ids)}")
    
    console.print(f"\n[bold]Caché:[/bold]")
    console.print(f"  Directorio: {CACHE_DIR}")
    
    if TAGS_CACHE.exists():
        with open(TAGS_CACHE) as f:
            tag_count = len(json.load(f))
        console.print(f"  [green]✓[/green] Tags: {tag_count}")
    else:
        console.print(f"  [red]✗[/red] Tags: No existe")
    
    if NOTES_CACHE.exists():
        with open(NOTES_CACHE) as f:
            note_count = len(json.load(f))
        console.print(f"  [green]✓[/green] Notas: {note_count}")
    else:
        console.print(f"  [red]✗[/red] Notas: No existe")
    
    pending = CACHE_DIR / "pending_assignments.json"
    if pending.exists():
        with open(pending) as f:
            pending_count = len(json.load(f))
        console.print(f"  [yellow]![/yellow] Pendientes: {pending_count}")


if __name__ == "__main__":
    app()
