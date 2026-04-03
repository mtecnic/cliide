"""Settings screen for configuring cliide."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from cliide.core.config import get_config, update_vllm_config
from cliide.utils.logger import log


class SettingsScreen(ModalScreen[bool]):
    """Settings modal for VLLM configuration."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center top;
        overflow-y: auto;
    }

    #settings-container {
        width: 80;
        height: auto;
        margin: 2 0 4 0;
        background: $panel;
        border: round $primary;
        layout: vertical;
    }

    #settings-header {
        dock: top;
        height: 1;
        background: $boost;
        border-bottom: heavy $primary;
        padding: 0 1;
        color: $primary;
        text-style: bold;
    }

    #settings-content {
        height: auto;
        padding: 1;
        background: $surface;
        overflow-y: auto;
    }

    .settings-section {
        margin: 0 0 1 0;
        border: none;
        background: $surface;
        padding: 0;
        height: auto;
    }

    .settings-label {
        color: $accent;
        text-style: bold;
        margin: 0;
        height: 1;
    }

    .url-input-row {
        width: 100%;
        height: 3;
    }

    .url-input-row > Input {
        width: 1fr;
        margin: 0;
        height: 3;
        border: round $primary;
        background: $background;
    }

    .url-input-row > Button {
        width: auto;
        min-width: 14;
        height: 3;
        margin-left: 1;
    }

    .settings-input {
        width: 100%;
        height: 3;
        margin: 0;
        border: round $primary;
        background: $background;
    }

    .settings-hint {
        color: $text 50%;
        margin: 0;
        height: 1;
    }

    #connection-status {
        height: 1;
        margin: 0;
        padding: 0 1;
        text-align: center;
        background: $surface;
        content-align: center middle;
    }

    .status-checking {
        color: $warning;
    }

    .status-success {
        color: $success;
    }

    .status-error {
        color: $error;
    }

    #settings-footer {
        height: 1;
        background: $surface;
        color: $text 50%;
        text-align: center;
        padding: 0 1;
        margin: 0;
    }

    #settings-buttons {
        dock: bottom;
        height: 5;
        align: center middle;
        background: $boost;
        border-top: heavy $accent;
        padding: 1 1;
    }

    #settings-buttons Button {
        margin: 0 1;
        border: round $primary;
    }
    """

    class ConfigSaved(Message):
        """Sent when configuration is saved."""
        pass

    def compose(self) -> ComposeResult:
        """Compose the settings screen."""
        # Load current config
        from cliide.core.config import get_user_config_path
        config = get_config()
        config_path = get_user_config_path()
        log(f"[SETTINGS] Config file path: {config_path}")
        log(f"[SETTINGS] Config file exists: {config_path.exists()}")
        if config_path.exists():
            log(f"[SETTINGS] Config file size: {config_path.stat().st_size} bytes")
        log(f"[SETTINGS] Loading config - URL: {config.vllm.base_url}, Model: {config.vllm.model}, Temp: {config.vllm.temperature}, MaxTokens: {config.vllm.max_tokens}")

        with Container(id="settings-container"):
            yield Static("⚙️ VLLM Settings", id="settings-header")

            with Vertical(id="settings-content"):
                # API Base URL
                with Container(classes="settings-section"):
                    yield Label("API Base URL:", classes="settings-label")
                    with Horizontal(classes="url-input-row"):
                        yield Input(
                            value=config.vllm.base_url,
                            placeholder="http://localhost:8000/v1",
                            id="url-input",
                            classes="settings-input"
                        )
                        yield Button("🔍 Auto-fill", id="auto-fill-btn", variant="primary")
                    yield Static("The base URL for your VLLM/OpenAI-compatible API", classes="settings-hint")

                # API Key
                with Container(classes="settings-section"):
                    yield Label("API Key (optional):", classes="settings-label")
                    yield Input(
                        value=config.vllm.api_key or "",
                        placeholder="Leave empty if no authentication required",
                        password=True,
                        id="api-key-input",
                        classes="settings-input"
                    )
                    yield Static("Optional authentication key for the API", classes="settings-hint")

                # Model Name
                with Container(classes="settings-section"):
                    yield Label("Model Name:", classes="settings-label")
                    yield Input(
                        value=config.vllm.model,
                        placeholder="deepseek-coder-33b-instruct",
                        id="model-input",
                        classes="settings-input"
                    )
                    yield Static("The model identifier to use for completions", classes="settings-hint")

                # Temperature
                with Container(classes="settings-section"):
                    yield Label("Temperature:", classes="settings-label")
                    yield Input(
                        value=str(config.vllm.temperature),
                        placeholder="0.2",
                        id="temperature-input",
                        classes="settings-input"
                    )
                    yield Static("Sampling temperature (0.0-2.0, lower is more focused)", classes="settings-hint")

                # Max Tokens
                with Container(classes="settings-section"):
                    yield Label("Max Tokens:", classes="settings-label")
                    yield Input(
                        value=str(config.vllm.max_tokens),
                        placeholder="2048",
                        id="max-tokens-input",
                        classes="settings-input"
                    )
                    yield Static("Maximum tokens to generate in responses", classes="settings-hint")

            # Connection status outside content area
            yield Static("", id="connection-status")

            # Footer showing config file location
            yield Static(f"Config: {config_path}", id="settings-footer")

            with Horizontal(id="settings-buttons"):
                yield Button("Test Connection", id="test-btn", variant="primary")
                yield Button("Save & Close", id="save-btn", variant="success")
                yield Button("Cancel", id="cancel-btn", variant="error")

    def on_mount(self) -> None:
        """Focus the URL input on mount."""
        self.query_one("#url-input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "auto-fill-btn":
            await self._auto_fill_from_api()
        elif event.button.id == "test-btn":
            await self._test_connection()
        elif event.button.id == "save-btn":
            await self._save_config()
        elif event.button.id == "cancel-btn":
            self.dismiss(False)

    async def _auto_fill_from_api(self) -> None:
        """Connect to API and auto-fill model details."""
        log("[SETTINGS] Auto-fill button clicked")
        status = self.query_one("#connection-status", Static)
        status.update("🔍 Detecting models...")
        status.remove_class("status-success", "status-error")
        status.add_class("status-checking")

        try:
            # Get current URL
            url = self.query_one("#url-input", Input).value
            api_key = self.query_one("#api-key-input", Input).value or None
            log(f"[SETTINGS] Connecting to: {url}")

            if not url:
                status.update("🔴 Please enter an API URL first")
                status.remove_class("status-checking", "status-success")
                status.add_class("status-error")
                return

            # Import here to avoid circular dependency
            from openai import AsyncOpenAI

            # Create temporary client
            client = AsyncOpenAI(
                base_url=url,
                api_key=api_key or "EMPTY",
                timeout=10.0,
            )

            # Get list of models
            log("[SETTINGS] Fetching models list...")
            models_response = await client.models.list()
            models_data = models_response.data
            log(f"[SETTINGS] Found {len(models_data)} models")

            if models_data:
                # Auto-fill with first model
                first_model_data = models_data[0]
                first_model = first_model_data.id
                model_input = self.query_one("#model-input", Input)
                model_input.value = first_model
                log(f"[SETTINGS] Auto-filled model: {first_model}")

                # Try to extract max tokens from model metadata
                max_tokens_detected = None
                if hasattr(first_model_data, 'max_model_len'):
                    max_tokens_detected = first_model_data.max_model_len
                    log(f"[SETTINGS] Found max_model_len: {max_tokens_detected}")
                elif hasattr(first_model_data, 'context_length'):
                    max_tokens_detected = first_model_data.context_length
                    log(f"[SETTINGS] Found context_length: {max_tokens_detected}")
                elif hasattr(first_model_data, 'max_tokens'):
                    max_tokens_detected = first_model_data.max_tokens
                    log(f"[SETTINGS] Found max_tokens: {max_tokens_detected}")

                # If we found max tokens, use a reasonable generation limit (1/4 of context window)
                if max_tokens_detected:
                    # Use 1/4 of context window for generation (common practice)
                    generation_limit = min(max_tokens_detected // 4, 8192)
                    max_tokens_input = self.query_one("#max-tokens-input", Input)
                    max_tokens_input.value = str(generation_limit)
                    log(f"[SETTINGS] Auto-filled max_tokens: {generation_limit} (from context: {max_tokens_detected})")
                    status.update(f"🟢 Auto-filled: {first_model} (max tokens: {generation_limit})")
                else:
                    log("[SETTINGS] No max tokens info found in model metadata")
                    status.update(f"🟢 Found {len(models_data)} model(s), auto-filled: {first_model}")

                status.remove_class("status-checking", "status-error")
                status.add_class("status-success")
            else:
                status.update("🔴 No models found on this server")
                status.remove_class("status-checking", "status-success")
                status.add_class("status-error")

        except Exception as e:
            log(f"[SETTINGS] Auto-fill error: {e}")
            status.update(f"🔴 Error: {str(e)}")
            status.remove_class("status-checking", "status-success")
            status.add_class("status-error")

    async def _test_connection(self) -> None:
        """Test the VLLM connection with current values."""
        log("[SETTINGS] Test connection button clicked")
        status = self.query_one("#connection-status", Static)
        status.update("🟡 Testing connection...")
        status.remove_class("status-success", "status-error")
        status.add_class("status-checking")

        try:
            # Get current input values
            url = self.query_one("#url-input", Input).value
            api_key = self.query_one("#api-key-input", Input).value or None
            log(f"[SETTINGS] Testing connection to: {url}")

            # Import here to avoid circular dependency
            from cliide.ai.vllm_client import VLLMClient
            from cliide.core.config import Config, VLLMConfig

            # Create temporary client with new settings
            temp_config = Config()
            temp_config.vllm.base_url = url
            temp_config.vllm.api_key = api_key
            client = VLLMClient(temp_config)

            # Test connection
            log("[SETTINGS] Checking connection...")
            connected = await client.check_connection()
            log(f"[SETTINGS] Connection result: {connected}")

            if connected:
                status.update("🟢 Connection successful!")
                status.remove_class("status-checking", "status-error")
                status.add_class("status-success")
                log("[SETTINGS] Connection successful")
            else:
                status.update("🔴 Connection failed - server not reachable")
                status.remove_class("status-checking", "status-success")
                status.add_class("status-error")
                log("[SETTINGS] Connection failed")

        except Exception as e:
            log(f"[SETTINGS] Connection error: {e}")
            status.update(f"🔴 Connection error: {str(e)}")
            status.remove_class("status-checking", "status-success")
            status.add_class("status-error")

    async def _save_config(self) -> None:
        """Save the configuration."""
        log("[SETTINGS] Save button clicked")
        status = self.query_one("#connection-status", Static)
        status.update("💾 Saving configuration...")
        status.remove_class("status-success", "status-error")
        status.add_class("status-checking")

        try:
            # Get input values
            url = self.query_one("#url-input", Input).value
            api_key = self.query_one("#api-key-input", Input).value or None
            model = self.query_one("#model-input", Input).value
            temperature_str = self.query_one("#temperature-input", Input).value
            max_tokens_str = self.query_one("#max-tokens-input", Input).value
            log(f"[SETTINGS] Saving config - URL: {url}, Model: {model}, Temp: {temperature_str}, MaxTokens: {max_tokens_str}")

            # Validate and convert numeric values
            try:
                temperature = float(temperature_str)
                if not 0.0 <= temperature <= 2.0:
                    raise ValueError("Temperature must be between 0.0 and 2.0")
            except ValueError as e:
                status = self.query_one("#connection-status", Static)
                status.update(f"🔴 Invalid temperature: {e}")
                status.remove_class("status-checking", "status-success")
                status.add_class("status-error")
                return

            try:
                max_tokens = int(max_tokens_str)
                if max_tokens < 1:
                    raise ValueError("Max tokens must be at least 1")
            except ValueError as e:
                status = self.query_one("#connection-status", Static)
                status.update(f"🔴 Invalid max tokens: {e}")
                status.remove_class("status-checking", "status-success")
                status.add_class("status-error")
                return

            # Update config
            log("[SETTINGS] Calling update_vllm_config...")
            update_vllm_config(
                base_url=url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            log("[SETTINGS] Config updated successfully")

            # Notify that config was saved
            log("[SETTINGS] Posting ConfigSaved message")
            self.post_message(self.ConfigSaved())

            # Close the settings screen
            log("[SETTINGS] Dismissing settings screen")
            self.dismiss(True)

        except IOError as e:
            log(f"[SETTINGS] IO Error saving config: {e}")
            status = self.query_one("#connection-status", Static)
            status.update(f"🔴 Save failed: {str(e)}")
            status.remove_class("status-checking", "status-success")
            status.add_class("status-error")
        except Exception as e:
            log(f"[SETTINGS] Unexpected error saving config: {e}")
            status = self.query_one("#connection-status", Static)
            status.update(f"🔴 Unexpected error: {str(e)}")
            status.remove_class("status-checking", "status-success")
            status.add_class("status-error")

    def on_key(self, event) -> None:
        """Handle key events."""
        if hasattr(event, "key") and event.key == "escape":
            self.dismiss(False)
            if hasattr(event, "stop"):
                event.stop()
