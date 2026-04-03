"""Chat session tabs for multi-conversation support."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Select
from textual.reactive import reactive


class ChatSessionSelected(Message):
    """Message emitted when a chat session is selected."""

    def __init__(self, session_id: str) -> None:
        """Initialize the message.

        Args:
            session_id: ID of the selected session
        """
        super().__init__()
        self.session_id = session_id


class NewChatRequested(Message):
    """Message emitted when user requests a new chat."""

    pass


class CloseChatRequested(Message):
    """Message emitted when user requests to close current chat."""

    def __init__(self, session_id: str) -> None:
        """Initialize the message.

        Args:
            session_id: ID of the session to close
        """
        super().__init__()
        self.session_id = session_id


class ChatTabs(Horizontal):
    """Tab bar for managing multiple chat sessions."""

    DEFAULT_CSS = """
    ChatTabs {
        height: 3;
        background: $surface;
        border-bottom: solid $primary;
        padding: 0 1;
    }

    ChatTabs Select {
        width: 1fr;
        margin-right: 1;
    }

    ChatTabs Button {
        min-width: 3;
        width: auto;
        margin: 0;
    }

    ChatTabs #new-chat {
        background: $success;
        color: $text;
    }

    ChatTabs #close-chat {
        background: $error;
        color: $text;
    }
    """

    active_session_id: reactive[str | None] = reactive(None)

    def __init__(self, **kwargs) -> None:
        """Initialize chat tabs."""
        super().__init__(**kwargs)
        self._sessions: dict[str, str] = {}  # id -> name

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Select(
            [],
            prompt="Select chat...",
            id="chat-select",
            allow_blank=True,
        )
        yield Button("+", id="new-chat", variant="success")
        yield Button("x", id="close-chat", variant="error")

    def add_session(self, session_id: str, name: str) -> None:
        """Add a session to the tabs.

        Args:
            session_id: Unique session ID
            name: Display name for the session
        """
        self._sessions[session_id] = name
        self._update_select()

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the tabs.

        Args:
            session_id: Session ID to remove
        """
        self._sessions.pop(session_id, None)
        self._update_select()

    def rename_session(self, session_id: str, new_name: str) -> None:
        """Rename a session.

        Args:
            session_id: Session ID to rename
            new_name: New display name
        """
        if session_id in self._sessions:
            self._sessions[session_id] = new_name
            self._update_select()

    def set_active(self, session_id: str) -> None:
        """Set the active session.

        Args:
            session_id: Session ID to activate
        """
        self.active_session_id = session_id
        select = self.query_one("#chat-select", Select)
        if session_id in self._sessions:
            select.value = session_id

    def get_session_count(self) -> int:
        """Get number of sessions.

        Returns:
            Number of sessions
        """
        return len(self._sessions)

    def _update_select(self) -> None:
        """Update the select widget options."""
        select = self.query_one("#chat-select", Select)
        options = [(name, sid) for sid, name in self._sessions.items()]
        select.set_options(options)

        # Restore selection if possible
        if self.active_session_id and self.active_session_id in self._sessions:
            select.value = self.active_session_id
        elif self._sessions:
            # Select first if current not available
            first_id = list(self._sessions.keys())[0]
            select.value = first_id
            self.active_session_id = first_id

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle session selection change.

        Args:
            event: Select changed event
        """
        if event.value and event.value != self.active_session_id:
            self.active_session_id = str(event.value)
            self.post_message(ChatSessionSelected(str(event.value)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button pressed event
        """
        if event.button.id == "new-chat":
            self.post_message(NewChatRequested())
        elif event.button.id == "close-chat":
            if self.active_session_id:
                self.post_message(CloseChatRequested(self.active_session_id))
