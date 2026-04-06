"""Keyboard shortcuts help screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


SHORTCUTS = """
[bold cyan]== General ==[/]
[yellow]Ctrl+P[/]      Command Palette
[yellow]Ctrl+S[/]      Save File
[yellow]Ctrl+Q[/]      Quit
[yellow]Ctrl+,[/]      Settings
[yellow]F1[/]          Show Shortcuts (this screen)

[bold cyan]== Panels ==[/]
[yellow]Ctrl+K[/]      Toggle Chat Panel
[yellow]Ctrl+`[/]      Toggle Terminal
[yellow]Ctrl+B[/]      Toggle File Tree
[yellow]Ctrl+J[/]      Toggle Agent Panel
[yellow]Ctrl+Shift+M[/] Toggle Problems Panel

[bold cyan]== AI Features ==[/]
[yellow]F9[/]          Toggle Plan/Act Mode
[yellow]Ctrl+E[/]      Explain Selected Code
[yellow]Ctrl+Shift+G[/] AI Git Commit
[yellow]Ctrl+Shift+R[/] AI Code Review
[yellow]Ctrl+.[/]      Quick Fix (AI suggestions)
[yellow]Ctrl+Shift+I[/] Toggle Inline Suggestions

[bold cyan]== Navigation ==[/]
[yellow]Ctrl+O[/]      Switch Project
[yellow]F12[/]         Go to Definition
[yellow]Shift+F12[/]   Find References
[yellow]Ctrl+Shift+O[/] Go to Symbol
[yellow]Ctrl+I[/]      Info at Cursor

[bold cyan]== Editing ==[/]
[yellow]F2[/]          Rename Symbol
[yellow]Ctrl+F[/]      Find & Replace
[yellow]Ctrl+Shift+F[/] Find in Files
[yellow]Alt+Shift+F[/]  Format Code
[yellow]Ctrl+Space[/]  Trigger Completion

[bold cyan]== Chat Commands ==[/]
Type in chat input:
[yellow]/diff[/]       Show git diff
[yellow]/commit[/]     AI commit message
[yellow]/undo[/]       Undo last commit
[yellow]/help[/]       Show chat commands

[dim]Press Escape or Enter to close[/]
"""


class ShortcutsScreen(ModalScreen[None]):
    """Modal screen showing keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("enter", "close", "Close", show=False),
    ]

    DEFAULT_CSS = """
    ShortcutsScreen {
        align: center middle;
    }

    #shortcuts-container {
        width: 60;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #shortcuts-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
    }

    #shortcuts-content {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="shortcuts-container"):
            yield Static("Keyboard Shortcuts", id="shortcuts-title")
            with VerticalScroll(id="shortcuts-content"):
                yield Static(SHORTCUTS, markup=True)

    def action_close(self) -> None:
        """Close the shortcuts screen."""
        self.dismiss()
