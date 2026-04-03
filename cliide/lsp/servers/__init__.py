"""Language server configurations."""

from typing import Optional


class ServerConfig:
    """Configuration for a language server."""

    def __init__(
        self,
        name: str,
        command: list[str],
        language_id: str,
        file_extensions: list[str],
    ) -> None:
        """Initialize server config.

        Args:
            name: Server name
            command: Command to start server
            language_id: LSP language identifier
            file_extensions: File extensions this server handles
        """
        self.name = name
        self.command = command
        self.language_id = language_id
        self.file_extensions = file_extensions


# Python server (pyright)
PYRIGHT_CONFIG = ServerConfig(
    name="pyright",
    command=["pyright-langserver", "--stdio"],
    language_id="python",
    file_extensions=[".py", ".pyi"],
)

# TypeScript/JavaScript server
TYPESCRIPT_CONFIG = ServerConfig(
    name="typescript-language-server",
    command=["typescript-language-server", "--stdio"],
    language_id="typescript",  # Will be adjusted based on file
    file_extensions=[".js", ".jsx", ".ts", ".tsx"],
)


def get_server_config(file_extension: str) -> Optional[ServerConfig]:
    """Get server config for a file extension.

    Args:
        file_extension: File extension (e.g., ".py")

    Returns:
        ServerConfig or None
    """
    configs = [PYRIGHT_CONFIG, TYPESCRIPT_CONFIG]

    for config in configs:
        if file_extension in config.file_extensions:
            return config

    return None


def get_language_id(file_extension: str) -> str:
    """Get language ID for a file extension.

    Args:
        file_extension: File extension (e.g., ".py")

    Returns:
        Language ID
    """
    mapping = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "javascriptreact",
        ".ts": "typescript",
        ".tsx": "typescriptreact",
    }

    return mapping.get(file_extension, "plaintext")


__all__ = [
    "ServerConfig",
    "PYRIGHT_CONFIG",
    "TYPESCRIPT_CONFIG",
    "get_server_config",
    "get_language_id",
]
