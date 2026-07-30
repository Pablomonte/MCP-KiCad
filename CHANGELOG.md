# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Discover all `mcp_kicad` subpackages when building wheels.
- Add a clean-wheel CI smoke test for all three console entry points.
- Remove the unavailable `update_from_schematic` tool, which called a
  non-existent `kicad-cli pcb export update-from-sch` command.
- Correct CI test paths and align the documented coverage threshold.

### Changed

- Make packaged console commands the canonical server and client launch path.
- Consolidate quick-start and fabrication examples into the main documentation.
- Stop tracking generated coverage, packaging and fabrication artifacts.

### Planned
- Auto-routing support
- Web UI for visual interaction
- Component database integration (Octopart, LCSC)
- Multi-board project support
- Enhanced DRC with custom rules
- 3D model management

## [2.0.0] - 2025-11-08

### Added - Infrastructure Modernization (Phase 2)

#### Input Validation
- Pydantic schemas for all 12 tool inputs with custom validators
- Automatic data coercion and type checking
- Field-level validation with clear error messages
- Reference format validation (e.g., "R1", "U10")
- Rotation angle normalization (0, 90, 180, 270 degrees)
- Path security validation and traversal prevention
- Layer name validation against KiCad conventions

#### Structured Logging
- `structlog` integration for JSON-formatted logs
- Correlation ID tracking across all operations
- Operation-specific IDs for request tracing
- Automatic operation timing and duration tracking
- Context managers for automatic logging setup
- Configurable log levels, formats, and destinations
- Log rotation with size limits (10MB default)
- Log retention policies (7 days default)
- Platform-specific log directories (Linux/macOS/Windows)

#### Exception Hierarchy
- 15+ custom exception types with machine-readable error codes
- `KiCadMCPError` base class with structured error information
- Component-specific exceptions (`ComponentNotFoundError`, etc.)
- Validation exceptions (`InvalidCoordinateError`, etc.)
- I/O exceptions (`BoardFileNotFoundError`, etc.)
- KiCad API exceptions (`KiCadAPIError`, `DRCError`, etc.)
- Auto-suggestions for typos (using difflib)
- Remediation steps for agent-friendly error recovery
- Error severity levels (CRITICAL, HIGH, MEDIUM, LOW)
- Retry capability indicators

#### Configuration Management
- `pydantic-settings` for type-safe configuration
- Environment variable support with `MCP_KICAD_` prefix
- `.env` file loading with validation
- 40+ configurable settings with sensible defaults
- Setting categories: KiCad integration, server, board constraints, logging, visual verification, security, performance
- Path validation and auto-creation
- Platform-specific defaults (log directories, etc.)
- Security whitelist for allowed project paths

#### Package Structure
- Modern src-layout: `src/mcp_kicad/` structure
- Proper package hierarchy with `__init__.py` files
- Absolute imports throughout (`from mcp_kicad.module import ...`)
- Subpackages: `server/`, `schemas/`, `utils/`
- Clean separation of concerns

#### Testing Infrastructure
- pytest configuration with fixtures in `tests/conftest.py`
- Mock fixtures: `mock_pcbnew`, `mock_board`, `mock_footprint`
- Test board creation fixtures
- Settings and logger mocks
- Singleton reset between tests
- Sample data fixtures (components, nets)
- Virtual environment setup for dependency isolation

#### Development Tools
- `pyproject.toml` for modern project configuration
- Dependency specification with version constraints
- Entry points for CLI commands (`mcp-kicad`, `mcp-kicad-basic`)
- `.env.example` with comprehensive documentation (137 lines)
- Development dependencies separation

### Changed

#### Server Implementation
- Updated `basic.py` with full validation and logging integration
- Updated `extended.py` with validation for all 12 tools
- Replaced generic exception handling with specific exception types
- Added operation context managers for automatic timing
- Integrated settings from config module
- Updated imports to use new package structure

#### Error Handling
- Validation errors now return structured `ErrorResponse` objects
- Error messages include error codes, severity, and remediation steps
- Component not found errors suggest similar components
- Path validation prevents directory traversal attacks
- Board file errors include troubleshooting steps

### Technical Details
- **New Dependencies**: `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`, `structlog>=24.0.0`
- **Python Version**: 3.10+ (unchanged)
- **Logging Format**: JSON or human-readable (configurable)
- **Configuration**: Environment variables + .env file
- **Testing**: pytest with comprehensive fixtures

