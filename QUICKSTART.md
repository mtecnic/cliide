# Quick Start Guide

Get up and running with cliide in minutes!

## 1. Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd cliide

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install cliide
pip install -e .
```

## 2. Set Up VLLM (Choose One Option)

### Option A: Docker (Easiest)

```bash
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model deepseek-ai/deepseek-coder-33b-instruct
```

### Option B: Local Installation

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/deepseek-coder-33b-instruct \
  --port 8000
```

### Option C: Use OpenAI API (for testing)

Create `.cliide.toml` in your project:

```toml
[vllm]
base_url = "https://api.openai.com/v1"
model = "gpt-4"
# Set OPENAI_API_KEY environment variable
```

## 3. Run cliide

```bash
# Open current directory
cliide

# Open specific project
cliide /path/to/your/project

# Use custom config
cliide --config custom-config.toml
```

## 4. Basic Usage

### Navigation
- **File Tree**: Left panel shows your project files
- **Editor**: Center panel for editing
- **AI Chat**: Right panel for AI assistance

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+Q` | Quit |
| `Ctrl+P` | Command palette |
| `Ctrl+S` | Save file |
| `Ctrl+K` | Toggle AI chat |
| `Ctrl+E` | Explain selected code |
| `Ctrl+B` | Toggle file tree |

### AI Features (Coming Soon)
1. Select code in the editor
2. Press `Ctrl+E` to explain
3. Type in chat for general questions
4. Use `/refactor`, `/fix`, `/test` commands

## 5. Configuration

Create `~/.config/cliide/config.toml`:

```toml
[vllm]
base_url = "http://localhost:8000/v1"
model = "deepseek-coder-33b-instruct"

[editor]
theme = "monokai"
tab_size = 4

[lsp]
enabled = true
```

See `config.example.toml` for all options.

## 6. Install Language Servers (Optional)

For enhanced code intelligence:

```bash
# Python
npm install -g pyright

# JavaScript/TypeScript
npm install -g typescript-language-server typescript

# Rust
rustup component add rust-analyzer

# Go
go install golang.org/x/tools/gopls@latest
```

## Troubleshooting

### cliide command not found
Make sure you activated the virtual environment:
```bash
source venv/bin/activate
```

### VLLM connection errors
1. Check VLLM server is running: `curl http://localhost:8000/health`
2. Verify config in `.cliide.toml` or `~/.config/cliide/config.toml`

### Import errors
Reinstall dependencies:
```bash
pip install -e . --force-reinstall
```

## Next Steps

- [ ] Implement VLLM client (Phase 2)
- [ ] Add streaming chat responses
- [ ] Integrate LSP for code intelligence
- [ ] Build AI-powered code actions

## Get Help

- GitHub Issues: Report bugs and request features
- Documentation: Full docs in README.md
- Community: Join discussions on GitHub

Happy coding! 🚀
