# KiCad MCP Integration

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![KiCad 9.0+](https://img.shields.io/badge/KiCad-9.0+-blue.svg)](https://www.kicad.org/)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/Pablomonte/MCP-KiCad/releases/tag/v1.0.0)
[![CI/CD](https://github.com/Pablomonte/MCP-KiCad/actions/workflows/ci.yml/badge.svg)](https://github.com/Pablomonte/MCP-KiCad/actions)
[![Tests](https://img.shields.io/badge/tests-135%20passing-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-43%25-yellow.svg)](#testing)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

AI-assisted KiCad PCB design using Model Context Protocol (MCP) and Anthropic Claude.

## Overview

This project provides an MCP server that exposes KiCad PCB design tools to AI assistants, enabling natural language interaction with your PCB designs. You can ask an AI to place components, read netlists, and get layout suggestions.

## Features

- **Natural Language PCB Design**: Interact with KiCad using plain English
- **Component Placement**: Ask AI to place components at specific coordinates
- **Board Analysis**: Query component lists, netlists, and board information
- **Layout Guidance**: Get AI-powered layout suggestions for common circuit types
- **Real-time Updates**: Changes are immediately reflected in KiCad

## Architecture

```
┌─────────────┐         ┌─────────────┐         ┌──────────┐
│   You       │ ───────▶│  AI Client  │ ───────▶│  Claude  │
│  (User)     │  Chat   │  (Python)   │   API   │   AI     │
└─────────────┘         └─────────────┘         └──────────┘
                              │
                              │ MCP Protocol
                              ▼
                        ┌─────────────┐         ┌──────────┐
                        │ MCP Server  │ ───────▶│  KiCad   │
                        │  (Python)   │ pcbnew  │ PCBNew   │
                        └─────────────┘         └──────────┘
```

## Prerequisites

1. **KiCad 9.0+** (Flatpak installation recommended)
2. **Python 3.10+**
3. **Anthropic API Key** (or xAI API key for Grok)

## Quick Start

```bash
git clone https://github.com/Pablomonte/MCP-KiCad.git
cd MCP-KiCad
./setup.sh
./kicad_flatpak_setup.sh
```

Open a board in KiCad, then start the packaged extended server and client:

```bash
# Terminal 1
./run_with_flatpak.sh

# Terminal 2, with the virtual environment activated
mcp-kicad-client ./run_with_flatpak.sh
```

The server also works without `pcbnew` in mock mode:

```bash
mcp-kicad
```

## Installation

### Method 1: Flatpak (Recommended)

Works with KiCad 9.0+ Flatpak installation. This is the tested and recommended approach.

#### Step 1: Clone the Repository

```bash
cd ~/repos
git clone https://github.com/Pablomonte/MCP-KiCad.git
cd MCP-KiCad
```

#### Step 2: Install KiCad Flatpak

```bash
flatpak install flathub org.kicad.KiCad
```

#### Step 3: Install Dependencies in Flatpak

```bash
./kicad_flatpak_setup.sh
```

This script automatically installs the required Python packages (`mcp`, `anthropic`, `python-dotenv`) inside the KiCad Flatpak container.

#### Step 4: Configure API Key

```bash
cp .env.example .env
nano .env  # or your preferred editor
```

Add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx
```

Get your API key from: https://console.anthropic.com/

#### Step 5: You're Ready!

Run the server using:

```bash
./run_with_flatpak.sh  # Uses extended server (12 tools) by default
```

### Method 2: Native Python (Advanced)

For native KiCad installations or development purposes.

#### Step 1-3: Same as Flatpak Method

Clone the repository and configure API key.

#### Step 4: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate  # On Windows
```

#### Step 5: Install Dependencies

```bash
# Install the package in editable mode
pip install -e .

# For development (includes testing tools)
pip install -e .[dev]
```

#### Step 6: Setup KiCad Python Environment

The MCP server needs access to KiCad's `pcbnew` module.

**Option A: Use KiCad's Python**

Find and use KiCad's Python installation:

```bash
# Linux
PYTHONPATH=src /usr/lib/kicad/bin/python3 -m mcp_kicad.server.extended

# Mac
PYTHONPATH=src /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -m mcp_kicad.server.extended

# Windows
set PYTHONPATH=src
"C:\Program Files\KiCad\9.0\bin\python.exe" -m mcp_kicad.server.extended
```

**Option B: Link pcbnew to Virtual Environment**

```bash
# Linux example
ln -s /usr/lib/python3/dist-packages/pcbnew.py venv/lib/python3.*/site-packages/
ln -s /usr/lib/python3/dist-packages/_pcbnew.so venv/lib/python3.*/site-packages/
```

**Note**: Exact paths vary by system. Check your KiCad installation directory.

## Usage

### 1. Open KiCad PCBNew

First, open your PCB project in KiCad PCBNew:

```bash
kicad path/to/your/project.kicad_pcb
```

Make sure the PCB editor (PCBNew) is open, not just the project manager.

### 2. Run the MCP Server

Choose between basic server (4 tools) or extended server (12 tools, recommended):

**With Flatpak (Recommended):**

```bash
# Extended server - recommended (includes fabrication tools)
./run_with_flatpak.sh

# Basic server only
./run_with_flatpak.sh basic
```

**With Native Python:**

```bash
# If using virtual environment
source venv/bin/activate
mcp-kicad  # use mcp-kicad-basic for the basic server

# Or with KiCad's Python
PYTHONPATH=src /usr/lib/kicad/bin/python3 -m mcp_kicad.server.extended
```

The server will connect to the currently open KiCad board and wait for MCP requests.

**Note**: If pcbnew is not available, the server runs in **mock mode** for testing.

### 3. Run the Client

In another terminal, launch the client with the command that starts the server:

```bash
# Native installation
mcp-kicad-client mcp-kicad

# Flatpak installation
mcp-kicad-client ./run_with_flatpak.sh
```

You should see:

```
Connected to KiCad MCP Server
Available tools: place_component, read_netlist, list_components, get_board_info

======================================================================
KiCad AI Assistant
======================================================================

You can ask me to help with your PCB design!
...

You:
```

### 4. Interact with Your Board

Try these example queries:

**Basic Operations:**
```
You: List all components on the board
You: Place R1 at position 10, 20 mm
You: Move capacitor C1 to 15, 25 mm with 90 degree rotation
You: Show me the netlist
You: What's the board size?
You: Give me layout suggestions for an LED circuit
```

**Fabrication Operations (Extended Server):**
```
You: Export Gerber files to ./gerber
You: Generate drill files in Excellon format
You: Create a complete fabrication package for JLCPCB
You: Export the Bill of Materials (BOM)
You: Generate pick-and-place position file
You: Run Design Rule Check
You: Fill all copper zones
```

The AI will:
1. Understand your natural language request
2. Call the appropriate KiCad tools via MCP
3. Execute changes or exports on your PCB
4. Provide feedback on what was done

### 5. Verify Changes in KiCad

After the AI makes changes, refresh your KiCad view to see the updates:
- Click on the PCB canvas
- Press `F5` or use View → Refresh

## Available Tools

The project includes two MCP server variants:

### Server Comparison

| Feature | Basic Server | Extended Server |
|---------|-------------|----------------|
| Entry point | `mcp-kicad-basic` | `mcp-kicad` |
| Tool Count | 4 tools | 12 tools |
| Use Case | Component placement & queries | Full fabrication workflow |
| Recommended | Testing & learning | Production use |

### Basic Server Tools (4 tools)

Both servers include these basic tools:

#### place_component
Move a component to a specific position on the PCB.

**Parameters**:
- `reference` (string): Component reference (e.g., "R1", "U1")
- `x_mm` (number): X position in millimeters
- `y_mm` (number): Y position in millimeters
- `rotation_deg` (number, optional): Rotation angle in degrees

#### list_components
List all components on the PCB with their current positions.

**Returns**: JSON array of components with reference, value, position, rotation, layer

#### read_netlist
Read netlist information from the board.

**Returns**: JSON array of nets with names and net codes

#### get_board_info
Get general information about the PCB.

**Returns**: Board size, layer count, component count, filename

### Extended Server Additional Tools (8 more tools)

The extended server adds these fabrication and verification tools:

#### Fabrication Tools (5 tools)

##### export_gerber
Export Gerber files (RS-274X format) for PCB manufacturing.

**Parameters**:
- `output_dir` (string): Output directory path
- `layers` (array, optional): Specific layers to export

**Returns**: List of generated Gerber files

##### export_drill_files
Export drill files in Excellon format.

**Parameters**:
- `output_dir` (string): Output directory path
- `merge_pth_npth` (boolean, optional): Merge PTH and NPTH into one file

**Returns**: Generated drill file paths

##### export_fabrication_package
Create a complete fabrication package as a ZIP file.

**Parameters**:
- `output_path` (string): ZIP file output path

**Returns**: Package path and included files list

##### export_bom
Export Bill of Materials in CSV format.

**Parameters**:
- `output_path` (string): CSV file output path
- `include_dnp` (boolean, optional): Include "Do Not Populate" components

**Returns**: BOM file path and component count

##### export_position_file
Export component positions for pick-and-place machines.

**Parameters**:
- `output_path` (string): CSV file output path
- `side` (string, optional): "front", "back", or "both"

**Returns**: Position file path and component count

#### Verification Tools (1 tool)

##### run_drc
Run Design Rule Check on the PCB.

**Parameters**:
- `report_path` (string, optional): Path for DRC report

**Returns**: DRC status, error count, warning count

#### Layout Tools (3 tools)

##### fill_zones
Fill copper zones on the PCB.

**Parameters**:
- `zone_names` (array, optional): Specific zones to fill (default: all)

**Returns**: Number of zones filled

##### get_track_info
Get information about tracks/traces on the PCB.

**Parameters**:
- `net_name` (string, optional): Filter by net name

**Returns**: Track count, total length, layer distribution

## Available Resources

### board://schematic
JSON list of all components from the board schematic

### board://info
General PCB board information and settings

### board://nets
JSON list of all nets (electrical connections) on the board

## Available Prompts

### simple_circuit
Get AI-powered layout guidance for simple circuits.

**Parameters**:
- `type` (string): Circuit type - "LED", "power_supply", "amplifier", etc.

**Returns**: Layout guidelines and best practices for the specified circuit type

## Project Structure

```
MCP-KiCad/
├── src/
│   └── mcp_kicad/
│       ├── __init__.py
│       ├── server/
│       │   ├── basic.py         # Basic MCP server (4 tools)
│       │   └── extended.py      # Extended MCP server (12 tools)
│       ├── client/
│       │   └── claude.py        # Claude AI client implementation
│       └── schemas/
│           └── tools.py         # Tool input/output schemas
├── tests/
│   ├── test_server.py          # Server unit tests
│   ├── test_fabrication.py     # Fabrication tools tests
│   └── ...                     # Additional test files
├── scripts/
│   └── smoke_test_entry_points.py
├── pyproject.toml              # Project configuration
├── requirements.txt            # Python dependencies
├── .env.example               # Example environment configuration
├── .env                       # Your API keys (not in git)
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI/CD
└── README.md                  # This file
```

## Known Limitations

### KiCad 9.x API Compatibility

**Via Width API Change:**
- `get_track_info` may return `None` for `total_length_mm` on boards with vias
- Caused by KiCad 9.x changing `PCB_VIA::GetWidth()` method signature
- **Impact**: Via length calculation may be unavailable
- **Workaround**: All other functionality works normally, fabrication exports unaffected

**Optional Fields:**
- Some `get_board_info` fields may return `None` depending on board configuration
- The server handles `None` values gracefully

**Testing Status:**
- Verified working with KiCad 9.0.5 Flatpak on real boards
- Test board: Olivia Control v0.2 (51 components, 2 layers, 56 nets, 38 vias)
- All 12 tools functional despite API warnings

For detailed information, see [FABRICATION.md](FABRICATION.md#via-width-api-change-kicad-9x).

## Troubleshooting

### "pcbnew module not available"

The server will run in mock mode. To fix:
- Make sure KiCad is installed
- Use KiCad's Python interpreter (see Installation step 5)
- Or link pcbnew to your virtual environment

### "No PCB board is currently open in KiCad"

- Open a PCB file in KiCad PCBNew before running the server
- Make sure you're in the PCB editor, not just the project manager

### "ANTHROPIC_API_KEY not found"

- Create `.env` file from `.env.example`
- Add your API key: `ANTHROPIC_API_KEY=sk-ant-...`
- Make sure `.env` is in the same directory as the scripts

### Component not found error

- List all components first: "List all components"
- Use exact reference designator (case-sensitive)
- Make sure components are on the PCB (not just schematic)

### Changes don't appear in KiCad

- Refresh the view in KiCad (F5)
- Check the console for error messages
- Verify the server is running and connected

### KiCad 9.x Via Width Warnings

**Symptom:**
```
/run/build/kicad/pcbnew/pcb_track.cpp(381): assert "false" failed in GetWidth()
```

**Explanation:**
- These warnings are **expected** on KiCad 9.x when processing boards with vias
- Caused by API changes in `PCB_VIA::GetWidth()` method signature
- Warnings appear during `get_track_info` operations

**Impact:**
- ⚠️ `get_track_info` may return `None` for `total_length_mm`
- ✅ All other tools work correctly
- ✅ Fabrication exports (Gerber, drill, BOM) are unaffected
- ✅ Component operations work normally

**Resolution:**
- No action needed - this is normal behavior on KiCad 9.x
- If you need total track length, use external tools like KiCad's built-in track length measurement
- The server handles these warnings gracefully and continues operation

**Testing:**
Successfully tested with Olivia Control v0.2 board (38 vias) - all 12 tools functional.

For more details, see [FABRICATION.md](FABRICATION.md#testing).

## Advanced Usage

### Using with xAI Grok (Alternative to Claude)

To use Grok instead of Claude:

1. Get an xAI API key from https://x.ai/
2. Adapt `src/mcp_kicad/client/claude.py`:

```python
# Replace Anthropic client with xAI client
from openai import OpenAI  # xAI uses OpenAI-compatible API

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)
```

3. Update API calls to use xAI's model name (e.g., "grok-beta")

### Running Server Standalone

The MCP server can be used by any MCP-compatible client:

```bash
mcp-kicad
```

Then connect with any MCP client using stdio transport.

### Extending with More Tools

Add new tools by:

1. Define tool in `list_tools()` handler
2. Implement tool function (e.g., `_route_traces()`)
3. Add tool call handler in `call_tool()`

Example tools to add:
- Route traces between components
- Apply design rules
- Generate copper pours
- Export Gerber files
- Import component footprints

## Security Considerations

- **API Keys**: Never commit `.env` file to version control
- **Auto-execution**: AI can modify your PCB directly - review changes carefully
- **Backups**: Always keep backups of your KiCad projects
- **Logging**: Tool calls are logged to console for transparency

## Development

### Testing in Mock Mode

Test without KiCad by running in mock mode:

```bash
mcp-kicad  # pcbnew not available → mock mode
mcp-kicad-client mcp-kicad
```

Mock mode returns simulated data for testing.

### Adding Logging

Add detailed logging for debugging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### Code Style

- Follow PEP 8 style guide
- Use type hints for all functions
- Document functions with docstrings
- Handle errors gracefully

## Testing

The project includes comprehensive test coverage with 135+ unit tests:

```bash
# Run tests locally
pip install -e .[dev]
pytest

# Run with coverage report
pytest --cov=mcp_kicad --cov-report=term-missing

# Run specific test files
pytest tests/test_server.py
pytest tests/test_fabrication.py
```

### CI/CD Pipeline

The project uses GitHub Actions for continuous integration:
- **Python Versions**: Tests run on Python 3.10, 3.11, and 3.12
- **Code Quality**: Black formatting and flake8 linting enforced
- **Coverage**: Minimum 40% coverage threshold required
- **Security**: Safety check for vulnerable dependencies

## Contributing

Contributions welcome! Areas for improvement:

- Support for more KiCad features (routing, DRC, etc.)
- Better error handling and recovery
- Unit tests and integration tests
- Support for other AI models
- Web-based UI
- Multi-board projects

## License

This project is free and open source. Use it however you like.

## Resources

- **KiCad**: https://www.kicad.org/
- **KiCad Python API**: https://docs.kicad.org/doxygen-python/namespacepcbnew.html
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Anthropic Claude**: https://www.anthropic.com/
- **xAI Grok**: https://x.ai/

## Support

For issues, questions, or suggestions:
- Check existing issues in the repository
- Read the Troubleshooting section above
- Review KiCad Python API documentation

## Acknowledgments

Built using:
- KiCad Python API (pcbnew)
- Anthropic's Model Context Protocol
- Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
- Python asyncio

---

**Happy PCB Designing with AI!** 🤖🔌