### Migration Guide

For existing installations:

1. **Update dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -e .
   ```

2. **Create configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Update imports** (if using as library):
   ```python
   # Old
   from server.basic import KiCadBasicServer

   # New
   from mcp_kicad.server.basic import KiCadBasicServer
   ```

4. **Check logs**: New location at `~/.local/share/mcp-kicad/logs/` (Linux)

### Breaking Changes
- Package structure changed to src-layout (imports must be updated)
- Configuration now requires `.env` file or environment variables
- Log output format changed (structured logging)
- Error responses now use `ErrorResponse` schema

## [1.0.0] - 2025-10-21

### Added

#### Core Features
- Complete MCP server implementation for KiCad PCB design
- AI client using Claude 3.5 Sonnet for natural language interaction
- 12 comprehensive tools for PCB design and fabrication
- Async/await architecture throughout
- Mock mode for testing without KiCad

#### Fabrication Tools
- `export_gerber`: Export Gerber files (RS-274X format, all standard layers)
- `export_drill_files`: Export drill files (Excellon format, PTH/NPTH)
- `export_fabrication_package`: Complete fabrication package as ZIP
- `export_bom`: Bill of Materials export (CSV format)
- `export_position_file`: Pick-and-place positions (CSV format)

#### Verification & Layout Tools
- `run_drc`: Design Rule Check integration
- `fill_zones`: Copper zone management
- `get_track_info`: Track/trace information

#### Basic Tools
- `place_component`: Precise component placement
- `list_components`: Component enumeration with positions
- `read_netlist`: Netlist information
- `get_board_info`: Board specifications

#### Flatpak Integration
- Full KiCad 9.0.5 Flatpak support
- `run_with_flatpak.sh`: Launcher script with filesystem access
- `kicad_flatpak_setup.sh`: Automatic dependency installer
- `check_kicad.py`: Environment checker with auto-detection

#### Testing
- 20 comprehensive tests covering all tools
- `test_server.py`: Basic server tests
- `test_fabrication.py`: Extended fabrication tests
- 100% test pass rate

#### Documentation
- `README.md` (11KB): Complete user guide
- `FABRICATION.md` (13KB): Fabrication tools documentation
- Quick-start guide in `README.md`
- Fabrication workflows in `FABRICATION.md`
- `CONTRIBUTING.md`: Development guidelines

#### Example Project
- Olivia Control v0.2 fabrication files included
- Complete Gerber set, drill files, BOM, and position file
- Ready-to-manufacture ZIP package

### Technical Details
- **Compatibility**: KiCad 9.0.5, Python 3.10+
- **AI Model**: Claude 3.5 Sonnet
- **Protocol**: Model Context Protocol (MCP) 1.0+
- **Platforms**: Linux (primary), macOS/Windows (untested)

### Known Limitations
- DRC integration is basic (requires KiCad 7+ API for full support)
- Auto-routing not yet implemented
- Single board per session
- No direct 3D model management

---

## Version History

### Release Notes - v1.0.0

First stable release of KiCad MCP Integration.

**Highlights:**
- Production-ready AI-assisted PCB design
- Complete fabrication workflow
- Flatpak support for KiCad 9.0.5
- Comprehensive documentation
- 20/20 tests passing

**Use Cases:**
- AI-assisted PCB design and layout
- Automated fabrication file generation
- Manufacturing preparation
- Component placement optimization
- PCB design education

**Tested With:**
- Olivia Control v0.2 (51 components, 90x100mm, 2-layer board)
- KiCad 9.0.5 Flatpak on Linux Mint 22.2
- Fabrication compatibility: JLCPCB, PCBWay, OSH Park

---

## Links

- **Repository**: https://github.com/Pablomonte/MCP-KiCad
- **Issues**: https://github.com/Pablomonte/MCP-KiCad/issues
- **Releases**: https://github.com/Pablomonte/MCP-KiCad/releases

[Unreleased]: https://github.com/Pablomonte/MCP-KiCad/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/Pablomonte/MCP-KiCad/releases/tag/v2.0.0
[1.0.0]: https://github.com/Pablomonte/MCP-KiCad/releases/tag/v1.0.0
