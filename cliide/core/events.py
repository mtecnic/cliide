"""Custom events for cliide application."""

from textual.message import Message


class FileOpened(Message):
    """Event sent when a file is opened."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class FileSaved(Message):
    """Event sent when a file is saved."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class AIRequestStarted(Message):
    """Event sent when an AI request starts."""

    bubble = True  # Ensure event bubbles to app

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt


class AIResponseReceived(Message):
    """Event sent when an AI response is received."""

    def __init__(self, response: str, streaming: bool = False) -> None:
        super().__init__()
        self.response = response
        self.streaming = streaming


class CommandExecuted(Message):
    """Event sent when a command is executed."""

    def __init__(self, command: str, args: dict[str, str] | None = None) -> None:
        super().__init__()
        self.command = command
        self.args = args or {}


class LSPDiagnostic(Message):
    """Event sent when LSP diagnostics are received."""

    def __init__(self, path: str, diagnostics: list[dict[str, str]]) -> None:
        super().__init__()
        self.path = path
        self.diagnostics = diagnostics


class ToolExecutionStarted(Message):
    """Event sent when a tool execution starts."""

    bubble = True

    def __init__(self, tool_name: str, args: dict, tool_call_id: str | None = None) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.args = args
        self.tool_call_id = tool_call_id


class ToolExecutionCompleted(Message):
    """Event sent when a tool execution completes."""

    bubble = True

    def __init__(self, tool_name: str, result: any, tool_call_id: str | None = None) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.result = result
        self.tool_call_id = tool_call_id


class ToolConfirmationRequired(Message):
    """Event sent when a tool requires user confirmation."""

    bubble = True

    def __init__(self, tool_name: str, args: dict, callback: any) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.args = args
        self.callback = callback


class ToolConfirmationResult(Message):
    """Event sent with result of tool confirmation."""

    bubble = True

    def __init__(self, approved: bool, tool_name: str, auto_session: bool = False) -> None:
        super().__init__()
        self.approved = approved
        self.tool_name = tool_name
        self.auto_session = auto_session  # If True, auto-approve all future tools this session


class FileSystemChanged(Message):
    """Event sent when external file system changes are detected."""

    def __init__(self, paths: list[str], event_type: str = "modified") -> None:
        super().__init__()
        self.paths = paths
        self.event_type = event_type  # "created", "deleted", "modified", "moved"


class FileCreated(Message):
    """Event sent when a new file is created via file tree."""

    bubble = True

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class FileDeleted(Message):
    """Event sent when a file is deleted via file tree."""

    bubble = True

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class FileRenamed(Message):
    """Event sent when a file is renamed via file tree."""

    bubble = True

    def __init__(self, old_path: str, new_path: str) -> None:
        super().__init__()
        self.old_path = old_path
        self.new_path = new_path
