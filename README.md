<p align="center">
  <img src="https://raw.githubusercontent.com/mtecnic/cliide/main/assets/logo.png" alt="cliide logo" width="200"/>
</p>

<h1 align="center">cliide</h1>

<p align="center">
  <strong>The AI-Native Terminal IDE</strong><br>
  <em>Code with AI agents, not against them</em>
</p>

<p align="center">
  <a href="https://github.com/mtecnic/cliide/stargazers"><img src="https://img.shields.io/github/stars/mtecnic/cliide?style=for-the-badge&logo=github&color=yellow" alt="Stars"></a>
  <a href="https://github.com/mtecnic/cliide/network/members"><img src="https://img.shields.io/github/forks/mtecnic/cliide?style=for-the-badge&logo=github&color=blue" alt="Forks"></a>
  <a href="https://github.com/mtecnic/cliide/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mtecnic/cliide?style=for-the-badge&color=green" alt="License"></a>
  <a href="https://pypi.org/project/cliide/"><img src="https://img.shields.io/pypi/v/cliide?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-why-cliide">Why cliide?</a> •
  <a href="#-documentation">Docs</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

<p align="center">
  <img src="https://raw.githubusercontent.com/mtecnic/cliide/main/assets/demo.gif" alt="cliide demo" width="800"/>
</p>

## ✨ What is cliide?

**cliide** (CLI IDE) is a **terminal-based AI-first development environment** that runs entirely in your terminal. Unlike traditional IDEs with AI bolted on, cliide is built from the ground up with AI agents at its core.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 📁 Files    │ 📝 Editor                        │ 💬 AI Chat              │
│             │                                  │                         │
│ ▼ src/      │  def calculate_tax(income):      │ You: Optimize this      │
│   main.py   │      if income < 50000:          │ function for large      │
│   utils.py  │          return income * 0.1     │ datasets                │
│   config.py │      else:                       │                         │
│             │          return income * 0.2     │ AI: I'll refactor this  │
│ ▼ tests/    │                                  │ to use numpy vectorized │
│   test_m... │  [Proposed changes - Y/N]        │ operations...           │
│             │                                  │                         │
│ ─────────── │                                  │ 🔧 write_file(utils.py) │
│ 📋 Tasks    │                                  │    ⏳ Executing...      │
│ ▶ Step 1... │                                  │                         │
│ ○ Step 2... │                                  │                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🎯 Why cliide?

| Feature | VS Code + Copilot | Cursor | **cliide** |
|---------|------------------|--------|------------|
| **Runs in terminal** | ❌ | ❌ | ✅ |
| **Uses local models** | ❌ | ❌ | ✅ |
| **No cloud dependency** | ❌ | ❌ | ✅ |
| **AI can edit files** | ❌ | ✅ | ✅ |
| **Inline diff review** | ❌ | ✅ | ✅ |
| **Sub-agent tasks** | ❌ | ❌ | ✅ |
| **100% open source** | ❌ | ❌ | ✅ |
| **Resource usage** | Heavy | Heavy | **Lightweight** |
| **SSH-friendly** | ❌ | ❌ | ✅ |

### 🔒 Privacy First

Your code **never leaves your machine**. cliide connects to local VLLM/Ollama instances, meaning:
- No API keys required
- No cloud processing
- No data retention concerns
- Works completely offline

### ⚡ Built for Speed

- **Terminal-native**: No Electron, no browser, no bloat
- **Instant startup**: Ready in milliseconds
- **Low memory**: Runs on modest hardware
- **SSH-ready**: Full functionality over remote connections

## 🚀 Features

### 🤖 AI-First Development
- **Inline code changes**: AI proposes edits directly in the editor with diff highlighting
- **Accept/Reject flow**: Review changes with `Y`/`N` keys before applying
- **Multi-step planning**: AI breaks down complex tasks and shows progress
- **Tool execution**: AI can read files, run commands, and make changes

### 📝 Modern Editor
- **Syntax highlighting** for 30+ languages
- **LSP integration**: Completions, diagnostics, go-to-definition
- **Multiple buffers**: Work on several files simultaneously
- **Vim-style keybindings**: Feel right at home

### 🎨 Sleek TUI
- **Resizable panels**: Drag to resize file tree, editor, and chat
- **Task panel**: See AI planning steps and tool executions
- **Approval queue**: Review AI actions before they execute
- **Rich markdown**: AI responses render beautifully

### 🔧 Developer Experience
- **Command palette**: Quick access to all commands (`Ctrl+P`)
- **File tree**: Navigate projects with ease
- **Find & replace**: Search across files
- **Git integration**: Status indicators in file tree

## 📦 Quick Start

### Prerequisites
- Python 3.10+
- A local LLM server (VLLM, Ollama, or OpenAI-compatible)

### Install

```bash
pip install cliide
```

### Run

```bash
# Open current directory
cliide

# Open a specific project
cliide ~/projects/my-app
```

### Connect to Your LLM

```bash
# Using Ollama (easiest)
ollama serve
ollama run deepseek-coder:33b

# Using VLLM
python -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-coder-33b-instruct
```

Configure in `~/.config/cliide/config.toml`:

```toml
[vllm]
base_url = "http://localhost:11434/v1"  # Ollama
# base_url = "http://localhost:8000/v1"  # VLLM
model = "deepseek-coder:33b"
```

## ⌨️ Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+P` | Command palette |
| `Ctrl+K` | Focus AI chat |
| `Ctrl+S` | Save file |
| `Ctrl+B` | Toggle file tree |
| `Ctrl+E` | Explain selected code |
| `Y` / `N` | Accept/Reject AI changes |
| `Ctrl+Q` | Quit |

## 🧠 AI Commands

Chat naturally or use shortcuts:

```
/explain    - Explain selected code
/refactor   - Suggest improvements
/fix        - Find and fix bugs
/test       - Generate unit tests
/doc        - Generate documentation
```

## 🏗️ Architecture

```
cliide/
├── ai/             # AI agents, prompts, event bus
├── core/           # App core, config, session management
├── ui/             # Textual widgets (editor, chat, panels)
├── lsp/            # Language Server Protocol client
└── editor/         # Buffer management, syntax highlighting
```

## 🤝 Contributing

We love contributions! Whether it's:

- 🐛 Bug reports
- 💡 Feature suggestions
- 📖 Documentation improvements
- 🔧 Code contributions

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/mtecnic/cliide.git
cd cliide
pip install -e ".[dev]"

# Run tests
pytest

# Run with live reload
textual run --dev cliide/core/app.py
```

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🌟 Star History

<p align="center">
  <a href="https://star-history.com/#mtecnic/cliide&Date">
    <img src="https://api.star-history.com/svg?repos=mtecnic/cliide&type=Date" alt="Star History Chart" width="600">
  </a>
</p>

## 💖 Acknowledgments

Built with amazing open source projects:

- [Textual](https://github.com/Textualize/textual) - TUI framework
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal formatting
- [VLLM](https://github.com/vllm-project/vllm) - Fast LLM inference
- [Ollama](https://github.com/ollama/ollama) - Easy local LLMs

---

<p align="center">
  <strong>If cliide helps you code faster, give it a ⭐!</strong>
</p>

<p align="center">
  <a href="https://github.com/mtecnic/cliide">GitHub</a> •
  <a href="https://github.com/mtecnic/cliide/issues">Issues</a> •
  <a href="https://github.com/mtecnic/cliide/discussions">Discussions</a>
</p>
