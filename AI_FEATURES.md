# AI Features Guide

**Phase 2 Complete!** 🎉 cliide now has full AI integration with your local VLLM server.

## Quick Setup

```bash
# 1. Configure your VLLM server
cliide --oapi-url http://192.168.86.30:8000/v1

# 2. Set your model (use the full path from your server)
cliide --model "/app/models/google--gemma-3-12b-it"

# 3. Launch cliide
cliide
```

## Using AI Features

### Chat Panel

The AI chat panel is on the right side of the screen.

**Basic Usage:**
1. Type your question in the input box at the bottom
2. Press Enter to send
3. Watch the AI respond in real-time (streaming!)

**Features:**
- ✅ Real-time streaming responses
- ✅ Conversation history maintained
- ✅ Context-aware (sees your current file)
- ✅ Code block highlighting in responses

### Slash Commands

Use slash commands for specific AI tasks:

#### `/explain`
Explain selected code or provided code

```
# Select code in editor, then in chat:
/explain

# Or provide code directly:
/explain def factorial(n): return 1 if n == 0 else n * factorial(n-1)
```

**What it does:**
- Explains what the code does
- Breaks down the logic step-by-step
- Identifies patterns and idioms
- Notes any potential issues

#### `/refactor`
Get refactoring suggestions

```
# Select code, then:
/refactor

# Provides:
- Readability improvements
- Performance optimizations
- Best practices
- Code examples
```

#### `/fix`
Find and fix bugs

```
# Select problematic code:
/fix

# AI will:
- Identify potential bugs
- Explain the issues
- Provide corrected code
- Suggest prevention strategies
```

#### `/test`
Generate tests for code

```
# Select function/class:
/test

# Creates:
- Unit tests
- Edge case tests
- Integration tests
- With assertions and descriptions
```

#### `/doc` or `/document`
Generate documentation

```
# Select code:
/doc

# Generates:
- Docstrings/comments
- Usage examples
- Parameter descriptions
- Following language conventions
```

### Context-Aware AI

The AI automatically sees:
- **Current file name**: Helps with language-specific advice
- **Selected code**: When you have text selected
- **Conversation history**: Maintains context across messages

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Toggle AI chat panel |
| `Ctrl+E` | Explain selected code (auto-opens chat) |

### Example Workflows

#### 1. Understanding New Code

```
1. Open a file you want to understand
2. Select a confusing function
3. Press Ctrl+E or type /explain in chat
4. Read AI's explanation
5. Ask follow-up questions in chat
```

#### 2. Improving Code Quality

```
1. Select code you wrote
2. Type: /refactor
3. Review suggestions
4. Type: /test
5. Get tests generated
6. Apply improvements
```

#### 3. Debugging

```
1. Select buggy code
2. Type: /fix
3. Review AI's analysis
4. Ask: "Why does this fail when n is negative?"
5. Get detailed explanation
6. Apply the fix
```

#### 4. Learning New Patterns

```
1. Ask: "Show me how to implement a singleton in Python"
2. Get code example
3. Ask: "When should I use this pattern?"
4. Get best practices
5. Apply to your code
```

## AI Configuration

### Config File Location

```bash
~/.config/cliide/config.toml
```

### AI Settings

```toml
[vllm]
base_url = "http://192.168.86.30:8000/v1"
model = "/app/models/google--gemma-3-12b-it"
temperature = 0.2  # Lower = more focused, Higher = more creative
max_tokens = 2048  # Maximum response length
streaming = true   # Enable real-time streaming
timeout = 60       # Request timeout in seconds
```

### Adjusting AI Behavior

**Temperature** (0.0 - 2.0):
- `0.1-0.3`: Focused, deterministic (good for code)
- `0.4-0.7`: Balanced
- `0.8-2.0`: Creative, varied

**Max Tokens**:
- `512`: Short responses
- `2048`: Standard (recommended)
- `4096+`: Long, detailed responses

## Tips & Tricks

### 1. Be Specific

❌ "Fix this"
✅ "This function crashes when the list is empty. How do I handle that?"

### 2. Use Context

Select relevant code before asking questions. The AI sees your selection!

### 3. Iterate

