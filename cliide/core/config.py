"""Configuration management for cliide."""

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib


class VLLMConfig(BaseModel):
    """VLLM configuration."""

    base_url: str = Field(default="http://localhost:8000/v1", description="VLLM API base URL")
    api_key: str | None = Field(default=None, description="Optional API key for authentication")
    model: str = Field(default="deepseek-coder-33b-instruct", description="Model name")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, ge=1, description="Max tokens")
    streaming: bool = Field(default=True, description="Enable streaming responses")
    timeout: int = Field(default=60, description="Request timeout in seconds")


class EditorConfig(BaseModel):
    """Editor configuration."""

    theme: str = Field(default="monokai", description="Color theme")
    tab_size: int = Field(default=4, ge=1, le=8, description="Tab size")
    line_numbers: bool = Field(default=True, description="Show line numbers")
    auto_save: bool = Field(default=False, description="Auto-save files")
    auto_save_delay: int = Field(default=2, ge=1, description="Auto-save delay in seconds")
    word_wrap: bool = Field(default=False, description="Enable word wrap")
    show_whitespace: bool = Field(default=False, description="Show whitespace characters")


class LSPConfig(BaseModel):
    """LSP server configuration."""

    enabled: bool = Field(default=True, description="Enable LSP")
    servers: dict[str, str] = Field(
        default_factory=lambda: {
            "python": "pyright-langserver --stdio",
            "rust": "rust-analyzer",
            "javascript": "typescript-language-server --stdio",
            "typescript": "typescript-language-server --stdio",
            "go": "gopls",
        },
        description="Language server commands",
    )


class KeybindingsConfig(BaseModel):
    """Keybindings configuration."""

    command_palette: str = Field(default="ctrl+p", description="Command palette")
    ai_chat: str = Field(default="ctrl+k", description="Open AI chat")
    explain_code: str = Field(default="ctrl+e", description="Explain selected code")
    save_file: str = Field(default="ctrl+s", description="Save file")
    quit: str = Field(default="ctrl+q", description="Quit application")
    find: str = Field(default="ctrl+f", description="Find in file")


class UIConfig(BaseModel):
    """UI configuration."""

    show_file_tree: bool = Field(default=True, description="Show file tree")
    show_chat_panel: bool = Field(default=True, description="Show AI chat panel")
    file_tree_width: int = Field(default=30, ge=10, description="File tree width")
    chat_panel_width: int = Field(default=40, ge=20, description="Chat panel width")
    agent_panel_enabled: bool = Field(default=True, description="Show agent status panel")
    agent_panel_width: int = Field(default=35, ge=20, description="Agent panel width in characters")
    chunk_batch_ms: int = Field(default=50, ge=10, le=500, description="Batch text chunks for this many ms")


class ContextConfig(BaseModel):
    """Context management configuration."""

    max_file_tokens: int = Field(default=8000, ge=1000, description="Maximum tokens per file read")
    max_context_tokens: int = Field(default=32000, ge=4000, description="Total context budget for conversations")
    search_context_lines: int = Field(default=5, ge=1, le=20, description="Lines of context before/after search matches")


class ToolsConfig(BaseModel):
    """AI Tools configuration."""

    enabled: bool = Field(default=True, description="Enable AI tool calling")
    confirmation_mode: str = Field(
        default="moderate",
        description="Confirmation mode: 'conservative' (confirm all writes), 'moderate' (auto-approve code writes, confirm shell/git), 'aggressive' (only confirm destructive ops)"
    )
    timeout_seconds: int = Field(default=30, ge=1, description="Timeout for tool operations in seconds")
    max_file_size_mb: float = Field(default=10.0, ge=0.1, description="Maximum file size for read/write operations in MB")
    workspace_only: bool = Field(default=True, description="Restrict file operations to workspace directory only")
    audit_log_enabled: bool = Field(default=True, description="Enable audit logging of tool executions")
    max_iterations: int = Field(default=50, ge=1, le=200, description="Maximum tool-calling iterations per request")
    auto_approve_reads: bool = Field(default=True, description="Auto-approve read-only operations")


class MemoryConfig(BaseModel):
    """Agent memory configuration."""

    enabled: bool = Field(default=True, description="Enable persistent agent memory")
    max_entries: int = Field(default=1000, ge=10, description="Maximum memory entries to store")
    prune_expired_hours: int = Field(default=168, ge=1, description="Hours before pruning expired memories (default 1 week)")
    auto_store_discoveries: bool = Field(default=True, description="Automatically store important discoveries")


