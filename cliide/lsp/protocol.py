"""LSP protocol helpers and utilities."""

from typing import Any, Optional

from lsprotocol.types import (
    CompletionItem,
    CompletionList,
    CompletionParams,
    DefinitionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Location,
    Position,
    Range,
    ReferenceParams,
    RenameParams,
    TextDocumentIdentifier,
    TextDocumentItem,
    VersionedTextDocumentIdentifier,
    WorkspaceEdit,
)


def create_position(line: int, character: int) -> Position:
    """Create an LSP Position.

    Args:
        line: Line number (0-indexed)
        character: Character offset (0-indexed)

    Returns:
        LSP Position
    """
    return Position(line=line, character=character)


def create_range(start_line: int, start_char: int, end_line: int, end_char: int) -> Range:
    """Create an LSP Range.

    Args:
        start_line: Start line number (0-indexed)
        start_char: Start character offset (0-indexed)
        end_line: End line number (0-indexed)
        end_char: End character offset (0-indexed)

    Returns:
        LSP Range
    """
    return Range(
        start=create_position(start_line, start_char),
        end=create_position(end_line, end_char),
    )


def create_text_document_identifier(uri: str) -> TextDocumentIdentifier:
    """Create a TextDocumentIdentifier.

    Args:
        uri: Document URI (file:// path)

    Returns:
        TextDocumentIdentifier
    """
    return TextDocumentIdentifier(uri=uri)


def create_versioned_text_document_identifier(
    uri: str, version: int
) -> VersionedTextDocumentIdentifier:
    """Create a VersionedTextDocumentIdentifier.

    Args:
        uri: Document URI (file:// path)
        version: Document version number

    Returns:
        VersionedTextDocumentIdentifier
    """
    return VersionedTextDocumentIdentifier(uri=uri, version=version)


def path_to_uri(path: str) -> str:
    """Convert a file path to a file:// URI.

    Args:
        path: File path

    Returns:
        file:// URI
    """
    from pathlib import Path
    from urllib.parse import quote

    # Convert to absolute path and normalize
    abs_path = Path(path).resolve()

    # Convert to URI-safe format
    # On Windows, paths like C:\foo become file:///C:/foo
    # On Unix, paths like /foo become file:///foo
    path_str = abs_path.as_posix()

    if not path_str.startswith("/"):
        path_str = "/" + path_str

    return f"file://{quote(path_str)}"


def uri_to_path(uri: str) -> str:
    """Convert a file:// URI to a file path.

    Args:
        uri: file:// URI

    Returns:
        File path
    """
    from urllib.parse import unquote, urlparse

    parsed = urlparse(uri)

    # Handle Windows paths (file:///C:/foo -> C:\foo)
    path = unquote(parsed.path)

    # Remove leading slash on Windows
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]

    return path


def diagnostic_severity_to_string(severity: Optional[DiagnosticSeverity]) -> str:
    """Convert DiagnosticSeverity to a readable string.

    Args:
        severity: Diagnostic severity

    Returns:
        Severity string
    """
    if severity == DiagnosticSeverity.Error:
        return "Error"
    elif severity == DiagnosticSeverity.Warning:
        return "Warning"
    elif severity == DiagnosticSeverity.Information:
        return "Info"
    elif severity == DiagnosticSeverity.Hint:
        return "Hint"
    else:
        return "Unknown"


def format_diagnostic(diagnostic: Diagnostic, file_path: str) -> str:
    """Format a diagnostic for display.

    Args:
        diagnostic: LSP diagnostic
        file_path: File path

    Returns:
        Formatted string
    """
    severity = diagnostic_severity_to_string(diagnostic.severity)
    line = diagnostic.range.start.line + 1  # Convert to 1-indexed
    char = diagnostic.range.start.character + 1

    message = diagnostic.message.split("\n")[0]  # First line only

    return f"{file_path}:{line}:{char}: {severity}: {message}"


def completion_item_kind_to_icon(kind: Optional[int]) -> str:
    """Convert CompletionItemKind to an icon.

    Args:
        kind: Completion item kind value

    Returns:
        Icon string
    """
    from lsprotocol.types import CompletionItemKind

    if kind == CompletionItemKind.Text:
        return "📝"
    elif kind == CompletionItemKind.Method:
        return "🔧"
    elif kind == CompletionItemKind.Function:
        return "📦"
    elif kind == CompletionItemKind.Constructor:
        return "🏗️"
    elif kind == CompletionItemKind.Field:
        return "🏷️"
    elif kind == CompletionItemKind.Variable:
        return "📊"
    elif kind == CompletionItemKind.Class:
        return "🏛️"
    elif kind == CompletionItemKind.Interface:
        return "🔗"
    elif kind == CompletionItemKind.Module:
        return "📚"
    elif kind == CompletionItemKind.Property:
        return "🔑"
    elif kind == CompletionItemKind.Keyword:
        return "🔤"
    elif kind == CompletionItemKind.Snippet:
        return "✂️"
    else:
        return "💡"


__all__ = [
    "CompletionItem",
    "CompletionList",
    "CompletionParams",
    "DefinitionParams",
    "Diagnostic",
    "DiagnosticSeverity",
    "DidChangeTextDocumentParams",
    "DidOpenTextDocumentParams",
    "DidSaveTextDocumentParams",
    "Location",
    "Position",
    "Range",
    "ReferenceParams",
    "RenameParams",
    "TextDocumentIdentifier",
    "TextDocumentItem",
    "VersionedTextDocumentIdentifier",
    "WorkspaceEdit",
    "create_position",
    "create_range",
    "create_text_document_identifier",
    "create_versioned_text_document_identifier",
    "path_to_uri",
    "uri_to_path",
    "diagnostic_severity_to_string",
    "format_diagnostic",
    "completion_item_kind_to_icon",
]
