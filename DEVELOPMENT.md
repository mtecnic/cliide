# Development Roadmap

## Phase 1: Foundation ✅ COMPLETED

**Status**: All tasks completed and tested

### Completed Tasks
- ✅ Python project setup with pyproject.toml
- ✅ Project directory structure
- ✅ Core application skeleton with Textual
- ✅ 3-panel layout (file tree, editor, chat)
- ✅ Configuration system with Pydantic
- ✅ File tree widget with DirectoryTree
- ✅ Editor widget with TextArea
- ✅ Chat panel widget
- ✅ Command palette modal
- ✅ Status bar widget
- ✅ Event system for app communication
- ✅ README and documentation
- ✅ Development environment setup

### Project Structure
```
cliide/
├── cliide/
│   ├── core/           # Application core
│   │   ├── app.py      # Main Textual app
│   │   ├── config.py   # Configuration management
│   │   └── events.py   # Custom events
│   ├── ui/             # UI widgets
│   │   ├── chat.py     # AI chat panel
│   │   ├── command_palette.py
│   │   ├── editor.py   # Text editor
│   │   ├── file_tree.py
│   │   └── statusbar.py
│   ├── ai/             # AI integration (empty)
│   ├── lsp/            # LSP client (empty)
│   ├── editor/         # Editor logic (empty)
│   └── utils/          # Utilities (empty)
├── tests/
├── pyproject.toml
├── README.md
├── QUICKSTART.md
└── config.example.toml
```

### Key Files
- `cliide/core/app.py` (179 lines) - Main application with layout and keybindings
- `cliide/core/config.py` (166 lines) - Configuration with Pydantic Settings
- `cliide/ui/editor.py` (149 lines) - Text editor with file operations
- `cliide/ui/chat.py` (115 lines) - Chat panel with message display

---

## Phase 2: AI Integration 🚧 IN PROGRESS

**Goal**: Connect to VLLM and implement AI-powered features

### Tasks

#### 2.1 VLLM Client
- [ ] Create `cliide/ai/vllm_client.py`
  - OpenAI-compatible client using `openai` library
  - Async streaming support
  - Connection health monitoring
  - Retry logic and error handling
  - Token usage tracking

- [ ] Add AI status to status bar
  - Show "Connected", "Disconnected", "Processing"
  - Display streaming indicator

#### 2.2 Chat Integration
- [ ] Wire up chat panel to VLLM client
  - Send user messages to AI
  - Stream responses back to chat
  - Handle errors gracefully
  - Show thinking indicator

- [ ] Implement context building
  - Include current file content
  - Include selected code
  - Add project metadata

#### 2.3 Basic AI Commands
- [ ] `/explain` - Explain selected code
  - Create prompt template
  - Parse code context
  - Display explanation in chat

- [ ] `/refactor` - Refactoring suggestions
  - Analyze code structure
  - Generate suggestions
  - Show diff preview

- [ ] `/fix` - Bug fix suggestions
  - Include error messages if available
  - Suggest fixes with explanations

- [ ] `/test` - Generate tests
  - Analyze function/class
  - Generate appropriate tests

#### 2.4 Prompt Management
- [ ] Create `cliide/ai/prompt_manager.py`
  - System prompts for different tasks
  - User prompt templates
  - Context injection
  - Token optimization

### Files to Create
- `cliide/ai/vllm_client.py`
- `cliide/ai/prompt_manager.py`
- `cliide/ai/code_actions.py`
- `cliide/ai/context_builder.py`

### Estimated Time
2-3 weeks

---

## Phase 3: LSP Integration

**Goal**: Add traditional IDE features via Language Server Protocol

### Tasks

#### 3.1 LSP Client Setup
- [ ] Create `cliide/lsp/client.py`
  - LSP client using pygls
  - Handle initialization
  - Manage lifecycle

