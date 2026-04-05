"""Test runner tool for various testing frameworks."""

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles

from cliide.ai.tools.base import Tool, ToolCategory, ToolResult, RiskLevel


class RunTestsTool(Tool):
    """Run tests using auto-detected or specified test framework."""

    # Test framework detection patterns
    FRAMEWORK_PATTERNS = {
        "pytest": {
            "files": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
            "command": "pytest",
            "args": ["-v", "--tb=short"],
        },
        "jest": {
            "files": ["jest.config.js", "jest.config.ts", "jest.config.json"],
            "package_json_key": "jest",
            "command": "npx",
            "args": ["jest", "--verbose"],
        },
        "vitest": {
            "files": ["vitest.config.ts", "vitest.config.js"],
            "command": "npx",
            "args": ["vitest", "run"],
        },
        "cargo": {
            "files": ["Cargo.toml"],
            "command": "cargo",
            "args": ["test"],
        },
        "go": {
            "files": ["go.mod"],
            "command": "go",
            "args": ["test", "-v", "./..."],
        },
        "npm": {
            "files": ["package.json"],
            "command": "npm",
            "args": ["test"],
        },
    }

    def __init__(
        self,
        workspace_root: str | Path,
        timeout: int = 120,
        max_output_size: int = 100000,
    ):
        """Initialize the test runner tool.

        Args:
            workspace_root: Root directory of the project
            timeout: Test timeout in seconds
            max_output_size: Maximum output size in characters
        """
        super().__init__()
        self._category = ToolCategory.COMMAND
        self._requires_confirmation = True  # Tests may have side effects
        self._risk_level = RiskLevel.HIGH  # Running tests can have side effects
        self.workspace_root = Path(workspace_root).resolve()
        self.timeout = timeout
        self.max_output_size = max_output_size

    @property
    def name(self) -> str:
        return "run_tests"

    @property
    def description(self) -> str:
        return """Run tests in the project. Auto-detects the testing framework (pytest, jest, vitest, cargo test, go test, npm test).
You can optionally specify a specific test file or pattern to run."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "framework": {
                    "type": "string",
                    "description": "Test framework to use (pytest, jest, vitest, cargo, go, npm). Auto-detected if not specified.",
                    "enum": ["pytest", "jest", "vitest", "cargo", "go", "npm"]
                },
                "pattern": {
                    "type": "string",
                    "description": "Test file pattern or specific test file to run"
                },
                "extra_args": {
                    "type": "string",
                    "description": "Additional arguments to pass to the test command"
                }
            },
            "required": []
        }

    async def _detect_framework(self) -> str | None:
        """Auto-detect the testing framework.

        Returns:
            Framework name or None if not detected
        """
        for framework, config in self.FRAMEWORK_PATTERNS.items():
            for file_pattern in config.get("files", []):
                if (self.workspace_root / file_pattern).exists():
                    # Special handling for package.json
                    if framework == "npm" and file_pattern == "package.json":
                        # Check if it has a test script
                        try:
                            async with aiofiles.open(self.workspace_root / "package.json") as f:
                                content = await f.read()
                                pkg = json.loads(content)
                                if "test" in pkg.get("scripts", {}):
                                    return framework
                        except (json.JSONDecodeError, FileNotFoundError):
                            continue
                    else:
                        return framework

        return None

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Run the tests.

        Args:
            args: Dictionary with optional framework, pattern, extra_args

        Returns:
            ToolResult with test output
        """
        framework = args.get("framework")
        pattern = args.get("pattern", "")
        extra_args = args.get("extra_args", "")

        # Auto-detect framework if not specified
        if not framework:
            framework = await self._detect_framework()
            if not framework:
                return ToolResult(
                    success=False,
                    error="Could not detect test framework. Please specify one of: pytest, jest, vitest, cargo, go, npm"
                )

        # Get framework config
        config = self.FRAMEWORK_PATTERNS.get(framework)
        if not config:
            return ToolResult(
                success=False,
                error=f"Unknown framework: {framework}"
            )

        # Build command
        command = config["command"]
        cmd_args = list(config["args"])

        # Add pattern if specified
        if pattern:
            if framework == "pytest":
                cmd_args.append(pattern)
            elif framework in ["jest", "vitest"]:
                cmd_args.extend(["--", pattern])
            elif framework == "cargo":
                cmd_args.append(pattern)
            elif framework == "go":
                cmd_args[-1] = pattern  # Replace ./...

        # Add extra args
        if extra_args:
            cmd_args.extend(extra_args.split())

        # Run command
        full_cmd = [command] + cmd_args

        try:
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                cwd=str(self.workspace_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    error=f"Tests timed out after {self.timeout} seconds"
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Truncate if needed
            combined = f"{stdout_str}\n{stderr_str}".strip()
            if len(combined) > self.max_output_size:
                combined = combined[:self.max_output_size] + f"\n... (truncated, {len(combined)} total chars)"

            exit_code = process.returncode or 0
            success = exit_code == 0

            # Parse results if possible
            summary = self._parse_test_summary(framework, stdout_str, stderr_str, exit_code)

            return ToolResult(
                success=success,
                data={
                    "output": combined,
                    "exit_code": exit_code,
                    "framework": framework,
                },
                summary=summary,
                error=None if success else f"Tests failed with exit code {exit_code}",
                metadata={
                    "framework": framework,
                    "command": " ".join(full_cmd),
                    "exit_code": exit_code,
                }
            )

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"Test command not found: {command}. Make sure {framework} is installed."
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to run tests: {str(e)}"
            )

    def _parse_test_summary(
        self,
        framework: str,
        stdout: str,
        stderr: str,
        exit_code: int
    ) -> str:
        """Parse test output to extract summary.

        Args:
            framework: Test framework name
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code

        Returns:
            Human-readable summary
        """
        output = f"{stdout}\n{stderr}"

        if framework == "pytest":
            # Look for pytest summary line like "5 passed, 2 failed in 1.23s"
            for line in reversed(output.split("\n")):
                if "passed" in line or "failed" in line or "error" in line:
                    return f"pytest: {line.strip()}"

        elif framework in ["jest", "vitest"]:
            # Look for Jest/Vitest summary
            for line in reversed(output.split("\n")):
                if "Tests:" in line or "Test Suites:" in line:
                    return line.strip()

        elif framework == "cargo":
            # Look for Cargo test summary
            for line in reversed(output.split("\n")):
                if "test result:" in line:
                    return line.strip()

        elif framework == "go":
            # Look for Go test summary
            if "PASS" in output:
                return "go test: PASS"
            elif "FAIL" in output:
                return "go test: FAIL"

        # Default summary
        status = "PASSED" if exit_code == 0 else "FAILED"
        return f"Tests {status} (exit code: {exit_code})\n\n{output[:2000]}"
