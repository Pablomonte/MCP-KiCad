#!/bin/bash
# Setup script for KiCad MCP Integration

set -e  # Exit on error

echo "======================================================================"
echo "KiCad MCP Integration - Setup Script"
echo "======================================================================"
echo

# Check Python version
echo "Checking Python version..."
python3 --version || {
    echo "Error: Python 3 not found"
    exit 1
}

# Create virtual environment
if [ -d "venv" ]; then
    echo "Virtual environment already exists"
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip -q

# Install the package and development dependencies
echo "Installing package and development dependencies..."
pip install -e ".[dev]" -q
echo "✓ Package installed"

# Create .env if it doesn't exist
if [ -f ".env" ]; then
    echo ".env file already exists"
else
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created"
    echo
    echo "⚠ IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY"
    echo "  Get your key from: https://console.anthropic.com/"
fi

# Make scripts executable
echo "Making scripts executable..."
chmod +x check_kicad.py run_with_flatpak.sh kicad_flatpak_setup.sh

# Run environment check
echo
echo "======================================================================"
echo "Running environment check..."
echo "======================================================================"
echo
python check_kicad.py

echo
echo "======================================================================"
echo "Setup Complete!"
echo "======================================================================"
echo
echo "Next steps:"
echo
echo "1. Add your API key to .env file:"
echo "   nano .env"
echo
echo "2. Test in mock mode:"
echo "   source venv/bin/activate"
echo "   pytest"
echo
echo "3. Or use with KiCad:"
echo "   - Open a PCB in KiCad PCBNew"
echo "   - Terminal 1: ./run_with_flatpak.sh"
echo "   - Terminal 2: mcp-kicad-client ./run_with_flatpak.sh"
echo
echo "See README.md for full documentation"
echo
