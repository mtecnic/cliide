"""Language Server Manager - manages multiple LSP clients."""

import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

from cliide.lsp.client import AsyncLSPClient
from cliide.lsp.servers import get_language_id, get_server_config
from cliide.utils.logger import log

# Cache TTL in seconds
_LSP_CACHE_TTL = 60.0


class _CacheEntry:
    """Simple cache entry with TTL."""
    __slots__ = ('value', 'expires_at')

    def __init__(self, value: Any, ttl: float = _LSP_CACHE_TTL):
        self.value = value
        self.expires_at = time.monotonic() + ttl

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


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
        self.diagnostic_handlers: list[Callable[[str, list[Any]], None]] = []
        # Keep legacy single handler for backwards compatibility
        self.diagnostic_handler: Optional[Callable[[str, list[Any]], None]] = None
        # LSP result caches (keyed by (file_path, line, character))
        self._completion_cache: dict[tuple[str, int, int], _CacheEntry] = {}
        self._definition_cache: dict[tuple[str, int, int], _CacheEntry] = {}
        self._hover_cache: dict[tuple[str, int, int], _CacheEntry] = {}

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

        # Register diagnostic handler if any handlers registered
        if self.diagnostic_handlers or self.diagnostic_handler:
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

        # Invalidate caches for this file (content changed)
        self._invalidate_file_cache(file_path)

        await client.did_change(file_path, version, content)
        log(f"[LSP Manager] Sent didChange for {file_path} (v{version})")

    def _invalidate_file_cache(self, file_path: str) -> None:
        """Invalidate all cached results for a file.

        Args:
            file_path: File path to invalidate
        """
        # Remove entries for this file from all caches
        for cache in (self._completion_cache, self._definition_cache, self._hover_cache):
            keys_to_remove = [k for k in cache if k[0] == file_path]
            for key in keys_to_remove:
                del cache[key]

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
        """Request completions (cached for 60s).

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

        # Check cache
        cache_key = (file_path, line, character)
        entry = self._completion_cache.get(cache_key)
        if entry and entry.is_valid():
            return entry.value

        # Fetch and cache
        result = await client.completion(file_path, line, character)
        self._completion_cache[cache_key] = _CacheEntry(result)
        return result

    async def definition(
        self, file_path: str, line: int, character: int
    ) -> Optional[list[Any]]:
        """Request definition (cached for 60s).

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

        # Check cache
        cache_key = (file_path, line, character)
        entry = self._definition_cache.get(cache_key)
        if entry and entry.is_valid():
            return entry.value

        # Fetch and cache
        result = await client.definition(file_path, line, character)
        self._definition_cache[cache_key] = _CacheEntry(result)
        return result

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

    async def hover(
        self, file_path: str, line: int, character: int
    ) -> Optional[dict[str, Any]]:
        """Request hover information (cached for 60s).

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)

        Returns:
            Hover result with contents
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return None

        # Check cache
        cache_key = (file_path, line, character)
        entry = self._hover_cache.get(cache_key)
        if entry and entry.is_valid():
            return entry.value

        # Fetch and cache
        result = await client.hover(file_path, line, character)
        self._hover_cache[cache_key] = _CacheEntry(result)
        return result

    async def document_symbols(self, file_path: str) -> Optional[list[Any]]:
        """Request document symbols (outline).

        Args:
            file_path: File path

        Returns:
            List of document symbols
        """
        client = self.get_client_for_file(file_path)
        if not client:
            return None

        return await client.document_symbols(file_path)

    def register_diagnostic_handler(
        self, handler: Callable[[str, list[Any]], None]
    ) -> None:
        """Register a handler for diagnostics.

        Multiple handlers can be registered. Each will be called when diagnostics arrive.

        Args:
            handler: Callback function (file_path, diagnostics)
        """
        # Legacy support
        if self.diagnostic_handler is None:
            self.diagnostic_handler = handler
        # Add to handlers list
        if handler not in self.diagnostic_handlers:
            self.diagnostic_handlers.append(handler)
            log(f"[LSP Manager] Registered diagnostic handler ({len(self.diagnostic_handlers)} total)")

    def _handle_diagnostics(self, params: dict[str, Any]) -> None:
        """Handle diagnostics notification from LSP.

        Args:
            params: Diagnostic parameters
        """
        if not self.diagnostic_handlers and not self.diagnostic_handler:
            return

        from cliide.lsp.protocol import uri_to_path

        uri = params.get("uri", "")
        file_path = uri_to_path(uri)
        diagnostics = params.get("diagnostics", [])

        log(f"[LSP Manager] Received {len(diagnostics)} diagnostics for {file_path}")

        # Call all registered handlers
        for handler in self.diagnostic_handlers:
            try:
                handler(file_path, diagnostics)
            except Exception as e:
                log(f"[LSP Manager] Error in diagnostic handler: {e}")
