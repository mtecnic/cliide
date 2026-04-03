# Chat Panel Usage Guide

## Accessing the Chat Input

The chat panel is on the **right side** of the screen. Here's how to use it:

### Method 1: Click on the Input (if using mouse-enabled terminal)
Simply click on the input box at the bottom of the chat panel.

### Method 2: Use Tab to Navigate
Press `Tab` repeatedly to cycle through widgets until the chat input is focused (you'll see the cursor in the input box).

### Method 3: Use Ctrl+K to Toggle
1. Press `Ctrl+K` to hide the chat panel
2. Press `Ctrl+K` again to show it
3. The input should be focused when the panel reopens

### Verifying Input Focus

When the chat input is focused, you should see:
- A cursor blinking in the input box
- The placeholder text: "Ask AI anything..."

## Sending Messages

Once the input is focused:
1. Type your message
2. Press `Enter` to send
3. Watch the AI respond in real-time above the input

## Common Issues

### "I type but nothing appears"

**Problem**: The chat input doesn't have focus.

**Solution**: Press `Tab` until you see the cursor in the chat input box.

### "Pressing Enter doesn't send"

**Problem**: Focus might be on the wrong widget.

**Solution**:
1. Press `Tab` to cycle to the chat input
2. Make sure you see the cursor blinking in the input
3. Try typing - you should see characters appear

### "Chat panel is hidden"

**Problem**: Chat panel was toggled off.

**Solution**: Press `Ctrl+K` to show the chat panel.

## Navigation Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Cycle through widgets (file tree → editor → chat input) |
| `Shift+Tab` | Cycle backwards |
| `Ctrl+K` | Toggle chat panel visibility |
| `Ctrl+B` | Toggle file tree |

## Testing Chat Input

Try this simple test:

1. Launch cliide: `cliide`
2. Press `Tab` until the cursor is in the chat input (bottom right)
3. Type: `hello`
4. Press `Enter`
5. You should see:
   - "👤 You: hello" appear in the chat
   - "🤖 AI: Thinking..." appear briefly
   - Then the AI's response stream in

## Debug Mode

If chat still doesn't work, test it standalone:

```bash
# Run the standalone chat test
./venv/bin/python test_chat_standalone.py
```

This isolated test will help identify if the issue is with:
- The chat panel itself
- The main app layout
- Terminal compatibility

## Terminal Compatibility

**Known Issues:**
- Some terminals don't support Tab navigation well
- WSL terminals may have focus issues

**Workarounds:**
1. Try a different terminal (kitty, alacritty, gnome-terminal)
2. Use tmux/screen
3. Try the standalone test app

## Quick Check

1. ✓ Can you see the chat panel on the right?
2. ✓ Can you see the input box at the bottom of the chat panel?
3. ✓ When you press Tab, does the cursor move?
4. ✓ Does typing show characters in the input?
5. ✓ Does Enter send the message?

If any of these fail, please report the issue with:
- Your terminal emulator name and version
- Operating system
- Output from the standalone test

## Need Help?

Run the diagnostic:
```bash
./venv/bin/python test_chat_standalone.py
```

If that works, the issue is with widget focus in the main app.
If that doesn't work, it's a terminal compatibility issue.

---

**TL;DR: Press Tab until you see the cursor in the chat input box, then type and press Enter!**
