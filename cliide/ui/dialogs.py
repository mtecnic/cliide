"""Reusable dialog screens for user input and confirmation."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class InputDialog(ModalScreen[str]):
    """Modal dialog for text input."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }

    InputDialog > Container {
        width: 60;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }

    InputDialog #dialog-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    InputDialog #dialog-prompt {
        margin-bottom: 1;
    }

    InputDialog Input {
        margin-bottom: 1;
    }

    InputDialog Horizontal {
        align: center middle;
        height: auto;
    }

    InputDialog Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str,
        prompt: str,
        placeholder: str = "",
        initial_value: str = "",
    ) -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._placeholder = placeholder
        self._initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._title, id="dialog-title")
            yield Label(self._prompt, id="dialog-prompt")
            yield Input(
                placeholder=self._placeholder,
                value=self._initial_value,
                id="dialog-input",
            )
            with Horizontal():
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("OK", variant="primary", id="ok-btn")

    def on_mount(self) -> None:
        """Focus the input when dialog opens."""
        self.query_one("#dialog-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "ok-btn":
            value = self.query_one("#dialog-input", Input).value
            self.dismiss(value)
        else:
            self.dismiss("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss("")


class ConfirmDialog(ModalScreen[bool]):
    """Modal dialog for confirmation."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    ConfirmDialog > Container {
        width: 50;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }

    ConfirmDialog #dialog-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    ConfirmDialog #dialog-message {
        text-align: center;
        margin-bottom: 1;
    }

    ConfirmDialog Horizontal {
        align: center middle;
        height: auto;
    }

    ConfirmDialog Button {
        margin: 0 1;
    }

    ConfirmDialog .danger {
        background: $error;
    }
    """

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str = "OK",
        cancel_label: str = "Cancel",
        danger: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._danger = danger

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._title, id="dialog-title")
            yield Label(self._message, id="dialog-message")
            with Horizontal():
                yield Button(self._cancel_label, variant="default", id="cancel-btn")
                confirm_btn = Button(
                    self._confirm_label,
                    variant="error" if self._danger else "primary",
                    id="confirm-btn",
                )
                if self._danger:
                    confirm_btn.add_class("danger")
                yield confirm_btn

    def on_mount(self) -> None:
        """Focus the confirm button."""
        self.query_one("#confirm-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id == "confirm-btn")

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Confirm the dialog."""
        self.dismiss(True)
