# cliide 🚀

**AI-first CLI IDE powered by local VLLM models**

cliide is a terminal-based IDE that combines traditional code editing with AI assistance through locally-run VLLM models. It features a modern TUI built with Textual, LSP integration for intelligent code completion, and seamless AI chat for code explanation, refactoring, and more.

## Features

- 🎨 **Modern TUI Interface** - Clean 3-panel layout with file tree, editor, and AI chat
- 🤖 **Local AI Integration** - Powered by VLLM for privacy and performance
- 📝 **Smart Editor** - Syntax highlighting, multiple file support, vim-like keybindings
- 🔧 **LSP Support** - Traditional IDE features (completion, diagnostics, go-to-definition)
- 💬 **AI Chat Panel** - Ask questions, explain code, get refactoring suggestions
- ⚡ **Fast & Lightweight** - Terminal-based for maximum efficiency
- 🎯 **Code Actions** - AI-powered refactoring, bug fixes, and code improvements
- 🎨 **Customizable** - Themes, keybindings, and configuration via TOML

## Installation

### Prerequisites

- Python 3.10 or higher
- A running VLLM server (see [VLLM Setup](#vllm-setup))

### Install via pip

```bash
pip install cliide
```

### Install from source

```bash
git clone https://github.com/mtecnic/cliide.git
cd cliide
pip install -e .
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/mtecnic/cliide.git
cd cliide

# Install with dev dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

## VLLM Setup

cliide requires a VLLM server running locally or accessible via network. Here's how to set it up:

### Option 1: Quick Start with Docker

```bash
docker run --gpus all \
    -p 8000:8000 \
    vllm/vllm-openai:latest \
    --model deepseek-ai/deepseek-coder-33b-instruct
```

### Option 2: Install VLLM Locally

```bash
# Install VLLM
pip install vllm

# Start VLLM server
python -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-coder-33b-instruct \
    --port 8000
```

### Recommended Models

- **deepseek-coder-33b-instruct** - Excellent for code tasks
- **codellama-34b-instruct** - Good all-around performance
- **mistral-7b-instruct** - Lightweight option
- **starcoder2-15b** - Fast code completion

## Usage

### Basic Usage

```bash
# Open current directory
cliide

# Open specific project
cliide /path/to/project

# Use custom config
cliide --config ~/.config/cliide/my-config.toml
```

### Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+Q` | Quit application |
| `Ctrl+P` | Open command palette |
| `Ctrl+S` | Save current file |
| `Ctrl+K` | Toggle AI chat panel |
| `Ctrl+E` | Explain selected code |
| `Ctrl+B` | Toggle file tree |
| `Ctrl+F` | Find in file |

### AI Commands

In the chat panel, you can use natural language or these shortcuts:

- `/explain` - Explain selected code
- `/refactor` - Get refactoring suggestions
- `/fix` - Suggest bug fixes
- `/test` - Generate tests for selected code
- `/doc` - Generate documentation

## Configuration

Create a configuration file at `~/.config/cliide/config.toml`:

```toml
[vllm]
base_url = "http://localhost:8000/v1"
model = "deepseek-coder-33b-instruct"
temperature = 0.2
max_tokens = 2048
streaming = true

[editor]
theme = "monokai"
tab_size = 4
line_numbers = true
auto_save = false
word_wrap = false

[lsp]
enabled = true

[lsp.servers]
python = "pyright-langserver --stdio"
rust = "rust-analyzer"
javascript = "typescript-language-server --stdio"
typescript = "typescript-language-server --stdio"
go = "gopls"

[keybindings]
command_palette = "ctrl+p"
ai_chat = "ctrl+k"
explain_code = "ctrl+e"
save_file = "ctrl+s"
quit = "ctrl+q"

[ui]
show_file_tree = true
show_chat_panel = true
file_tree_width = 30
chat_panel_width = 40
```

### Environment Variables

You can also configure cliide using environment variables:

```bash
export CLIIDE_VLLM__BASE_URL="http://localhost:8000/v1"
export CLIIDE_VLLM__MODEL="deepseek-coder-33b-instruct"
export CLIIDE_EDITOR__THEME="monokai"
```

## LSP Server Setup

For full IDE features, install language servers:

```bash
# Python & TypeScript (most common)
npm install -g pyright typescript-language-server typescript

# Rust
rustup component add rust-analyzer

# Go
go install golang.org/x/tools/gopls@latest
```

## Architecture

```
cliide/
├── core/           # Application core (app, config, events)
├── ui/             # UI widgets (editor, chat, file tree, etc.)
├── ai/             # AI integration (VLLM client, prompts)
├── lsp/            # LSP client and providers
├── editor/         # Editor logic (buffer, cursor, syntax)
└── utils/          # Utilities (file watcher, keybindings)
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy cliide
```

### Live Development

Textual provides a dev mode with live reloading:

```bash
textual run --dev cliide/core/app.py
```

## Roadmap

### Phase 1: Foundation ✅
- [x] Basic TUI with Textual
- [x] File tree and editor
- [x] Configuration system
- [x] Command palette

### Phase 2: AI Integration (Current)
- [ ] VLLM client implementation
- [ ] Chat interface with streaming
- [ ] Basic AI commands (explain, refactor, fix)
- [ ] Context building

### Phase 3: LSP Integration
- [ ] LSP client setup
- [ ] Diagnostics display
- [ ] Code completion
- [ ] Go-to-definition

### Phase 4: Advanced Features
- [ ] Multi-file refactoring
- [ ] Diff view for AI suggestions
- [ ] Split panes
- [ ] Plugin system

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Textual](https://github.com/Textualize/textual) - Amazing TUI framework
- [VLLM](https://github.com/vllm-project/vllm) - Fast LLM inference
- [pygls](https://github.com/openlawlibrary/pygls) - Python LSP implementation
- [tree-sitter](https://tree-sitter.github.io/) - Syntax parsing

## Support

- 📖 [Documentation](https://github.com/mtecnic/cliide/docs)
- 🐛 [Issue Tracker](https://github.com/mtecnic/cliide/issues)
- 💬 [Discussions](https://github.com/mtecnic/cliide/discussions)

---

Made with ❤️ by the cliide contributors
