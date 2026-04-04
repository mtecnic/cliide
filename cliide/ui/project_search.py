"""Workspace-wide search panel (Find in Files)."""

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Checkbox, Input, Static, Tree
from textual.widgets.tree import TreeNode


class ProjectSearchPanel(Container):
    """Panel for searching across project files."""

    class SearchResultSelected(Message):
        """Sent when a search result is selected."""

        def __init__(self, file_path: str, line: int, column: int) -> None:
            super().__init__()
            self.file_path = file_path
            self.line = line
            self.column = column

    DEFAULT_CSS = """
    ProjectSearchPanel {
        width: 100%;
        height: 100%;
        background: $panel;
        border: round $primary;
    }

    #search-header {
        height: auto;
        padding: 1;
        background: $boost;
        border-bottom: heavy $primary;
    }

    #search-input {
        width: 1fr;
        border: round $accent;
    }

    #search-options {
        height: auto;
        padding: 0 1;
    }

    #search-btn {
        width: auto;
        min-width: 12;
        margin-left: 1;
    }

    #close-btn {
        width: auto;
        min-width: 10;
        margin-left: 1;
    }

    #search-results {
        height: 1fr;
        background: $surface;
        overflow-y: auto;
    }

    #search-status {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }

    .result-file {
        color: $accent;
        text-style: bold;
    }

    .result-match {
        color: $warning;
    }

    .result-line-num {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        workspace_path: Path,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """Initialize.

        Args:
            workspace_path: Root workspace path
            name: Widget name
            id: Widget ID
        """
        super().__init__(name=name, id=id)
        self._workspace_path = workspace_path
        self._search_task: asyncio.Task | None = None
        self._results: dict[str, list[dict[str, Any]]] = {}  # file -> matches

    def compose(self) -> ComposeResult:
        """Compose the panel."""
        with Vertical(id="search-header"):
            with Horizontal():
                yield Input(placeholder="Search in files...", id="search-input")
                yield Button("Search", id="search-btn", variant="primary")
                yield Button("Close", id="close-btn", variant="error")

            with Horizontal(id="search-options"):
                yield Checkbox("Regex", id="regex-check")
                yield Checkbox("Case Sensitive", id="case-check")

        yield Static("", id="search-status")

        yield Tree("Results", id="search-results")

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#search-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "search-btn":
            self._do_search()
        elif event.button.id == "close-btn":
            self.remove()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submit (Enter key)."""
        if event.input.id == "search-input":
            self._do_search()

    def _do_search(self) -> None:
        """Start the search."""
        # Cancel existing search
        if self._search_task:
            self._search_task.cancel()

        query = self.query_one("#search-input", Input).value.strip()
        if not query:
            return

        is_regex = self.query_one("#regex-check", Checkbox).value
        case_sensitive = self.query_one("#case-check", Checkbox).value

        # Update status
        self.query_one("#search-status", Static).update("Searching...")

        # Start async search
        self._search_task = asyncio.create_task(
            self._search_async(query, is_regex, case_sensitive)
        )

    async def _search_async(
        self, query: str, is_regex: bool, case_sensitive: bool
    ) -> None:
        """Perform search asynchronously.

        Args:
            query: Search query
            is_regex: Use regex
            case_sensitive: Case sensitive search
        """
        self._results.clear()

        try:
            # Try ripgrep first (faster)
            results = await self._search_ripgrep(query, is_regex, case_sensitive)

            if results is None:
                # Fallback to Python search
                results = await self._search_python(query, is_regex, case_sensitive)

            self._results = results
            self._display_results()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.query_one("#search-status", Static).update(f"Error: {e}")

    async def _search_ripgrep(
        self, query: str, is_regex: bool, case_sensitive: bool
    ) -> dict[str, list[dict[str, Any]]] | None:
        """Search using ripgrep.

        Args:
            query: Search query
            is_regex: Use regex
            case_sensitive: Case sensitive search

        Returns:
            Results dict or None if rg not available
        """
        try:
            args = ["rg", "--json", "--no-heading"]

            if not is_regex:
                args.append("--fixed-strings")

            if not case_sensitive:
                args.append("--ignore-case")

            args.append(query)
            args.append(str(self._workspace_path))

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await process.communicate()

            if process.returncode not in (0, 1):  # 1 = no matches
                return None

            return self._parse_ripgrep_output(stdout.decode("utf-8", errors="replace"))

        except FileNotFoundError:
            return None  # rg not installed

    def _parse_ripgrep_output(self, output: str) -> dict[str, list[dict[str, Any]]]:
        """Parse ripgrep JSON output.

        Args:
            output: ripgrep JSON output

        Returns:
            Results dict
        """
        import json

        results: dict[str, list[dict[str, Any]]] = {}

        for line in output.splitlines():
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data.get("data", {})
                    path = match_data.get("path", {}).get("text", "")
                    line_num = match_data.get("line_number", 0)
                    line_text = match_data.get("lines", {}).get("text", "").rstrip()

                    # Get match positions
                    submatches = match_data.get("submatches", [])
                    col = submatches[0].get("start", 0) if submatches else 0

                    if path not in results:
                        results[path] = []

                    results[path].append({
                        "line": line_num,
                        "column": col,
                        "text": line_text,
                    })

            except json.JSONDecodeError:
                continue

        return results

    async def _search_python(
        self, query: str, is_regex: bool, case_sensitive: bool
    ) -> dict[str, list[dict[str, Any]]]:
        """Fallback Python-based search.

        Args:
            query: Search query
            is_regex: Use regex
            case_sensitive: Case sensitive search

        Returns:
            Results dict
        """
        results: dict[str, list[dict[str, Any]]] = {}

        # Compile pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        if is_regex:
            pattern = re.compile(query, flags)
        else:
            pattern = re.compile(re.escape(query), flags)

        # Common text file extensions
        text_exts = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java",
            ".c", ".cpp", ".h", ".hpp", ".css", ".scss", ".html", ".xml",
            ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".sh",
            ".bash", ".lua", ".rb", ".php", ".swift", ".kt", ".sql",
        }

        # Directories to skip
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

        async def search_file(file_path: Path) -> list[dict[str, Any]]:
            """Search a single file."""
            matches = []
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        match = pattern.search(line)
                        if match:
                            matches.append({
                                "line": line_num,
                                "column": match.start(),
                                "text": line.rstrip(),
                            })
                            if len(matches) >= 100:  # Limit per file
                                break
            except Exception:
                pass
            return matches

        # Walk workspace
        for root, dirs, files in self._workspace_path.walk():
            # Skip hidden and common non-source directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            for filename in files:
                file_path = root / filename
                if file_path.suffix.lower() not in text_exts:
                    continue

                matches = await search_file(file_path)
                if matches:
                    rel_path = str(file_path.relative_to(self._workspace_path))
                    results[rel_path] = matches

                    # Yield to event loop periodically
                    await asyncio.sleep(0)

                if len(results) >= 100:  # Limit total files
                    break

            if len(results) >= 100:
                break

        return results

    def _display_results(self) -> None:
        """Display search results in tree."""
        tree = self.query_one("#search-results", Tree)
        tree.clear()
        tree.root.expand()

        total_matches = sum(len(matches) for matches in self._results.values())

        # Update status
        status = f"Found {total_matches} matches in {len(self._results)} files"
        self.query_one("#search-status", Static).update(status)

        # Add results to tree
        for file_path, matches in sorted(self._results.items()):
            # File node
            file_node = tree.root.add(
                f"[bold cyan]{file_path}[/] ({len(matches)} matches)",
                data={"file": file_path, "line": 1, "column": 0},
            )

            # Match nodes
            for match in matches[:20]:  # Limit displayed matches per file
                line_num = match["line"]
                text = match["text"][:80]  # Truncate long lines
                file_node.add_leaf(
                    f"[dim]{line_num}:[/] {text}",
                    data={
                        "file": file_path,
                        "line": line_num,
                        "column": match["column"],
                    },
                )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        data = event.node.data
        if data:
            file_path = str(self._workspace_path / data["file"])
            self.post_message(
                self.SearchResultSelected(
                    file_path=file_path,
                    line=data["line"] - 1,  # Convert to 0-indexed
                    column=data["column"],
                )
            )

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "escape":
            self.remove()