Don't be afraid to ask follow-up questions:
- "Can you explain that differently?"
- "Show me an example"
- "What are the trade-offs?"

### 4. Combine Commands

```
1. /explain (understand code)
2. Ask: "How can this be improved?"
3. /refactor (get suggestions)
4. /test (generate tests)
```

### 5. Ask for Explanations

"Why did you suggest this approach?"
"What's the performance impact?"
"Are there alternatives?"

## Troubleshooting

### "Disconnected" Status

```bash
# Check VLLM server is running:
curl http://192.168.86.30:8000/health

# Verify config:
cat ~/.config/cliide/config.toml

# Reconnect:
cliide --oapi-url http://YOUR_SERVER:8000/v1
```

### Model Not Found Error

```bash
# Get available models:
curl http://192.168.86.30:8000/v1/models

# Update model name (use exact name from above):
cliide --model "/app/models/YOUR_MODEL_NAME"
```

### Slow Responses

- Check network connection to VLLM server
- Try reducing `max_tokens` in config
- Ensure VLLM server has sufficient resources

### No Response

1. Check status bar shows "Connected"
2. Try a simple message: "Hello"
3. Check terminal for error messages
4. Verify VLLM server is responding:
   ```bash
   curl http://YOUR_SERVER:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "YOUR_MODEL", "messages": [{"role": "user", "content": "test"}]}'
   ```

## Advanced Usage

### Custom System Prompts

Currently, system prompts are built-in. Custom prompts coming in future versions!

### Multi-File Context

Currently sees one file at a time. Multi-file context coming in Phase 3!

### Command Chaining

```
/explain
# ... read explanation ...
# Then ask follow-up:
"Now show me how to make this asynchronous"
```

### Using with LSP

Phase 3 will integrate AI with LSP diagnostics for even smarter suggestions!

## What's Next

### Coming in Phase 3: LSP Integration

- AI will see LSP diagnostics (errors/warnings)
- Smarter fixes based on type information
- Integration with code completion
- Go-to-definition with AI explanations

### Future Features

- [ ] Code review mode
- [ ] Diff view for AI suggestions
- [ ] Multi-file refactoring
- [ ] Custom prompt templates
- [ ] Fine-tuned models for specific tasks
- [ ] Collaborative AI sessions

## Performance

**Benchmarks** (with google--gemma-3-12b-it):
- Connection check: < 100ms
- Simple completion: ~1-2s
- Code explanation: ~2-5s (streaming)
- Refactoring suggestions: ~3-6s

**Network Requirements:**
- Low latency to VLLM server
- Stable connection for streaming
- ~1-10 KB/s bandwidth during streaming

## Privacy & Security

✅ **Your data stays local!**
- All AI processing on your VLLM server
- No data sent to third parties
- No API keys required (unless using OpenAI)
- Conversation history stored in memory only

## Examples

### Example 1: Explaining Complex Code

**Input:**
```python
def memoize(func):
    cache = {}
    def wrapper(*args):
        if args in cache:
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result
    return wrapper
```

**Command:** `/explain`

**AI Response:** (streamed in real-time)
> This is a memoization decorator in Python. Here's how it works:
>
> 1. **Purpose**: Caches function results to avoid redundant calculations
> 2. **Mechanism**:
>    - Creates a `cache` dictionary to store results
>    - Wraps the original function
>    - Checks if arguments exist in cache
>    - Returns cached result or computes new one
> 3. **Pattern**: Classic decorator pattern
> 4. **Note**: May have issues with unhashable arguments

### Example 2: Getting Help

**You:** "How do I read a CSV file in Python?"

**AI:** (streams response)
> Here are several ways to read a CSV file in Python:
>
> **Using csv module:**
> ```python
> import csv
> with open('file.csv', 'r') as f:
>     reader = csv.reader(f)
>     for row in reader:
>         print(row)
> ```
> ...

## Resources

- **VLLM Docs**: https://docs.vllm.ai
- **Model Hub**: https://huggingface.co/models
- **cliide Issues**: https://github.com/yourusername/cliide/issues
- **Prompt Engineering**: https://www.promptingguide.ai

---

**Happy coding with AI!** 🚀🤖

