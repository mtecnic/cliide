# Troubleshooting Guide

Common issues and solutions for cliide.

## Installation Issues

### `cliide: command not found`

**Problem**: The cliide command is not available in your PATH.

**Solution**:
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Verify installation
which cliide
```

### Import Errors

**Problem**: Module import errors when running cliide.

**Solution**:
```bash
# Reinstall dependencies
pip install -e . --force-reinstall

# Or create a fresh venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Runtime Issues

### Tree-sitter Language Not Found

**Problem**:
```
LanguageDoesNotExist: tree-sitter is available, but no built-in or user-registered language called 'python'
```

**Solution**: This warning is harmless and has been fixed in the latest version. The editor will fall back to plain text highlighting when a language is not available.

**Status**: ✅ Fixed - The editor now gracefully handles missing languages.

### DirectoryTree Async Warning

**Problem**:
```
RuntimeWarning: coroutine 'DirectoryTree.watch_path' was never awaited
```

**Solution**: This is a harmless warning from Textual's DirectoryTree widget. It doesn't affect functionality.

**Status**: ⚠️ Known issue - Can be ignored. File tree still works normally.

**To suppress**:
```bash
# Run with warnings filtered
python -W ignore::RuntimeWarning venv/bin/cliide
```

## Configuration Issues

### VLLM Connection Failed

**Problem**: Cannot connect to VLLM server.

**Solution**:
```bash
# 1. Check if VLLM server is running
curl http://192.168.86.30:8000/health

# 2. Verify configuration
cat ~/.config/cliide/config.toml

# 3. Update VLLM URL
cliide --oapi-url http://YOUR_SERVER:8000/v1

# 4. Test connection
curl http://YOUR_SERVER:8000/v1/models
```

### Config File Not Found

**Problem**: cliide doesn't find your config file.

**Solution**:
cliide looks for config in these locations (in order):
1. `.cliide.toml` in current directory
2. `~/.config/cliide/config.toml`

Create config:
```bash
# Copy example config
mkdir -p ~/.config/cliide
cp config.example.toml ~/.config/cliide/config.toml

# Edit as needed
nano ~/.config/cliide/config.toml
```

## UI Issues

### No Syntax Highlighting

**Problem**: Code appears as plain text without colors.

**Solution**:
- This is expected when tree-sitter languages aren't available
- Future versions will include better syntax highlighting
- Editor still provides all functionality

### File Tree Not Showing

**Problem**: Left panel (file tree) is empty or hidden.

**Solution**:
```bash
# Toggle file tree
Press Ctrl+B

# Or check config
cat ~/.config/cliide/config.toml
# Ensure: show_file_tree = true
```

### Chat Panel Not Responding

**Problem**: Chat panel doesn't send messages to AI.

**Solution**:
- AI integration is in Phase 2 (not yet implemented)
- Currently only the UI is functional
- Backend coming soon!

**Status**: 🚧 In Development - Phase 2

## Performance Issues

### Slow File Loading

**Problem**: Large files load slowly.

**Solution**:
- Current version loads entire file into memory
- For large files (>10MB), use traditional editors
- Optimization planned for Phase 4

### High Memory Usage

**Problem**: cliide uses a lot of memory.

**Solution**:
- Close unused files/tabs
- Restart cliide periodically
- Memory optimization planned for Phase 4

## Keyboard Issues

### Shortcuts Not Working

**Problem**: Ctrl+key combinations don't work.

**Solution**:
```bash
# Check your terminal emulator settings
# Some terminals intercept certain key combinations

# Common issues:
# - Ctrl+Q might close terminal (not cliide)
# - Ctrl+S might freeze terminal (use Ctrl+Q to unfreeze)

# Test in different terminal:
# - Try: gnome-terminal, kitty, alacritty, etc.
```

### Vim Keybindings?

**Problem**: Want vim-style navigation.

**Status**: 📋 Planned for Phase 4

**Current**: Use arrow keys and standard keybindings

## Getting Help

### Debug Mode

Run cliide with debug output:
```bash
# Enable Python debugging
PYTHONDEVMODE=1 cliide

# Or with Textual's dev mode
textual console &
cliide
```

### Report Issues

If you encounter issues not listed here:

1. **Check GitHub Issues**: https://github.com/yourusername/cliide/issues
2. **Gather Information**:
   ```bash
   # System info
   python --version
   pip list | grep textual

   # Config
   cat ~/.config/cliide/config.toml

   # Error messages
   cliide 2>&1 | tee cliide_error.log
   ```
3. **Create Issue**: Include the above information

## Known Limitations

### Phase 1 (Current)
- ✅ Basic UI functional
- ⚠️ AI features not yet implemented
- ⚠️ LSP not yet integrated
- ⚠️ Limited syntax highlighting
- ⚠️ No multi-file editing

### Coming Soon
- 🚧 Phase 2: AI integration with VLLM
- 📋 Phase 3: LSP support
- 📋 Phase 4: Advanced editor features

## Quick Fixes

### Reset Configuration

```bash
# Backup current config
cp ~/.config/cliide/config.toml ~/.config/cliide/config.toml.backup

# Remove config
rm ~/.config/cliide/config.toml

# Reconfigure
cliide --oapi-url http://YOUR_SERVER:8000/v1
cliide --model "YOUR_MODEL_NAME"
```

### Clean Reinstall

```bash
# Remove installation
pip uninstall cliide -y

# Clear cache
rm -rf ~/.cache/cliide

# Remove config
rm -rf ~/.config/cliide

# Reinstall
cd /path/to/cliide
pip install -e .

# Reconfigure
cliide --oapi-url http://YOUR_SERVER:8000/v1
cliide --model "google--gemma-3-12b-it"
```

## FAQ

**Q: Why does tree-sitter not work?**
A: Textual's TextArea has its own tree-sitter integration that requires specific setup. We're working on proper integration in Phase 2.

**Q: When will AI features work?**
A: Phase 2 is next! AI integration with VLLM is the top priority.

**Q: Can I use OpenAI instead of VLLM?**
A: Yes! Set the URL to OpenAI's endpoint:
```bash
cliide --oapi-url https://api.openai.com/v1
export OPENAI_API_KEY=your-key-here
```

**Q: Why is there an async warning?**
A: It's a harmless internal warning from Textual's DirectoryTree. Doesn't affect functionality.

**Q: How do I change themes?**
A: Edit `~/.config/cliide/config.toml`:
```toml
[editor]
theme = "monokai"  # or "dracula", "github", etc.
```

## Still Having Issues?

1. **Check logs**: `~/.local/share/cliide/logs/` (if enabled)
2. **Discord**: Join our community (coming soon)
3. **GitHub**: Open an issue with details
4. **Email**: support@cliide.dev (coming soon)

---

Last Updated: Phase 1 Complete