class CheckpointConfig(BaseModel):
    """Checkpoint configuration for autonomous mode."""

    enabled: bool = Field(default=True, description="Enable checkpointing in autonomous mode")
    auto_interval: int = Field(default=5, ge=1, description="Auto-checkpoint every N iterations")
    max_checkpoints: int = Field(default=20, ge=1, description="Maximum checkpoints to keep per task")
    max_age_hours: int = Field(default=48, ge=1, description="Maximum age in hours before pruning checkpoints")


class SubAgentConfig(BaseModel):
    """Sub-agent configuration."""

    default_trust_level: str = Field(
        default="read_only",
        description="Default trust level for sub-agents: 'read_only', 'write_safe', 'write_all', 'full'"
    )
    max_concurrent: int = Field(default=10, ge=1, le=20, description="Maximum concurrent sub-agents")
    auto_approve_reads: bool = Field(default=True, description="Auto-approve read operations for sub-agents")
    milestone_interval: int = Field(default=3, ge=1, description="Emit milestone events every N iterations")


class ToolWorkerConfig(BaseModel):
    """Tool worker pool configuration for async tool delegation."""

    enabled: bool = Field(default=True, description="Enable tool worker delegation (tools run in parallel)")
    max_concurrent: int = Field(default=10, ge=1, le=50, description="Maximum parallel tool workers")
    timeout_seconds: int = Field(default=60, ge=1, le=300, description="Per-tool execution timeout in seconds")


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_prefix="CLIIDE_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    vllm: VLLMConfig = Field(default_factory=VLLMConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    lsp: LSPConfig = Field(default_factory=LSPConfig)
    keybindings: KeybindingsConfig = Field(default_factory=KeybindingsConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    checkpoints: CheckpointConfig = Field(default_factory=CheckpointConfig)
    subagent: SubAgentConfig = Field(default_factory=SubAgentConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    tool_worker: ToolWorkerConfig = Field(default_factory=ToolWorkerConfig)

    @classmethod
    def load_from_file(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from a TOML file.

        Args:
            config_path: Path to config file. If None, uses default locations.

        Returns:
            Config instance
        """
        from cliide.utils.logger import log

        try:
            if config_path is None:
                # Try default locations
                config_paths = [
                    Path.cwd() / ".cliide.toml",
                    Path.home() / ".config" / "cliide" / "config.toml",
                ]
                log(f"[CONFIG] Searching for config in default locations...")
                for path in config_paths:
                    log(f"[CONFIG] Checking: {path}")
                    if path.exists():
                        config_path = path
                        log(f"[CONFIG] Found config at: {path}")
                        break

            if config_path and config_path.exists():
                log(f"[CONFIG] Loading config from: {config_path}")
                try:
                    with open(config_path, "rb") as f:
                        data = tomllib.load(f)
                    log(f"[CONFIG] Loaded config data: {data}")
                    config = cls(**data)
                    log(f"[CONFIG] Config loaded - URL: {config.vllm.base_url}, Model: {config.vllm.model}")
                    return config
                except tomllib.TOMLDecodeError as e:
                    log(f"[CONFIG] ERROR: Invalid TOML syntax in {config_path}: {e}")
                    log(f"[CONFIG] Falling back to default config")
                    return cls()
                except PermissionError as e:
                    log(f"[CONFIG] ERROR: Permission denied reading {config_path}: {e}")
                    log(f"[CONFIG] Falling back to default config")
                    return cls()
                except Exception as e:
                    log(f"[CONFIG] ERROR: Failed to load config from {config_path}: {e}")
                    log(f"[CONFIG] Falling back to default config")
                    return cls()

            # Return default config if no file found
            log("[CONFIG] No config file found, using defaults")
            return cls()

        except Exception as e:
            log(f"[CONFIG] ERROR: Unexpected error during config loading: {e}")
            log(f"[CONFIG] Returning default config")
            return cls()

    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to a TOML file.

        Args:
            config_path: Path to save config file

        Raises:
            IOError: If the file cannot be saved
        """
        from cliide.utils.logger import log

        try:
            log(f"[CONFIG] Saving config to: {config_path}")

            # Create directory if it doesn't exist
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                log(f"[CONFIG] Config directory ensured: {config_path.parent}")
            except PermissionError as e:
                log(f"[CONFIG] ERROR: Permission denied creating directory {config_path.parent}: {e}")
                raise IOError(f"Cannot create config directory: Permission denied") from e
            except Exception as e:
                log(f"[CONFIG] ERROR: Failed to create directory {config_path.parent}: {e}")
                raise IOError(f"Cannot create config directory: {e}") from e

            import tomli_w

            # Exclude None values since TOML can't serialize them
            try:
                config_dict = self.model_dump(exclude_none=True)
                log(f"[CONFIG] Config data to save: {config_dict}")
            except Exception as e:
                log(f"[CONFIG] ERROR: Failed to serialize config: {e}")
                raise IOError(f"Cannot serialize config: {e}") from e

            # Write to file
            try:
                with open(config_path, "wb") as f:
                    tomli_w.dump(config_dict, f)
            except PermissionError as e:
                log(f"[CONFIG] ERROR: Permission denied writing to {config_path}: {e}")
                raise IOError(f"Cannot write config file: Permission denied") from e
            except Exception as e:
                log(f"[CONFIG] ERROR: Failed to write config to {config_path}: {e}")
                raise IOError(f"Cannot write config file: {e}") from e

            log(f"[CONFIG] Config saved successfully to {config_path}")

            # Verify the file was written
            if config_path.exists():
                file_size = config_path.stat().st_size
                log(f"[CONFIG] Verified: File exists with size {file_size} bytes")
            else:
                log(f"[CONFIG] WARNING: File does not exist after save!")
                raise IOError(f"Config file not found after save")

        except IOError:
            # Re-raise IOErrors as-is
            raise
        except Exception as e:
            log(f"[CONFIG] ERROR: Unexpected error saving config: {e}")
            raise IOError(f"Unexpected error saving config: {e}") from e


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config.load_from_file()
    return _config


def set_config(config: Config) -> None:
    """Set the global config instance."""
    global _config
    _config = config


def reload_config() -> Config:
    """Force reload configuration from file.

    Returns:
        Freshly loaded config instance
    """
    from cliide.utils.logger import log

    global _config
    log("[CONFIG] Forcing config reload from file...")
    _config = None  # Clear cached config
    config = Config.load_from_file()  # Reload from file
    _config = config
    log(f"[CONFIG] Config reloaded - URL: {config.vllm.base_url}, Model: {config.vllm.model}")
    return config


def get_user_config_path() -> Path:
    """Get the default user config file path.

    Returns:
        Path to user config file
    """
    return Path.home() / ".config" / "cliide" / "config.toml"


def update_vllm_url(url: str) -> None:
    """Update and persist the VLLM API URL.

    Args:
        url: New VLLM API base URL
    """
    # Load current config
    config = get_config()

    # Update URL
    config.vllm.base_url = url

    # Save to user config file
    config_path = get_user_config_path()
    config.save_to_file(config_path)

    print(f"✓ VLLM API URL updated to: {url}")
    print(f"✓ Config saved to: {config_path}")


def update_vllm_model(model: str) -> None:
    """Update and persist the VLLM model name.

    Args:
        model: Model name to use
    """
    # Load current config
    config = get_config()

    # Update model
    config.vllm.model = model

    # Save to user config file
    config_path = get_user_config_path()
    config.save_to_file(config_path)

    print(f"✓ VLLM model updated to: {model}")
    print(f"✓ Config saved to: {config_path}")


def update_vllm_config(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Config:
    """Update and persist VLLM configuration.

    Args:
        base_url: New API base URL
        api_key: New API key (or empty string to clear)
        model: New model name
        temperature: New temperature value
        max_tokens: New max tokens value

    Returns:
        Updated config instance
    """
    from cliide.utils.logger import log

    config = get_config()
    log(f"[CONFIG] update_vllm_config called with: URL={base_url}, Model={model}, Temp={temperature}, MaxTokens={max_tokens}")

    # Update provided values
    if base_url is not None:
        log(f"[CONFIG] Updating base_url from '{config.vllm.base_url}' to '{base_url}'")
        config.vllm.base_url = base_url
    if api_key is not None:
        log(f"[CONFIG] Updating api_key (was: {'set' if config.vllm.api_key else 'empty'}, now: {'set' if api_key else 'empty'})")
        config.vllm.api_key = api_key if api_key else None
    if model is not None:
        log(f"[CONFIG] Updating model from '{config.vllm.model}' to '{model}'")
        config.vllm.model = model
    if temperature is not None:
        log(f"[CONFIG] Updating temperature from {config.vllm.temperature} to {temperature}")
        config.vllm.temperature = temperature
    if max_tokens is not None:
        log(f"[CONFIG] Updating max_tokens from {config.vllm.max_tokens} to {max_tokens}")
        config.vllm.max_tokens = max_tokens

    # Save to user config file
    config_path = get_user_config_path()
    log(f"[CONFIG] Calling save_to_file with path: {config_path}")
    config.save_to_file(config_path)

    # Update global instance
    set_config(config)
    log(f"[CONFIG] Global config updated. Final values - URL: {config.vllm.base_url}, Model: {config.vllm.model}")

    return config
