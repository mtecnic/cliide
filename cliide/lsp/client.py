"""Async LSP client for communication with language servers."""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Optional

from lsprotocol.types import (
    ClientCapabilities,
    CompletionParams,
    DefinitionParams,
    InitializeParams,
    InitializeResult,
    InitializedParams,
    ReferenceParams,
    RenameParams,
    TextDocumentSyncKind,
    WorkspaceFolder,
)

from cliide.lsp.protocol import path_to_uri
from cliide.utils.logger import log


class AsyncLSPClient:
    """Async LSP client that communicates with a language server via JSON-RPC."""

    def __init__(self, server_command: list[str], workspace_path: Path) -> None:
        """Initialize the LSP client.

        Args:
            server_command: Command to start the language server (e.g., ["pyright", "--stdio"])
            workspace_path: Root path of the workspace
        """
        self.server_command = server_command
        self.workspace_path = workspace_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: dict[int, asyncio.Future[Any]] = {}
        self.notification_handlers: dict[str, Callable[[Any], None]] = {}
        self.initialized = False
        self.capabilities: Optional[Any] = None
        self._read_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> bool:
        """Start the language server process.

        Returns:
            True if started successfully
        """
        try:
            log(f"[LSP] Starting server: {' '.join(self.server_command)}")

            # Start the process
            self.process = await asyncio.create_subprocess_exec(
                *self.server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Start reading responses
            self._read_task = asyncio.create_task(self._read_messages())

            # Initialize the server
            result = await self._initialize()

            if result:
                self.initialized = True
                self.capabilities = result.capabilities
                log("[LSP] Server initialized successfully")
                return True
            else:
                log("[LSP] Failed to initialize server")
                return False

        except Exception as e:
            log(f"[LSP] Error starting server: {e}")
            return False

    async def stop(self) -> None:
        """Stop the language server process."""
        if not self.process:
            return

        try:
            # Send shutdown request
            await self._send_request("shutdown", {})

            # Send exit notification
            await self._send_notification("exit", {})

            # Wait for process to exit
            await asyncio.wait_for(self.process.wait(), timeout=5.0)

        except asyncio.TimeoutError:
            log("[LSP] Server did not exit gracefully, terminating")
            if self.process:
                self.process.terminate()
                await self.process.wait()
        except Exception as e:
            log(f"[LSP] Error stopping server: {e}")

        finally:
            if self._read_task:
                self._read_task.cancel()
                try:
                    await self._read_task
                except asyncio.CancelledError:
                    pass

            # Close pipes properly
            if self.process:
                if self.process.stdin and not self.process.stdin.is_closing():
                    self.process.stdin.close()
                if self.process.stdout and not self.process.stdout.at_eof():
                    self.process.stdout.feed_eof()
                if self.process.stderr and not self.process.stderr.at_eof():
                    self.process.stderr.feed_eof()

            self.initialized = False
            self.process = None

    async def _initialize(self) -> Optional[InitializeResult]:
        """Send initialize request to the server.

        Returns:
            InitializeResult if successful
        """
        workspace_uri = path_to_uri(str(self.workspace_path))

        params = InitializeParams(
            process_id=None,
            root_uri=workspace_uri,
            workspace_folders=[
                WorkspaceFolder(
                    uri=workspace_uri,
                    name=self.workspace_path.name,
                )
            ],
            capabilities=ClientCapabilities(
                text_document=None,  # Use defaults
                workspace=None,
            ),
        )

        try:
            result = await self._send_request("initialize", params)

            # Send initialized notification
            await self._send_notification("initialized", InitializedParams())

            # Parse result as InitializeResult
            if result:
                return InitializeResult(**result)
            return None

        except Exception as e:
            log(f"[LSP] Initialize error: {e}")
            return None

    async def _read_messages(self) -> None:
        """Read messages from the server's stdout."""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                # Read headers
                headers: dict[str, str] = {}
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        return  # EOF

                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        break  # Empty line, end of headers

                    key, value = line_str.split(":", 1)
                    headers[key.strip()] = value.strip()

                # Get content length
                content_length = int(headers.get("Content-Length", 0))
                if content_length == 0:
                    continue

                # Read content
                content = await self.process.stdout.readexactly(content_length)
                message = json.loads(content.decode("utf-8"))

                # Handle message
                await self._handle_message(message)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log(f"[LSP] Error reading messages: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle a message from the server.

        Args:
            message: JSON-RPC message
        """
        if "id" in message and "result" in message:
            # Response to a request
            request_id = message["id"]
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                future.set_result(message["result"])

        elif "id" in message and "error" in message:
            # Error response
            request_id = message["id"]
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                error = message["error"]
                future.set_exception(
                    Exception(f"LSP Error {error.get('code')}: {error.get('message')}")
                )

        elif "method" in message:
            # Notification or request from server
            method = message["method"]
            params = message.get("params", {})

            # Call notification handler if registered
            if method in self.notification_handlers:
                handler = self.notification_handlers[method]
                handler(params)

    async def _send_request(self, method: str, params: Any) -> Any:
        """Send a request to the server and wait for response.

        Args:
            method: LSP method name
            params: Request parameters

        Returns:
            Response result
        """
        if not self.process or not self.process.stdin:
            raise Exception("Server not started")

        request_id = self.request_id
        self.request_id += 1

        # Create future for response
        future: asyncio.Future[Any] = asyncio.Future()
        self.pending_requests[request_id] = future

        # Build message
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": self._serialize_params(params),
        }

        # Send message
        await self._write_message(message)

        # Wait for response (with timeout)
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            log(f"[LSP] Request timeout: {method}")
            return None

    async def _send_notification(self, method: str, params: Any) -> None:
        """Send a notification to the server (no response expected).

        Args:
            method: LSP method name
            params: Notification parameters
        """
        if not self.process or not self.process.stdin:
            return

        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": self._serialize_params(params),
        }

        await self._write_message(message)

    async def _write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to the server.

        Args:
            message: Message dict
        """
        if not self.process or not self.process.stdin:
            return

        content = json.dumps(message)
        content_bytes = content.encode("utf-8")

        # Build headers
        headers = f"Content-Length: {len(content_bytes)}\r\n\r\n"

        # Write to stdin
        self.process.stdin.write(headers.encode("utf-8"))
        self.process.stdin.write(content_bytes)
        await self.process.stdin.drain()

    def _serialize_params(self, params: Any) -> Any:
        """Serialize parameters for JSON-RPC.

        Args:
            params: Parameters (can be dataclass from lsprotocol)

        Returns:
            Serializable dict
        """
        if hasattr(params, "__dict__"):
            # Convert dataclass to dict
            return self._obj_to_dict(params)
        return params

    def _obj_to_dict(self, obj: Any) -> Any:
        """Recursively convert an object to a dict.

        Args:
            obj: Object to convert

        Returns:
            Dict representation
        """
        if hasattr(obj, "__dict__"):
            result: dict[str, Any] = {}
            for key, value in obj.__dict__.items():
                if value is not None:
                    result[key] = self._obj_to_dict(value)
            return result
        elif isinstance(obj, list):
            return [self._obj_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._obj_to_dict(v) for k, v in obj.items()}
        else:
            return obj

    def register_notification_handler(self, method: str, handler: Callable[[Any], None]) -> None:
        """Register a handler for server notifications.

        Args:
            method: LSP method name (e.g., "textDocument/publishDiagnostics")
            handler: Callback function
        """
        self.notification_handlers[method] = handler

    async def did_open(
        self, file_path: str, language_id: str, version: int, content: str
    ) -> None:
        """Send textDocument/didOpen notification.

        Args:
            file_path: File path
            language_id: Language identifier (e.g., "python")
            version: Document version
            content: File content
        """
        from lsprotocol.types import DidOpenTextDocumentParams, TextDocumentItem

        params = DidOpenTextDocumentParams(
            text_document=TextDocumentItem(
                uri=path_to_uri(file_path),
                language_id=language_id,
                version=version,
                text=content,
            )
        )

        await self._send_notification("textDocument/didOpen", params)

    async def did_change(self, file_path: str, version: int, content: str) -> None:
        """Send textDocument/didChange notification.

        Args:
            file_path: File path
            version: Document version
            content: New file content
        """
        from lsprotocol.types import (
            DidChangeTextDocumentParams,
            TextDocumentContentChangeEvent,
            VersionedTextDocumentIdentifier,
        )

        params = DidChangeTextDocumentParams(
            text_document=VersionedTextDocumentIdentifier(
                uri=path_to_uri(file_path),
                version=version,
            ),
            content_changes=[TextDocumentContentChangeEvent(text=content)],
        )

        await self._send_notification("textDocument/didChange", params)

    async def did_save(self, file_path: str) -> None:
        """Send textDocument/didSave notification.

        Args:
            file_path: File path
        """
        from lsprotocol.types import DidSaveTextDocumentParams, TextDocumentIdentifier

        params = DidSaveTextDocumentParams(
            text_document=TextDocumentIdentifier(uri=path_to_uri(file_path))
        )

        await self._send_notification("textDocument/didSave", params)

    async def completion(
        self, file_path: str, line: int, character: int
    ) -> Optional[list[Any]]:
        """Request code completions.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)

        Returns:
            List of completion items
        """
        from lsprotocol.types import Position, TextDocumentIdentifier

        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri=path_to_uri(file_path)),
            position=Position(line=line, character=character),
        )

        result = await self._send_request("textDocument/completion", params)

        if result is None:
            return None

        # Result can be CompletionList or list of CompletionItem
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        elif isinstance(result, list):
            return result
        return None

    async def definition(self, file_path: str, line: int, character: int) -> Optional[list[Any]]:
        """Request definition location.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)

        Returns:
            List of locations
        """
        from lsprotocol.types import Position, TextDocumentIdentifier

        params = DefinitionParams(
            text_document=TextDocumentIdentifier(uri=path_to_uri(file_path)),
            position=Position(line=line, character=character),
        )

        result = await self._send_request("textDocument/definition", params)

        if result is None:
            return None

        # Result can be Location or list of Location
        if isinstance(result, dict):
            return [result]
        elif isinstance(result, list):
            return result
        return None

    async def references(
        self, file_path: str, line: int, character: int, include_declaration: bool = True
    ) -> Optional[list[Any]]:
        """Request references to a symbol.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)
            include_declaration: Include declaration in results

        Returns:
            List of locations
        """
        from lsprotocol.types import Position, ReferenceContext, TextDocumentIdentifier

        params = ReferenceParams(
            text_document=TextDocumentIdentifier(uri=path_to_uri(file_path)),
            position=Position(line=line, character=character),
            context=ReferenceContext(include_declaration=include_declaration),
        )

        result = await self._send_request("textDocument/references", params)
        return result if isinstance(result, list) else None

    async def rename(self, file_path: str, line: int, character: int, new_name: str) -> Optional[Any]:
        """Request rename operation.

        Args:
            file_path: File path
            line: Line number (0-indexed)
            character: Character offset (0-indexed)
            new_name: New symbol name

        Returns:
            WorkspaceEdit
        """
        from lsprotocol.types import Position, TextDocumentIdentifier

        params = RenameParams(
            text_document=TextDocumentIdentifier(uri=path_to_uri(file_path)),
            position=Position(line=line, character=character),
            new_name=new_name,
        )

        result = await self._send_request("textDocument/rename", params)
        return result
