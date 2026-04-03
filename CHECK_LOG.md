# Check Debug Log

I've added file-based logging to trace exactly what's happening!

## Run cliide

```bash
source venv/bin/activate
cliide
```

## Send a test message

1. Press Tab to focus the chat input (bottom right)
2. Type: `hello`
3. Press Enter
4. You'll see "Thinking..." appear

## Check the log

```bash
# In another terminal:
tail -f /tmp/cliide_debug.log
```

Or after you've sent the message:
```bash
cat /tmp/cliide_debug.log
```

## What you should see

If everything is working:
```
[HH:MM:SS] [CHAT] Posting AIRequestStarted: hello
[HH:MM:SS] [APP] Received AIRequestStarted: hello
[HH:MM:SS] [APP] Updating status to Processing
[HH:MM:SS] [APP] Parsing command from: hello
[HH:MM:SS] [APP] Command: None, Content: hello
[HH:MM:SS] [APP] Starting AI response
[HH:MM:SS] [APP] Handling regular chat
[HH:MM:SS] [APP] Calling chat with context: file=None, has_code=False
[HH:MM:SS] [APP] Received chunk 1: Hello...
[HH:MM:SS] [APP] Received chunk 2: from...
... more chunks ...
[HH:MM:SS] [APP] Total chunks received: 45
[HH:MM:SS] [APP] Finishing AI response
[HH:MM:SS] [APP] AI request completed successfully
```

## What tells us what

### No [CHAT] line
**Problem**: Input event not firing or send_message not called
**Try**: Run `./venv/bin/python test_sync_event.py`

### [CHAT] but no [APP]
**Problem**: Event not reaching app handler
**Issue**: Event routing broken (I'll fix)

### [APP] lines but stops early
**Problem**: Exception or async issue
**Look for**: "Error:" or "Traceback:" in log

### All [APP] lines, 0 chunks
**Problem**: VLLM connection or API issue
**Check**: VLLM server logs

## Send me the log

Paste the contents of `/tmp/cliide_debug.log` after you send a message!

This will tell me exactly where it's failing.