- [ ] Create `cliide/lsp/manager.py`
  - Auto-detect language servers
  - Launch servers per file type
  - Handle multiple servers

#### 3.2 LSP Features
- [ ] Diagnostics display
  - Show errors/warnings in editor
  - Update status bar
  - Error list view

- [ ] Code completion
  - Trigger on type
  - Show completion menu
  - Insert completion

- [ ] Go to definition
  - Ctrl+Click or `gd` keybinding
  - Open file at location
  - Jump back stack

- [ ] Hover documentation
  - Show docs on hover
  - Format with Rich

#### 3.3 Hybrid AI+LSP
- [ ] Feed LSP diagnostics to AI
  - Include errors in context
  - AI suggests fixes

- [ ] Use LSP symbols for context
  - Find related functions
  - Include in AI prompts

### Files to Create
- `cliide/lsp/client.py`
- `cliide/lsp/manager.py`
- `cliide/lsp/providers.py`

### Estimated Time
3-4 weeks

---

## Phase 4: Advanced Features

**Goal**: Polish UI/UX and add power user features

### Tasks

#### 4.1 Code Actions
- [ ] Diff view for AI suggestions
  - Side-by-side diff
  - Accept/reject changes
  - Partial acceptance

- [ ] Multi-file refactoring
  - AI suggests changes across files
  - Preview all changes
  - Apply atomically

#### 4.2 Editor Enhancements
- [ ] Multiple tabs/buffers
  - Tab bar widget
  - Switch between files
  - Close tabs

- [ ] Split panes
  - Horizontal/vertical splits
  - Multiple editors
  - Sync scrolling

- [ ] Advanced search
  - Fuzzy file finder
  - Project-wide search
  - Regex support

#### 4.3 Syntax Highlighting
- [ ] Integrate tree-sitter
  - Parse code into AST
  - Syntax-based highlighting
  - Language detection

#### 4.4 Customization
- [ ] Theme system
  - Multiple color schemes
  - Custom themes via config
  - Dynamic theme switching

- [ ] Custom keybindings
  - Rebind any action
  - Vim/Emacs modes
  - Keymap editor

### Files to Create
- `cliide/editor/buffer.py`
- `cliide/editor/cursor.py`
- `cliide/editor/syntax.py`
- `cliide/ui/tabs.py`
- `cliide/ui/diff_viewer.py`
- `cliide/utils/keybindings.py`

### Estimated Time
4-5 weeks

---

## Phase 5: Testing & Polish

**Goal**: Production-ready release

### Tasks

#### 5.1 Testing
- [ ] Unit tests for core logic
- [ ] Integration tests for UI
- [ ] End-to-end tests
- [ ] Performance benchmarks

#### 5.2 Documentation
- [ ] User guide
- [ ] API documentation
- [ ] Video tutorials
- [ ] Example projects

#### 5.3 Packaging
- [ ] PyPI package
- [ ] Docker image
- [ ] Homebrew formula (macOS)
- [ ] AUR package (Arch Linux)

#### 5.4 CI/CD
- [ ] GitHub Actions workflows
- [ ] Automated testing
- [ ] Release automation
- [ ] Changelog generation

### Estimated Time
2-3 weeks

---

## Future Ideas

### Plugin System
- Python-based plugins
- Hook into events
- Custom AI actions
- Custom widgets

### Collaborative Features
- Real-time collaboration
- Share AI sessions
- Team settings

### AI Enhancements
- Multiple AI models
- Model switching
- Fine-tuned models for specific tasks
- Code review mode

### Performance
- Lazy loading for large files
- Virtual scrolling
- Background indexing
- Caching layer

---

## Contributing

See areas where you can help:
1. **Phase 2**: AI integration - Core functionality
2. **Phase 3**: LSP support - IDE features
3. **Phase 4**: Advanced features - UX polish
4. **Testing**: Write tests for existing code
5. **Documentation**: Improve docs and examples

Check GitHub Issues for specific tasks!
