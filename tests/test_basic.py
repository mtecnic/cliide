#!/usr/bin/env python3
"""Basic import and structure test for cliide."""

import sys
from pathlib import Path


def test_imports():
    """Test that all modules can be imported."""
    try:
        # Core
        from cliide.core import app, config, events
        print("✓ Core modules imported successfully")

        # UI
        from cliide.ui import chat, command_palette, editor, file_tree, statusbar
        print("✓ UI modules imported successfully")

        # Config
        from cliide.core.config import Config, get_config
        print("✓ Configuration module imported successfully")

        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """Test configuration loading."""
    try:
        from cliide.core.config import Config

        # Test default config
        config = Config()
        assert config.vllm.base_url == "http://localhost:8000/v1"
        assert config.editor.tab_size == 4
        assert config.lsp.enabled is True
        print("✓ Configuration system working")

        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_app_creation():
    """Test that the app can be created."""
    try:
        from cliide.core.app import CliideApp

        # Create app instance (don't run it)
        app = CliideApp(project_path=Path.cwd())
        assert app.project_path == Path.cwd()
        print("✓ Application instance created successfully")

        return True
    except Exception as e:
        print(f"✗ App creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("Running cliide basic tests...\n")

    tests = [
        test_imports,
        test_config,
        test_app_creation,
    ]

    results = [test() for test in tests]

    print(f"\n{'='*50}")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print(f"{'='*50}")

    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
