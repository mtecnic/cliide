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

    def __init__(self, approved: bool, tool_name: str) -> None:
        super().__init__()
        self.approved = approved
        self.tool_name = tool_name
