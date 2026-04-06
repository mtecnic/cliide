"""Lightweight entry point with immediate startup spinner.

This module shows a spinner IMMEDIATELY before importing heavy modules.
The actual app code is imported INSIDE the spinner context.
"""

import sys
from pathlib import Path


def main() -> None:
    """Main entry point with immediate spinner."""
    # Parse args BEFORE showing spinner (need to handle --help, --version first)
    # These are lightweight operations that don't need the spinner
    args = sys.argv[1:]

    # Handle --version quickly
    if "--version" in args or "-V" in args:
        print("cliide 0.1.0")
        return

    # Handle --help quickly (just show basic help, full help requires click)
    if "--help" in args or "-h" in args:
        print("cliide - AI-first CLI IDE powered by local VLLM models")
        print()
        print("Usage: cliide [OPTIONS] [PATH]")
        print()
        print("Options:")
        print("  -c, --config PATH    Path to config file")
        print("  --oapi-url TEXT      Set OpenAI-compatible API URL and save to config")
        print("  --model TEXT         Set model name and save to config")
        print("  --version            Show version and exit")
        print("  --help               Show this message and exit")
        print()
        print("PATH: Optional path to project directory (defaults to current directory)")
        return

    # Handle --oapi-url (config update, no spinner needed)
    if "--oapi-url" in args:
        try:
            idx = args.index("--oapi-url")
            url = args[idx + 1]
            from cliide.core.config import update_vllm_url
            update_vllm_url(url)
            print(f"Updated VLLM URL to: {url}")
            return
        except (IndexError, ValueError):
            print("Error: --oapi-url requires a URL argument")
            sys.exit(1)

    # Handle --model (config update, no spinner needed)
    if "--model" in args:
        try:
            idx = args.index("--model")
            model = args[idx + 1]
            from cliide.core.config import update_vllm_model
            update_vllm_model(model)
            print(f"Updated model to: {model}")
            return
        except (IndexError, ValueError):
            print("Error: --model requires a model name argument")
            sys.exit(1)

    # Parse remaining args for path and config
    project_path: Path | None = None
    config_path: Path | None = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-c", "--config"):
            if i + 1 < len(args):
                config_path = Path(args[i + 1])
                if not config_path.exists():
                    print(f"Error: Config file not found: {config_path}")
                    sys.exit(1)
                i += 2
            else:
                print("Error: --config requires a path argument")
                sys.exit(1)
        elif not arg.startswith("-"):
            # Positional argument = project path
            project_path = Path(arg)
            if not project_path.exists():
                print(f"Error: Path not found: {project_path}")
                sys.exit(1)
            i += 1
        else:
            i += 1

    # NOW show spinner and do heavy imports
    from rich.console import Console
    from rich.live import Live
    from rich.spinner import Spinner

    console = Console()

    with Live(
        Spinner("dots", text=" Starting cliide...", style="cyan"),
        console=console,
        refresh_per_second=10,
        transient=True,
    ):
        # Heavy imports happen HERE, inside the spinner
        from cliide.core.app import CliideApp
        from cliide.core.config import Config, set_config

        # Load config if specified
        if config_path:
            cfg = Config.load_from_file(config_path)
            set_config(cfg)

        # Create app (this also does initialization work)
        app = CliideApp(project_path=project_path)

    # Spinner done, run the app
    app.run()


if __name__ == "__main__":
    main()
