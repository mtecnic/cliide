"""Language Server Manager - manages multiple LSP clients."""

from pathlib import Path
from typing import Any, Callable, Optional

from cliide.lsp.client import AsyncLSPClient
from cliide.lsp.servers import get_language_id, get_server_config
from cliide.utils.logger import log


class LanguageServerManager:
    """Manages multiple language server clients."""

    def __init__(self, workspace_path: Path) -> None:
        """Initialize the manager.

        Args:
            workspace_path: Root workspace path
        """
        self.workspace_path = workspace_path
        self.clients: dict[str, AsyncLSPClient] = {}  # server_name -> client
        self.file_to_server: dict[str, str] = {}  # file_path -> server_name
        self.diagnostic_handler: Optional[Callable[[str, list[Any]], None]] = None

    async def start_server_for_file(self, file_path: str) -> bool:
        """Start a language server for a file if not already running.

        Args:
            file_path: File path

        Returns:
            True if server is available
        """
        # Get file extension
        path = Path(file_path)
        ext = path.suffix

        # Get server config
        config = get_server_config(ext)
        if not config:
            log(f"[LSP Manager] No server configured for {ext}")
            return False

        # Check if server already running
        if config.name in self.clients:
            log(f"[LSP Manager] Server {config.name} already running")
            return True

        # Start server
        log(f"[LSP Manager] Starting {config.name} for {ext} files")

        client = AsyncLSPClient(config.command, self.workspace_path)

        # Register diagnostic handler
        if self.diagnostic_handler:
            client.register_notification_handler(
                "textDocument/publishDiagnostics",
                self._handle_diagnostics,
            )

        success = await client.start()

        if success:
            self.clients[config.name] = client
            log(f"[LSP Manager] {config.name} started successfully")
            return True
        else:
            log(f"[LSP Manager] Failed to start {config.name}")
            return False

    async def stop_all_servers(self) -> None:
        """Stop all running language servers."""
        log("[LSP Manager] Stopping all servers")

        for name, client in self.clients.items():
            log(f"[LSP Manager] Stopping {name}")
            await client.stop()

        self.clients.clear()
        self.file_to_server.clear()

    def get_client_for_file(self, file_path: str) -> Optional[AsyncLSPClient]:
        """Get the LSP client for a file.

        Args:
            file_path: File path

        Returns:
            AsyncLSPClient or None
        """
        # Get file extension
        ext = Path(file_path).suffix

        # Get server config
        config = get_server_config(ext)
        if not config:
            return None

        # Return client if running
        return self.clients.get(config.name)

    async def did_open(self, file_path: str, content: str) -> None:
        """Notify LSP that a file was opened.

        Args:
            file_path: File path
            content: File content
        """
        # Ensure server is started
        success = await self.start_server_for_file(file_path)
        if not success:
            return

        # Get client
        client = self.get_client_for_file(file_path)
        if not client:
            return

        # Get language ID
        ext = Path(file_path).suffix
        language_id = get_language_id(ext)

        # Track file
        config = get_server_config(ext)
        if config:
            self.file_to_server[file_path] = config.name

        # Send didOpen
        await client.did_open(file_path, language_id, version=1, content=content)
        log(f"[LSP Manager] Sent didOpen for {file_path}")

    async def did_change(self, file_path: str, version: int, content: str) -> None:
        """Notify LSP that a file changed.

        Args:
            file_path: File path
            version: Document version
            content: New content
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return

        await client.did_change(file_path, version, content)
        log(f"[LSP Manager] Sent didChange for {file_path} (v{version})")

    async def did_save(self, file_path: str) -> None:
        """Notify LSP that a file was saved.

        Args:
            file_path: File path
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return

        await client.did_save(file_path)
        log(f"[LSP Manager] Sent didSave for {file_path}")

    async def completion(
        self, file_path: str, line: int, character: int
    ) -> Optional[list[Any]]:
        """Request completions.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)

        Returns:
            List of completion items
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return None

        return await client.completion(file_path, line, character)

    async def definition(
        self, file_path: str, line: int, character: int
    ) -> Optional[list[Any]]:
        """Request definition.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)

        Returns:
            List of locations
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return None

        return await client.definition(file_path, line, character)

    async def references(
        self, file_path: str, line: int, character: int, include_declaration: bool = True
    ) -> Optional[list[Any]]:
        """Request references.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)
            include_declaration: Include declaration in results

        Returns:
            List of locations
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return None

        return await client.references(file_path, line, character, include_declaration)

    async def rename(
        self, file_path: str, line: int, character: int, new_name: str
    ) -> Optional[Any]:
        """Request rename.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)
            new_name: New symbol name

        Returns:
            WorkspaceEdit
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return None

        return await client.rename(file_path, line, character, new_name)

    def register_diagnostic_handler(
        self, handler: Callable[[str, list[Any]], None]
    ) -> None:
        """Register a handler for diagnostics.

        Args:
            handler: Callback function (file_path, diagnostics)
        """
        self.diagnostic_handler = handler

    def _handle_diagnostics(self, params: dict[str, Any]) -> None:
        """Handle diagnostics notification from LSP.

        Args:
            params: Diagnostic parameters
        """
        if not self.diagnostic_handler:
            return

        from cliide.lsp.protocol import uri_to_path

        uri = params.get("uri", "")
        file_path = uri_to_path(uri)
        diagnostics = params.get("diagnostics", [])

        log(f"[LSP Manager] Received {len(diagnostics)} diagnostics for {file_path}")

        self.diagnostic_handler(file_path, diagnostics)
