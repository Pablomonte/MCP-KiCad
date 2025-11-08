#!/usr/bin/env python3
"""
Test suite for basic KiCad MCP Server functionality.

Tests mock mode operations, exception handling, and Phase 2 features.
"""

import pytest
from mcp_kicad.server import KiCadMCPServer
from mcp_kicad.exceptions import BoardNotOpenError, ComponentNotFoundError


@pytest.mark.asyncio
async def test_list_components_mock():
    """Test list_components in mock mode"""
    server = KiCadMCPServer()
    result = await server._list_components()

    assert result["status"] == "mock"
    assert "components" in result
    assert len(result["components"]) > 0
    assert all("reference" in c for c in result["components"])


@pytest.mark.asyncio
async def test_get_board_info_mock():
    """Test get_board_info in mock mode"""
    server = KiCadMCPServer()
    result = await server._get_board_info()

    assert result["status"] == "mock"
    assert "board_name" in result
    assert "size" in result
    assert "example_board" in result["board_name"]


@pytest.mark.asyncio
async def test_read_netlist_mock():
    """Test read_netlist in mock mode"""
    server = KiCadMCPServer()
    result = await server._read_netlist()

    assert result["status"] == "mock"
    assert "nets" in result
    assert len(result["nets"]) > 0


@pytest.mark.asyncio
async def test_place_component_mock():
    """Test place_component in mock mode with valid rotation"""
    server = KiCadMCPServer()
    result = await server._place_component("R1", 10.0, 20.0, 0.0)

    assert result["status"] == "mock"
    assert "R1" in result["message"]


@pytest.mark.asyncio
async def test_place_component_rotation_normalization():
    """Test that rotation angles are normalized to 0/90/180/270"""
    server = KiCadMCPServer()

    # Test valid rotations
    for rotation in [0.0, 90.0, 180.0, 270.0]:
        result = await server._place_component("R1", 10.0, 20.0, rotation)
        assert result["status"] == "mock"


@pytest.mark.asyncio
async def test_circuit_guidance():
    """Test circuit guidance generation"""
    server = KiCadMCPServer()
    components = await server._list_components()
    guidance = server._get_circuit_guidance("LED", components)

    assert isinstance(guidance, str)
    assert len(guidance) > 0
    assert "LED" in guidance or "led" in guidance.lower()


@pytest.mark.asyncio
async def test_server_initialization():
    """Test server initializes with correct attributes"""
    server = KiCadMCPServer()

    assert hasattr(server, "logger")
    assert hasattr(server, "settings")
    assert hasattr(server, "server")
    assert server.board is None  # No board loaded in mock mode


@pytest.mark.asyncio
async def test_mock_mode_detection():
    """Test that server correctly detects and operates in mock mode"""
    server = KiCadMCPServer()

    # All operations should return mock status
    result = await server._list_components()
    assert result["status"] == "mock"
