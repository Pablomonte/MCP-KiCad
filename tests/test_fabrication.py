#!/usr/bin/env python3
"""
Test suite for KiCad MCP Server Extended fabrication tools.

Tests all fabrication, verification, and layout tools in mock mode with Phase 2 features.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from mcp_kicad.server import KiCadMCPServerExtended


# ============================================================================
# BASIC TOOLS
# ============================================================================

@pytest.mark.asyncio
async def test_list_components():
    """Test list_components returns proper structure"""
    server = KiCadMCPServerExtended()
    result = await server._list_components()

    assert result["status"] == "mock"
    assert "components" in result
    assert len(result["components"]) > 0


@pytest.mark.asyncio
async def test_get_board_info():
    """Test get_board_info returns board specifications"""
    server = KiCadMCPServerExtended()
    result = await server._get_board_info()

    assert result["status"] == "mock"
    assert "board_name" in result
    assert "size" in result


@pytest.mark.asyncio
async def test_read_netlist():
    """Test read_netlist returns net information"""
    server = KiCadMCPServerExtended()
    result = await server._read_netlist()

    assert result["status"] == "mock"
    assert "nets" in result


@pytest.mark.asyncio
async def test_place_component():
    """Test place_component with valid inputs"""
    server = KiCadMCPServerExtended()
    result = await server._place_component("R1", 10.0, 20.0, 0.0)

    assert result["status"] == "mock"
    assert "R1" in result["message"]


# ============================================================================
# FABRICATION TOOLS
# ============================================================================

@pytest.mark.asyncio
async def test_export_gerber():
    """Test Gerber file export"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        gerber_dir = Path(temp_dir) / "gerber"
        result = await server._export_gerber(str(gerber_dir))

        assert result["status"] == "mock"
        assert "files" in result
        assert len(result["files"]) > 0


@pytest.mark.asyncio
async def test_export_drill_files():
    """Test drill file export (separate PTH/NPTH)"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        drill_dir = Path(temp_dir) / "drill"
        result = await server._export_drill_files(str(drill_dir))

        assert result["status"] == "mock"
        assert "files" in result
        assert "merged" in result
        assert result["merged"] is False


@pytest.mark.asyncio
async def test_export_drill_files_merged():
    """Test drill file export (merged PTH/NPTH)"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        drill_dir = Path(temp_dir) / "drill_merged"
        result = await server._export_drill_files(str(drill_dir), merge_pth_npth=True)

        assert result["status"] == "mock"
        assert result["merged"] is True


@pytest.mark.asyncio
async def test_export_bom():
    """Test BOM export"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        bom_file = Path(temp_dir) / "bom.csv"
        result = await server._export_bom(str(bom_file))

        assert result["status"] == "mock"


@pytest.mark.asyncio
async def test_export_position_file():
    """Test position file export"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        pos_file = Path(temp_dir) / "position.csv"
        result = await server._export_position_file(str(pos_file))

        assert result["status"] == "mock"


@pytest.mark.asyncio
async def test_export_fabrication_package():
    """Test complete fabrication package export"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        result = await server._export_fabrication_package(str(temp_dir), "generic")

        assert result["status"] == "success"
        assert "data" in result
        assert result["data"]["manufacturer"] == "generic"


@pytest.mark.asyncio
async def test_export_fabrication_package_jlcpcb():
    """Test fabrication package with manufacturer preset"""
    server = KiCadMCPServerExtended()

    with tempfile.TemporaryDirectory() as temp_dir:
        result = await server._export_fabrication_package(str(temp_dir), "jlcpcb")

        assert result["status"] == "success"
        assert result["data"]["manufacturer"] == "jlcpcb"


# ============================================================================
# VERIFICATION TOOLS
# ============================================================================

@pytest.mark.asyncio
async def test_run_drc_all():
    """Test DRC with all severity levels"""
    server = KiCadMCPServerExtended()
    result = await server._run_drc("all")

    assert result["status"] == "mock"
    assert "error_count" in result
    assert "warning_count" in result


@pytest.mark.asyncio
async def test_run_drc_error_only():
    """Test DRC with errors only"""
    server = KiCadMCPServerExtended()
    result = await server._run_drc("error")

    assert result["status"] == "mock"


# ============================================================================
# LAYOUT TOOLS
# ============================================================================

@pytest.mark.asyncio
async def test_fill_zones_all():
    """Test filling all zones"""
    server = KiCadMCPServerExtended()
    result = await server._fill_zones()

    assert result["status"] == "mock"
    assert "count" in result or "data" in result


@pytest.mark.asyncio
async def test_fill_zones_specific():
    """Test filling specific zones"""
    server = KiCadMCPServerExtended()
    result = await server._fill_zones(zone_names=["GND"])

    assert result["status"] == "mock"


@pytest.mark.asyncio
async def test_get_track_info_all():
    """Test getting all track information"""
    server = KiCadMCPServerExtended()
    result = await server._get_track_info()

    assert result["status"] == "mock"
    assert "count" in result or "data" in result


@pytest.mark.asyncio
async def test_get_track_info_filtered():
    """Test getting track info filtered by net"""
    server = KiCadMCPServerExtended()
    result = await server._get_track_info(net_name="VCC")

    assert result["status"] == "mock"


# ============================================================================
# PROMPTS
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_guidance_led():
    """Test circuit guidance for LED"""
    server = KiCadMCPServerExtended()
    components = await server._list_components()
    guidance = server._get_circuit_guidance("LED", components)

    assert isinstance(guidance, str)
    assert len(guidance) > 0


@pytest.mark.asyncio
async def test_circuit_guidance_power():
    """Test circuit guidance for power supply"""
    server = KiCadMCPServerExtended()
    components = await server._list_components()
    guidance = server._get_circuit_guidance("power_supply", components)

    assert isinstance(guidance, str)
    assert "power" in guidance.lower()


@pytest.mark.asyncio
async def test_fabrication_checklist():
    """Test fabrication checklist generation"""
    server = KiCadMCPServerExtended()
    checklist = await server._get_fabrication_checklist()

    assert isinstance(checklist, str)
    assert "DRC" in checklist
    assert "Gerber" in checklist


# ============================================================================
# ERROR HANDLING
# ============================================================================

@pytest.mark.asyncio
async def test_place_component_with_invalid_reference():
    """Test component placement with invalid reference (mock mode)"""
    server = KiCadMCPServerExtended()
    result = await server._place_component("INVALID_REF", 0, 0)

    # In mock mode, should still return mock response
    assert result["status"] == "mock"


@pytest.mark.asyncio
async def test_get_track_info_nonexistent_net():
    """Test track info with non-existent net filter"""
    server = KiCadMCPServerExtended()
    result = await server._get_track_info(net_name="NON_EXISTENT_NET")

    assert result["status"] == "mock"


# ============================================================================
# SERVER INITIALIZATION
# ============================================================================

@pytest.mark.asyncio
async def test_server_initialization():
    """Test extended server initializes correctly"""
    server = KiCadMCPServerExtended()

    assert hasattr(server, 'logger')
    assert hasattr(server, 'settings')
    assert hasattr(server, 'server')
    assert server.board is None  # No board in mock mode
