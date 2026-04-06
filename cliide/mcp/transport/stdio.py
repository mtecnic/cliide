"""Stdio transport for local MCP servers.

This transport communicates with MCP servers via standard input/output
using newline-delimited JSON messages.
"""

import asyncio
import json
import os
from typing import Any

from cliide.mcp.transport.base import Transport
from cliide.utils.logger import log


class StdioTransport(Transport):
    """Transport that communicates via stdin/stdout of a subprocess."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        """Initialize stdio transport.

        Args:
            command: Command to execute (e.g., "npx")
            args: Command arguments (e.g., ["-y", "@modelcontextprotocol/server-github"])
            env: Additional environment variables
            cwd: Working directory for the process
        """
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd

        self._process: asyncio.subprocess.Process | None = None
        self._connected = False
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected and self._process is not None

    async def start(self) -> bool:
        """Start the subprocess and establish connection.

        Returns:
            True if subprocess started successfully
        """
        try:
            # Build environment
            process_env = os.environ.copy()
            process_env.update(self.env)

            # Build command
            full_command = [self.command] + self.args
            log(f"[MCP_STDIO] Starting: {' '.join(full_command)}")

            # Start subprocess
            self._process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=self.cwd,
            )

            self._connected = True
            log(f"[MCP_STDIO] Process started with PID: {self._process.pid}")

            # Start stderr reader for debugging
            asyncio.create_task(self._read_stderr())

            return True

        except FileNotFoundError as e:
            log(f"[MCP_STDIO] Command not found: {self.command}: {e}")
            return False
        except Exception as e:
            log(f"[MCP_STDIO] Failed to start subprocess: {e}")
            return False

    async def stop(self) -> None:
        """Stop the subprocess and clean up."""
        self._connected = False

        if self._process:
            try:
                # Close stdin to signal EOF
                if self._process.stdin:
                    self._process.stdin.close()
                    await self._process.stdin.wait_closed()

                # Wait for process to terminate with timeout
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    log("[MCP_STDIO] Process did not terminate, killing...")
                    self._process.kill()
                    await self._process.wait()

                log(f"[MCP_STDIO] Process terminated with code: {self._process.returncode}")

            except Exception as e:
                log(f"[MCP_STDIO] Error stopping process: {e}")

            self._process = None

    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the server.

        Args:
            message: JSON-RPC message dict
        """
        if not self.is_connected or not self._process or not self._process.stdin:
            raise ConnectionError("Transport not connected")

        async with self._write_lock:
            try:
                # Serialize to JSON and add newline
                data = json.dumps(message) + "\n"
                log(f"[MCP_STDIO] Sending: {data[:200]}...")

                self._process.stdin.write(data.encode("utf-8"))
                await self._process.stdin.drain()

            except Exception as e:
                log(f"[MCP_STDIO] Error sending message: {e}")
                self._connected = False
                raise

    async def receive(self) -> dict[str, Any] | None:
        """Receive a JSON-RPC message from the server.

        Returns:
            JSON-RPC message dict or None if connection closed
        """
        if not self.is_connected or not self._process or not self._process.stdout:
            return None

        async with self._read_lock:
            try:
                # Read a line from stdout
                line = await self._process.stdout.readline()

                if not line:
                    log("[MCP_STDIO] EOF received")
                    self._connected = False
                    return None

                # Parse JSON
                data = line.decode("utf-8").strip()
                if not data:
                    return None

                log(f"[MCP_STDIO] Received: {data[:200]}...")
                return json.loads(data)

            except json.JSONDecodeError as e:
                log(f"[MCP_STDIO] Invalid JSON received: {e}")
                return None
            except Exception as e:
                log(f"[MCP_STDIO] Error receiving message: {e}")
                self._connected = False
                return None

    async def _read_stderr(self) -> None:
        """Read stderr for debugging."""
        if not self._process or not self._process.stderr:
            return

        try:
            while self.is_connected:
                line = await self._process.stderr.readline()
                if not line:
                    break
                stderr_text = line.decode("utf-8", errors="replace").strip()
                if stderr_text:
                    log(f"[MCP_STDIO] stderr: {stderr_text}")
        except Exception as e:
            log(f"[MCP_STDIO] Error reading stderr: {e}")
