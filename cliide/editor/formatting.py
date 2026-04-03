"""Code formatting utilities."""

import asyncio
from pathlib import Path
from typing import Optional


class CodeFormatter:
    """Format code using language-specific formatters."""

    @staticmethod
    async def format_python(code: str) -> Optional[str]:
        """Format Python code using black.

        Args:
            code: Python code to format

        Returns:
            Formatted code or None if formatting failed
        """
        try:
            # Check if black is installed
            process = await asyncio.create_subprocess_exec(
                "black",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            if process.returncode != 0:
                return None

            # Format code
            process = await asyncio.create_subprocess_exec(
                "black",
                "--quiet",
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate(input=code.encode("utf-8"))

            if process.returncode == 0:
                return stdout.decode("utf-8")

            return None

        except FileNotFoundError:
            return None
        except Exception:
            return None

    @staticmethod
    async def format_javascript(code: str) -> Optional[str]:
        """Format JavaScript/TypeScript code using prettier.

        Args:
            code: JavaScript/TypeScript code to format

        Returns:
            Formatted code or None if formatting failed
        """
        try:
            # Check if prettier is installed
            process = await asyncio.create_subprocess_exec(
                "prettier",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            if process.returncode != 0:
                return None

            # Format code
            process = await asyncio.create_subprocess_exec(
                "prettier",
                "--parser",
                "typescript",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate(input=code.encode("utf-8"))

            if process.returncode == 0:
                return stdout.decode("utf-8")

            return None

        except FileNotFoundError:
            return None
        except Exception:
            return None

    @staticmethod
    async def format_code(code: str, language: Optional[str] = None, file_path: Optional[str] = None) -> Optional[str]:
        """Format code based on language.

        Args:
            code: Code to format
            language: Language name (python, javascript, etc.)
            file_path: File path to detect language

        Returns:
            Formatted code or None if formatting failed
        """
        # Detect language from file extension if not provided
        if not language and file_path:
            ext = Path(file_path).suffix.lower()
            if ext == ".py":
                language = "python"
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                language = "javascript"

        # Format based on language
        if language == "python":
            return await CodeFormatter.format_python(code)
        elif language in ["javascript", "typescript"]:
            return await CodeFormatter.format_javascript(code)

        return None
