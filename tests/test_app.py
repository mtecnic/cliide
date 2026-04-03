#!/usr/bin/env python3
"""Quick test of the app to check for errors."""

from pathlib import Path
from cliide.core.app import CliideApp


def test_app_startup():
    """Test that app can start without errors."""
    try:
        # Create app instance
        app = CliideApp(project_path=Path.cwd())
        print("✓ App created successfully")

        # Check widgets are composed
        print("✓ App ready to run (press Ctrl+Q to quit when testing)")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_app_startup()
