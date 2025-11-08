"""
Pytest configuration and fixtures for MCP-KiCad tests.

Provides common fixtures for mocking KiCad, creating test boards,
and setting up test environments.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path


@pytest.fixture
def mock_pcbnew():
    """
    Mock pcbnew module for testing without KiCad installation.

    Returns:
        MagicMock: Mocked pcbnew module with common methods
    """
    mock_module = MagicMock()

    # Mock common classes and methods
    mock_module.GetBoard.return_value = None
    mock_module.VECTOR2I = lambda x, y: MagicMock(x=x, y=y)
    mock_module.PLOT_CONTROLLER = MagicMock
    mock_module.EXCELLON_WRITER = MagicMock
    mock_module.ZONE_FILLER = MagicMock

    # Mock plot formats
    mock_module.PLOT_FORMAT_GERBER = 0
    mock_module.PLOT_FORMAT_PNG = 1

    # Mock layers
    mock_module.F_Cu = 0
    mock_module.B_Cu = 31

    with patch.dict(sys.modules, {'pcbnew': mock_module}):
        yield mock_module


@pytest.fixture
def mock_board():
    """
    Create a mock board with common methods and properties.

    Returns:
        MagicMock: Mocked PCB board
    """
    board = MagicMock()

    # Board properties
    board.GetFileName.return_value = "test_board.kicad_pcb"

    # Board dimensions (100mm x 80mm)
    bbox = MagicMock()
    bbox.GetWidth.return_value = 100 * 1e6  # nm
    bbox.GetHeight.return_value = 80 * 1e6  # nm
    board.GetBoardEdgesBoundingBox.return_value = bbox

    # Layer count
    board.GetCopperLayerCount.return_value = 2

    # Empty footprints by default
    board.GetFootprints.return_value = []

    # Empty netlist by default
    netinfo = MagicMock()
    netinfo.NetsByName.return_value = {}
    board.GetNetInfo.return_value = netinfo

    # Layer ID mapping
    board.GetLayerID.return_value = 0

    # Zones
    board.Zones.return_value = []

    # Tracks
    board.GetTracks.return_value = []

    return board


@pytest.fixture
def mock_footprint():
    """
    Create a mock footprint/component.

    Returns:
        MagicMock: Mocked footprint
    """
    fp = MagicMock()
    fp.GetReference.return_value = "R1"
    fp.GetValue.return_value = "10k"
    fp.GetPosition.return_value = MagicMock(x=10*1e6, y=20*1e6)  # nm
    fp.GetOrientationDegrees.return_value = 0.0
    fp.GetLayerName.return_value = "F.Cu"
    fp.GetLayer.return_value = 0  # F_Cu

    # FPID for footprint library reference
    fpid = MagicMock()
    fpid.GetLibItemName.return_value = "R_0805_2012Metric"
    fp.GetFPID.return_value = fpid

    return fp


@pytest.fixture
def temp_board_file(tmp_path):
    """
    Create a temporary KiCad board file for testing.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path: Path to temporary board file
    """
    board_file = tmp_path / "test.kicad_pcb"
    board_file.write_text(
        "(kicad_pcb (version 20221018) (generator pcbnew)\n"
        "  (general\n"
        "    (thickness 1.6)\n"
        "  )\n"
        "  (layers\n"
        "    (0 \"F.Cu\" signal)\n"
        "    (31 \"B.Cu\" signal)\n"
        "  )\n"
        ")\n"
    )
    return board_file


@pytest.fixture
def temp_project_dir(tmp_path):
    """
    Create a temporary project directory with basic structure.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path: Path to project directory
    """
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create subdirectories
    (project_dir / "gerber").mkdir()
    (project_dir / "drill").mkdir()
    (project_dir / "exports").mkdir()

    return project_dir


@pytest.fixture
def mock_settings():
    """
    Create mock settings for testing.

    Returns:
        Settings: Test settings instance
    """
    from mcp_kicad.config import Settings

    settings = Settings(
        log_level="DEBUG",
        enable_debug=True,
        enable_mock_mode=True,
        log_to_file=False,  # Don't write files during tests
        log_to_console=False,  # Don't spam console during tests
    )
    return settings


@pytest.fixture
def mock_logger():
    """
    Create a mock logger for testing.

    Returns:
        MagicMock: Mocked structlog logger
    """
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.exception = MagicMock()
    return logger


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch):
    """
    Reset singleton instances between tests and disable file logging.

    This ensures tests don't affect each other through shared state.
    """
    # Disable file logging for tests to prevent resource warnings
    monkeypatch.setenv("MCP_KICAD_LOG_TO_FILE", "false")
    monkeypatch.setenv("MCP_KICAD_LOG_TO_CONSOLE", "false")

    # Reset settings singleton
    from mcp_kicad import config
    config._settings = None

    yield

    # Cleanup after test
    config._settings = None


@pytest.fixture
def sample_components():
    """
    Create sample component data for testing.

    Returns:
        list: List of component dictionaries
    """
    return [
        {
            "reference": "R1",
            "value": "10k",
            "x_mm": 10.0,
            "y_mm": 20.0,
            "rotation_deg": 0.0,
            "layer": "F.Cu"
        },
        {
            "reference": "C1",
            "value": "100nF",
            "x_mm": 20.0,
            "y_mm": 20.0,
            "rotation_deg": 90.0,
            "layer": "F.Cu"
        },
        {
            "reference": "U1",
            "value": "LM358",
            "x_mm": 30.0,
            "y_mm": 30.0,
            "rotation_deg": 0.0,
            "layer": "F.Cu"
        },
    ]


@pytest.fixture
def sample_nets():
    """
    Create sample netlist data for testing.

    Returns:
        list: List of net dictionaries
    """
    return [
        {"name": "GND", "code": 0},
        {"name": "+5V", "code": 1},
        {"name": "+3V3", "code": 2},
        {"name": "SDA", "code": 3},
        {"name": "SCL", "code": 4},
    ]
