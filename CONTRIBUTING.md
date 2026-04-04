# Contributing to cliide

Thank you for your interest in contributing to cliide! We welcome contributions of all kinds.

## Ways to Contribute

- **Report bugs**: Open an issue describing the bug
- **Suggest features**: Open an issue with your idea
- **Fix bugs**: Submit a pull request
- **Add features**: Discuss in an issue first, then submit a PR
- **Improve docs**: Documentation improvements are always welcome

## Development Setup

```bash
# Clone the repo
git clone https://github.com/mtecnic/cliide.git
cd cliide

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
pytest
```

## Code Style

We use `ruff` for linting and formatting:

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Type checking
mypy cliide
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

## Code of Conduct

Be respectful and constructive. We're all here to build something great together.

## Questions?

Open a [Discussion](https://github.com/mtecnic/cliide/discussions) or reach out in issues.
