# Debug Run Instructions

I've added comprehensive debug logging to trace the event flow. Here's how to see what's happening:

## Run with Debug Output

```bash
# In one terminal, watch your VLLM server logs
# (wherever you're running VLLM)

# In another terminal:
source venv/bin/activate
cliide 2>&1 | tee debug.log
```

This will:
1. Run cliide
2. Show ALL debug messages (stderr and stdout)
3. Save everything to `debug.log`

## What to Look For

When you type a message and press Enter, you should see:

```
[CHAT] Posting AIRequestStarted: your message here
[APP] Received AIRequestStarted: your message here
[APP] Updating status to Processing
[APP] Parsing command from: your message here
[APP] Command: None, Content: your message here
[APP] Starting AI response
[APP] Handling regular chat
[APP] Calling chat with context: file=None, has_code=False
[APP] Received chunk: Hello...
[APP] Received chunk: from...
[APP] Received chunk: AI...
[APP] Finishing AI response
```

## Scenarios

### Scenario 1: No [CHAT] message
**Problem**: Input event not firing
**Debug**: Run the standalone test
```bash
./venv/bin/python test_event_flow.py 2>&1
```

### Scenario 2: [CHAT] but no [APP]
**Problem**: Event not reaching app handler
**Possible cause**: Event bubbling issue

### Scenario 3: [APP] but no VLLM request
**Problem**: Exception in AI code
**Look for**: Python traceback in output

### Scenario 4: VLLM request but no chunks
**Problem**: Streaming issue or model response empty
**Check**: VLLM server logs

## Quick Test

1. Launch cliide with debug output:
   ```bash
   cliide 2>&1 | tee debug.log
   ```

2. Press Tab until cursor is in chat input (bottom right)

3. Type: `hello`

4. Press Enter

5. Watch for debug messages in the terminal

6. Check debug.log file for full trace

7. Also check your VLLM server logs

## Send Me the Output

If it's still not working, send me:

1. The debug.log file (or relevant portion)
2. What you saw in the UI
3. What appeared in VLLM server logs (if anything)

This will help me pinpoint exactly where the flow breaks!

## Cleanup Debug Logging

Once we fix this, I'll remove all the debug print statements.
