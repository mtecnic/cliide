#!/usr/bin/env bash
# Install language servers for cliide LSP integration

set -e

echo "=========================================="
echo "cliide - LSP Server Installation"
echo "=========================================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo ""
    echo "Node.js is required for pyright and typescript-language-server."
    echo "Please install Node.js first:"
    echo ""
    echo "Ubuntu/Debian:"
    echo "  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -"
    echo "  sudo apt-get install -y nodejs"
    echo ""
    echo "macOS:"
    echo "  brew install node"
    echo ""
    echo "Or download from: https://nodejs.org"
    exit 1
fi

echo "✓ Node.js $(node --version) found"
echo ""

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    echo "Please install npm (usually comes with Node.js)"
    exit 1
fi

echo "✓ npm $(npm --version) found"
echo ""

# Install pyright (Python language server)
echo "Installing pyright (Python language server)..."
if sudo npm install -g pyright; then
    echo "✓ pyright installed successfully"
else
    echo "❌ Failed to install pyright"
    echo "Try running: sudo npm install -g pyright"
    exit 1
fi
echo ""

# Install typescript-language-server
echo "Installing typescript-language-server..."
if sudo npm install -g typescript-language-server typescript; then
    echo "✓ typescript-language-server installed successfully"
else
    echo "❌ Failed to install typescript-language-server"
    echo "Try running: sudo npm install -g typescript-language-server typescript"
    exit 1
fi
echo ""

echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "Installed language servers:"
echo "  • pyright (Python)"
echo "  • typescript-language-server (JavaScript/TypeScript)"
echo ""
echo "You can now use LSP features in cliide:"
echo "  • Ctrl+Space - Code completion"
echo "  • F12 - Go to definition"
echo "  • Shift+F12 - Find references"
echo "  • F2 - Rename symbol"
echo "  • Ctrl+Shift+M - Toggle problems panel"
echo ""
