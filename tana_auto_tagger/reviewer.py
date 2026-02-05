"""Interactive review interface for tag suggestions."""

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text

from .models import Note, Tag, TagSuggestion


console = Console()


class ReviewSession:
    """
    Interactive session for reviewing and approving tag suggestions.
    
    Presents notes one by one with their suggested tags and allows
    the user to accept, reject, or choose different tags.
    """
    
    def __init__(self, all_tags: list[Tag]):
        """
        Initialize review session.
        
        Args:
            all_tags: Complete list of available tags for manual selection
        """
        self.all_tags = sorted(all_tags, key=lambda t: t.name.lower())
        self.decisions: list[tuple[Note, Tag | None]] = []
    
    def review_note(
        self,
        note: Note,
        suggestions: list[TagSuggestion]
    ) -> Tag | None:
        """
        Present a note for review and get user decision.
        
        Args:
            note: The note to review
            suggestions: AI-suggested tags
            
        Returns:
            Selected tag or None if skipped
        """
        console.clear()
        
        # Display note info
        console.print(Panel(
            f"[bold]{note.name or '(Sin nombre)'}[/bold]\n\n"
            f"[dim]{note.full_path}[/dim]\n\n"
            f"{note.content[:500] + '...' if len(note.content) > 500 else note.content}",
            title="📝 Nota",
            border_style="blue"
        ))
        
        # Display suggestions
        if suggestions:
            table = Table(title="🏷️ Tags Sugeridos", show_header=True)
            table.add_column("#", style="cyan", width=3)
            table.add_column("Tag", style="green")
            table.add_column("Confianza", justify="center")
            table.add_column("Score", justify="right")
            
            for i, suggestion in enumerate(suggestions, 1):
                confidence_color = {
                    "High": "green",
                    "Medium": "yellow",
                    "Low": "red"
                }.get(suggestion.confidence_label, "white")
                
                table.add_row(
                    str(i),
                    suggestion.tag.name,
                    f"[{confidence_color}]{suggestion.confidence_label}[/]",
                    f"{suggestion.score:.1%}"
                )
            
            console.print(table)
        else:
            console.print("[yellow]No hay sugerencias para esta nota.[/yellow]")
        
        # Get user input
        console.print("\n[bold]Opciones:[/bold]")
        console.print("  [cyan]1-N[/cyan] = Seleccionar tag sugerido")
        console.print("  [cyan]m[/cyan]   = Elegir manualmente de la lista")
        console.print("  [cyan]s[/cyan]   = Saltar esta nota")
        console.print("  [cyan]q[/cyan]   = Salir de la revisión")
        
        choice = Prompt.ask("\nTu elección", default="s")
        
        if choice.lower() == "q":
            raise KeyboardInterrupt("Usuario canceló la revisión")
        
        if choice.lower() == "s":
            return None
        
        if choice.lower() == "m":
            return self._manual_tag_selection()
        
        # Try to parse as number
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(suggestions):
                selected = suggestions[idx].tag
                self.decisions.append((note, selected))
                return selected
        except ValueError:
            pass
        
        console.print("[red]Opción inválida. Saltando nota.[/red]")
        return None
    
    def _manual_tag_selection(self) -> Tag | None:
        """Show full tag list for manual selection."""
        console.print("\n[bold]Tags disponibles:[/bold]")
        
        # Display in columns
        cols = 3
        for i in range(0, len(self.all_tags), cols):
            row_tags = self.all_tags[i:i+cols]
            row_str = "  ".join(
                f"[cyan]{i+j+1:3}[/cyan] {t.name[:20]:<20}"
                for j, t in enumerate(row_tags)
            )
            console.print(row_str)
        
        choice = Prompt.ask("\nNúmero del tag (o Enter para cancelar)")
        
        if not choice:
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(self.all_tags):
                return self.all_tags[idx]
        except ValueError:
            pass
        
        console.print("[red]Selección inválida.[/red]")
        return None
    
    def show_summary(self) -> None:
        """Display summary of all decisions made in this session."""
        if not self.decisions:
            console.print("[dim]No se realizaron asignaciones.[/dim]")
            return
        
        table = Table(title="📊 Resumen de Asignaciones", show_header=True)
        table.add_column("Nota", style="white", max_width=40)
        table.add_column("Tag Asignado", style="green")
        
        for note, tag in self.decisions:
            if tag:
                table.add_row(
                    note.name[:40] or "(Sin nombre)",
                    tag.name
                )
        
        console.print(table)


def review_single_note(
    note: Note,
    suggestions: list[TagSuggestion],
    all_tags: list[Tag]
) -> Tag | None:
    """
    Quick single-note review without session tracking.
    
    Returns selected tag or None.
    """
    session = ReviewSession(all_tags)
    return session.review_note(note, suggestions)
