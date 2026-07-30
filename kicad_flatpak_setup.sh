#!/bin/bash
# Setup MCP dependencies inside KiCad Flatpak container

set -e

FLATPAK_ID="org.kicad.KiCad"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================================================"
echo "KiCad MCP Server - Flatpak Setup"
echo "======================================================================"
echo

# Check if Flatpak is installed
if ! command -v flatpak &> /dev/null; then
    echo -e "${RED}Error: Flatpak not found${NC}"
    echo "Install flatpak first"
    exit 1
fi

# Check if KiCad Flatpak is installed
if ! flatpak list | grep -q "$FLATPAK_ID"; then
    echo -e "${RED}Error: KiCad Flatpak not installed${NC}"
    echo
    echo "Install with:"
    echo "  flatpak install flathub org.kicad.KiCad"
    exit 1
fi

echo -e "${GREEN}✓ KiCad Flatpak found${NC}"
echo

# Get KiCad version
KICAD_VERSION=$(flatpak run --command=python3 "$FLATPAK_ID" -c "import pcbnew; print(pcbnew.GetBuildVersion())")
echo "KiCad version: $KICAD_VERSION"
echo

# Check Python version
PYTHON_VERSION=$(flatpak run --command=python3 "$FLATPAK_ID" --version)
echo "Python version: $PYTHON_VERSION"
echo

# Check if pip is available
echo "Checking if pip is available in Flatpak..."
if flatpak run --command=python3 "$FLATPAK_ID" -m pip --version &>/dev/null; then
    echo -e "${GREEN}✓ pip is available${NC}"
else
    echo -e "${YELLOW}⚠ pip not found, attempting to install...${NC}"

    # Try to install pip using get-pip.py
    echo "Downloading get-pip.py..."
    TMP_DIR=$(mktemp -d)
    cd "$TMP_DIR"

    curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py

    echo "Installing pip in Flatpak..."
    flatpak run --command=python3 --filesystem="$TMP_DIR" "$FLATPAK_ID" get-pip.py --user

    cd - > /dev/null
    rm -rf "$TMP_DIR"

    if flatpak run --command=python3 "$FLATPAK_ID" -m pip --version &>/dev/null; then
        echo -e "${GREEN}✓ pip installed successfully${NC}"
    else
        echo -e "${RED}✗ Failed to install pip${NC}"
        echo
        echo "Alternative: Install dependencies manually in the Flatpak"
        exit 1
    fi
fi

echo
echo "======================================================================"
echo "Installing MCP dependencies..."
echo "======================================================================"
echo

# Install required packages
echo "Installing: mcp 1.x, anthropic, python-dotenv"
echo

flatpak run --command=python3 "$FLATPAK_ID" -m pip install --user --upgrade \
    "mcp>=1.0.0,<2.0.0" \
    anthropic \
    python-dotenv

echo
echo "======================================================================"
echo "Verifying installation..."
echo "======================================================================"
echo

# Verify each package
PACKAGES=("mcp" "anthropic" "dotenv")
ALL_OK=true

for pkg in "${PACKAGES[@]}"; do
    echo -n "Checking $pkg... "
    if flatpak run --command=python3 "$FLATPAK_ID" -c "import $pkg" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ALL_OK=false
    fi
done

echo

if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}======================================================================"
    echo "Setup Complete!"
    echo "======================================================================${NC}"
    echo
    echo "Next steps:"
    echo "1. Make sure you have a .env file with your ANTHROPIC_API_KEY"
    echo "2. Open a PCB in KiCad PCBNew"
    echo "3. Run the server:"
    echo "   ./run_with_flatpak.sh"
    echo
    echo "4. In another terminal, run the client:"
    echo "   source venv/bin/activate"
    echo "   mcp-kicad-client ./run_with_flatpak.sh"
else
    echo -e "${RED}======================================================================"
    echo "Setup Failed"
    echo "======================================================================${NC}"
    echo
    echo "Some packages failed to install."
    echo "Try installing manually:"
    echo "  flatpak run --command=python3 $FLATPAK_ID -m pip install --user 'mcp>=1,<2' anthropic python-dotenv"
    exit 1
fi
