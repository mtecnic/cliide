# Project Summary: cliide – AI-First CLI IDE

## 1. Project Overview

**cliide** is an AI-first, terminal-based Integrated Development Environment (IDE) built as a modern Text User Interface (TUI) application. It combines traditional code editing capabilities with AI assistance powered by locally-run VLLM models, enabling developers to work with AI features like code explanation, refactoring, and chat without relying on external cloud services.

The project is in **Alpha** stage (v0.1.0) and is designed for developers who prefer working in the terminal while leveraging local AI capabilities for enhanced productivity.

## 2. Key Components (Main Directories/Modules)

### Core Application Structure
- **`cliide/`** – Main application source code
  - `core/` – Core application logic (entry point: `app.py` with `CliideApp` class)
  - `ai/` – AI integration functionality (chat, code analysis, VLLM communication)
  - `editor/` – Code editor components and text handling
  - `lsp/` – Language Server Protocol integration for intelligent code features
  - `ui/` – User interface components (panels, widgets, layouts)
  - `themes/` – UI theme definitions
  - `utils/` – Utility functions and helpers

### Supporting Directories
- **`tests/`** – Test suite for application components
- **`.cliide/`** – Application state and checkpoints
- **`venv/`** – Python virtual environment

### Documentation Files (in root)
- `README.md`, `PROJECT_SUMMARY.md`, `QUICKSTART.md`, `DEVELOPMENT.md`, `IMPLEMENTATION.md`
- Feature-specific docs: `AI_FEATURES.md`, `CHAT_USAGE.md`, `TOOLS_README.md`
- Phase reports: `PHASE2_COMPLETE.md`, `PHASE2_SUMMARY.txt`

## 3. Tech Stack

### Core Frameworks & Libraries
| Category | Technology |
|----------|------------|
| **UI Framework** | Textual (TUI framework for Python) |
| **AI Integration** | VLLM (local LLM inference), OpenAI client library |
| **LSP Support** | pygls (Python LSP implementation), lsprotocol |
| **Code Analysis** | tree-sitter (incremental parsing), tree-sitter-languages |
| **Configuration** | Pydantic, Pydantic-Settings, TOML |
| **CLI Framework** | Click |
| **Terminal Formatting** | Rich |
| **Async I/O** | aiofiles, watchdog |

### Development Tools
- **Build System**: Hatchling
- **Testing**: pytest, pytest-asyncio
- **Quality Tools**: mypy (type checking), ruff (linting), pre-commit
- **Python Version**: >=3.10 (virtual environment uses 3.12.3)

## 4. Notable Features

### AI Capabilities
- **Local AI Processing**: Powered by VLLM with models like deepseek-coder-33b-instruct
- **AI Chat Interface**: Context-aware conversation for code explanation, refactoring, and generation
- **Code Analysis**: Intelligent code understanding and transformation

### Development Experience
- **3-Panel TUI Layout**: File tree, editor, and AI chat panels
- **LSP Integration**: Intelligent code completion, diagnostics, and navigation for multiple languages (Python, Rust, JavaScript, Go, Java, C/C++)
- **Modern Editor Features**: Line numbers, tab support, find/replace, diff view, problems panel

### Configuration & Customization
- **Configurable via TOML**: Settings for VLLM, editor preferences, LSP servers, keybindings, and UI layout
- **Theme Support**: Built-in themes (monokai, dracula) with customization options
- **Extensible Tools**: Dangerous operation confirmation, workspace restrictions, audit logging

### Developer Tooling
- **Command Palette**: Quick access to actions (Ctrl+P)
- **Keybindings**: Customizable shortcuts for common operations
- **Debugging Support**: Comprehensive logging and troubleshooting tools

The project demonstrates a well-structured, modular architecture with clear separation of concerns between UI, core logic, AI integration, and language server support, making it maintainable and extensible for future enhancements.
