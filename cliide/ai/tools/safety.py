"""Safety and sandboxing utilities for tools."""

import os
from pathlib import Path


# Sensitive file patterns that should never be accessed
SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*_rsa",
    "*_dsa",
    "*_ecdsa",
    "*_ed25519",
    "credentials.json",
    "secrets.*",
    "*.secret",
    ".aws/credentials",
    ".ssh/*",
    ".gnupg/*",
    "*.keystore",
]


# Sensitive directories that should never be accessed
SENSITIVE_DIRS = [
    "/etc",
    "/root",
    "/sys",
    "/proc",
    "/dev",
    "~/.ssh",
    "~/.gnupg",
    "~/.aws",
]


def normalize_path(path: str | Path, workspace_root: str | Path) -> Path:
    """Normalize a path and resolve it relative to workspace.

    Args:
        path: Path to normalize (can be relative or absolute)
        workspace_root: Root directory of workspace

    Returns:
        Absolute normalized path

    Raises:
        ValueError: If path is invalid
    """
    workspace_root = Path(workspace_root).resolve()

    # Convert to Path object
    if isinstance(path, str):
        path = Path(path)

    # If relative, make it relative to workspace root
    if not path.is_absolute():
        path = workspace_root / path

    # Resolve to absolute path (handles .., ., symlinks)
    try:
        path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid path: {e}")

    return path


def validate_path(
    path: str | Path,
    workspace_root: str | Path,
    allow_outside_workspace: bool = False,
) -> tuple[bool, str, Path | None]:
    """Validate that a path is safe to access.

    Args:
        path: Path to validate
        workspace_root: Root directory of workspace
        allow_outside_workspace: Allow access outside workspace

    Returns:
        Tuple of (is_valid, error_message, normalized_path)
    """
    try:
        normalized = normalize_path(path, workspace_root)
    except ValueError as e:
        return False, str(e), None

    workspace_root = Path(workspace_root).resolve()

    # Check if path is within workspace
    if not allow_outside_workspace:
        try:
            normalized.relative_to(workspace_root)
        except ValueError:
            return False, f"Path outside workspace: {normalized}", None

    # Check for sensitive directories
    for sensitive_dir in SENSITIVE_DIRS:
        sensitive_path = Path(sensitive_dir).expanduser().resolve()
        try:
            normalized.relative_to(sensitive_path)
            return False, f"Access to sensitive directory denied: {sensitive_dir}", None
        except ValueError:
            # Not under this sensitive directory, continue checking
            pass

    # Check for sensitive file patterns
    path_str = str(normalized)
    filename = normalized.name.lower()

    for pattern in SENSITIVE_PATTERNS:
        # Simple pattern matching (could be enhanced with fnmatch)
        if pattern.startswith("*"):
            suffix = pattern[1:].lower()
            if filename.endswith(suffix):
                return False, f"Access to sensitive file denied: matches {pattern}", None
        elif pattern.endswith("*"):
            prefix = pattern[:-1].lower()
            if filename.startswith(prefix):
                return False, f"Access to sensitive file denied: matches {pattern}", None
        elif pattern.lower() in path_str.lower():
            return False, f"Access to sensitive file denied: matches {pattern}", None

    return True, "", normalized


def validate_file_size(file_path: Path, max_size_mb: float) -> tuple[bool, str]:
    """Validate that a file is not too large.

    Args:
        file_path: Path to file
        max_size_mb: Maximum allowed size in megabytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"

    if not file_path.is_file():
        return False, f"Not a file: {file_path}"

    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    if size_mb > max_size_mb:
        return False, f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)"

    return True, ""


def is_binary_file(file_path: Path, sample_size: int = 8192) -> bool:
    """Check if a file is binary.

    Args:
        file_path: Path to file
        sample_size: Number of bytes to sample

    Returns:
        True if file appears to be binary
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(sample_size)

        # Check for null bytes (common in binary files)
        if b'\x00' in chunk:
            return True

        # Check ratio of non-text bytes
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
        non_text = sum(1 for byte in chunk if byte not in text_chars)

        # If more than 30% non-text, consider it binary
        if len(chunk) > 0 and (non_text / len(chunk)) > 0.3:
            return True

        return False
    except Exception:
        # If we can't read it, assume it's binary
        return True


def get_safe_cwd(workspace_root: str | Path) -> Path:
    """Get current working directory, falling back to workspace root if invalid.

    Args:
        workspace_root: Root directory of workspace

    Returns:
        Safe current working directory
    """
    workspace_root = Path(workspace_root).resolve()

    try:
        cwd = Path.cwd().resolve()
        # Validate it's within workspace
        cwd.relative_to(workspace_root)
        return cwd
    except (ValueError, OSError):
        # Fall back to workspace root
        return workspace_root
