#!/usr/bin/env python3
"""
KiCad MCP Server - Provides AI access to KiCad PCB design via MCP
"""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    Prompt,
    PromptMessage,
    GetPromptResult,
)

try:
    import pcbnew
except ImportError:
    pcbnew = None
    print(
        "Warning: pcbnew module not available. Server will run in mock mode.",
        file=sys.stderr,
    )


class KiCadMCPServer:
    """MCP Server for KiCad automation"""

    def __init__(self):
        self.server = Server("kicad-mcp-server")
        self.board: Optional[Any] = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Register MCP protocol handlers"""

        # List available tools
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="place_component",
                    description="Move a component to a specific position on the PCB board",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "reference": {
                                "type": "string",
                                "description": "Component reference designator (e.g., 'R1', 'U1', 'C5')",
                            },
                            "x_mm": {
                                "type": "number",
                                "description": "X position in millimeters",
                            },
                            "y_mm": {
                                "type": "number",
                                "description": "Y position in millimeters",
                            },
                            "rotation_deg": {
                                "type": "number",
                                "description": "Rotation angle in degrees (default: 0)",
                                "default": 0,
                            },
                        },
                        "required": ["reference", "x_mm", "y_mm"],
                    },
                ),
                Tool(
                    name="read_netlist",
                    description="Read the netlist from the current PCB board, returning component and net information",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="list_components",
                    description="List all components (footprints) on the PCB board with their current positions",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="get_board_info",
                    description="Get general information about the PCB board (size, layer count, etc.)",
                    inputSchema={"type": "object", "properties": {}},
                ),
            ]

        # Handle tool calls
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent]:
            try:
                if name == "place_component":
                    result = await self._place_component(
                        arguments["reference"],
                        arguments["x_mm"],
                        arguments["y_mm"],
                        arguments.get("rotation_deg", 0),
                    )
                elif name == "read_netlist":
                    result = await self._read_netlist()
                elif name == "list_components":
                    result = await self._list_components()
                elif name == "get_board_info":
                    result = await self._get_board_info()
                else:
                    result = {"error": f"Unknown tool: {name}"}

                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

        # List available resources
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            return [
                Resource(
                    uri="board://schematic",
                    name="PCB Schematic Components",
                    mimeType="application/json",
                    description="List of all components from the board schematic",
                ),
                Resource(
                    uri="board://info",
                    name="PCB Board Information",
                    mimeType="application/json",
                    description="General PCB board information and settings",
                ),
            ]

        # Handle resource reads
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            if uri == "board://schematic":
                components = await self._list_components()
                return json.dumps(components, indent=2)
            elif uri == "board://info":
                info = await self._get_board_info()
                return json.dumps(info, indent=2)
            else:
                raise ValueError(f"Unknown resource: {uri}")

        # List available prompts
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            return [
                Prompt(
                    name="simple_circuit",
                    description="Get guidance for placing components in a simple circuit layout",
                    arguments=[
                        {
                            "name": "type",
                            "description": "Type of circuit (e.g., 'LED', 'power_supply', 'amplifier')",
                            "required": False,
                        }
                    ],
                )
            ]

        # Handle prompt requests
        @self.server.get_prompt()
        async def get_prompt(
            name: str, arguments: Optional[Dict[str, str]] = None
        ) -> GetPromptResult:
            if name == "simple_circuit":
                circuit_type = arguments.get("type", "LED") if arguments else "LED"

                components = await self._list_components()

                guidance = self._get_circuit_guidance(circuit_type, components)

                return GetPromptResult(
                    description=f"Layout guidance for {circuit_type} circuit",
                    messages=[
                        PromptMessage(
                            role="user", content=TextContent(type="text", text=guidance)
                        )
                    ],
                )
            else:
                raise ValueError(f"Unknown prompt: {name}")

    def _get_circuit_guidance(self, circuit_type: str, components: Dict) -> str:
        """Generate layout guidance for different circuit types"""

        base_text = (
            f"Current components on board:\n{json.dumps(components, indent=2)}\n\n"
        )

        if circuit_type.lower() == "led":
            return (
                base_text
                + """
Layout guidance for LED circuit:
1. Place LED (D1 or similar) in a central location
2. Place current-limiting resistor (R1) close to LED anode
3. Power connector should be on the edge of board
4. Keep traces short and direct
5. Consider polarity markings on silkscreen

Typical spacing:
- LED to resistor: 5-10mm
- Components to board edge: minimum 3mm
"""
            )
        elif circuit_type.lower() in ["power_supply", "power"]:
            return (
                base_text
                + """
Layout guidance for power supply:
1. Place input connector on one edge
2. Group filtering capacitors near voltage regulator
3. Place output connector on opposite edge
4. Keep high-current traces wide and short
5. Separate input and output grounds initially, join at one point

Critical spacing:
- Input caps to regulator: < 10mm
- Output caps to load: < 15mm
- Heatsink clearance: check datasheet
"""
            )
        else:
            return (
                base_text
                + f"""
Layout guidance for {circuit_type} circuit:
1. Group related components together
2. Place connectors on board edges
3. Keep signal paths short
4. Place decoupling capacitors close to IC power pins
5. Consider signal flow from input to output
6. Maintain minimum clearances per design rules

Standard practices:
- Decoupling caps to IC: < 5mm
- Components to board edge: > 3mm
- High-frequency components: minimize trace length
"""
            )

    async def _place_component(
        self, reference: str, x_mm: float, y_mm: float, rotation_deg: float = 0
    ) -> Dict:
        """Place/move a component on the board"""

        if pcbnew is None:
            return {
                "status": "mock",
                "message": f"Mock: Would place {reference} at ({x_mm}, {y_mm}) mm, rotation {rotation_deg}°",
            }

        try:
            # Load board if not loaded
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is currently open in KiCad"}

            # Find the footprint
            footprint = None
            for fp in self.board.GetFootprints():
                if fp.GetReference() == reference:
                    footprint = fp
                    break

            if footprint is None:
                available = [fp.GetReference() for fp in self.board.GetFootprints()]
                return {
                    "error": f"Component '{reference}' not found",
                    "available_components": available,
                }

            # Convert mm to KiCad internal units (nanometers)
            x_nm = int(x_mm * 1e6)
            y_nm = int(y_mm * 1e6)

            # Set position
            footprint.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))

            # Set rotation (KiCad uses decidegrees internally)
            rotation_decideg = rotation_deg * 10
            footprint.SetOrientationDegrees(rotation_deg)

            # Refresh the board
            pcbnew.Refresh()

            return {
                "status": "success",
                "reference": reference,
                "position": {"x_mm": x_mm, "y_mm": y_mm},
                "rotation_deg": rotation_deg,
                "message": f"Placed {reference} at ({x_mm}, {y_mm}) mm with {rotation_deg}° rotation",
            }

        except Exception as e:
            return {"error": f"Failed to place component: {str(e)}"}

    async def _list_components(self) -> Dict:
        """List all components on the board"""

        if pcbnew is None:
            return {
                "status": "mock",
                "components": [
                    {
                        "reference": "R1",
                        "value": "10k",
                        "x_mm": 10,
                        "y_mm": 20,
                        "rotation_deg": 0,
                    },
                    {
                        "reference": "C1",
                        "value": "100nF",
                        "x_mm": 20,
                        "y_mm": 20,
                        "rotation_deg": 90,
                    },
                    {
                        "reference": "U1",
                        "value": "LM358",
                        "x_mm": 30,
                        "y_mm": 30,
                        "rotation_deg": 0,
                    },
                ],
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is currently open in KiCad"}

            components = []
            for fp in self.board.GetFootprints():
                pos = fp.GetPosition()
                components.append(
                    {
                        "reference": fp.GetReference(),
                        "value": fp.GetValue(),
                        "x_mm": pos.x / 1e6,  # Convert from nm to mm
                        "y_mm": pos.y / 1e6,
                        "rotation_deg": fp.GetOrientationDegrees(),
                        "layer": fp.GetLayerName(),
                    }
                )

            return {
                "status": "success",
                "count": len(components),
                "components": components,
            }

        except Exception as e:
            return {"error": f"Failed to list components: {str(e)}"}

    async def _read_netlist(self) -> Dict:
        """Read netlist information from the board"""

        if pcbnew is None:
            return {
                "status": "mock",
                "nets": [
                    {"name": "GND", "pads": 5},
                    {"name": "+5V", "pads": 3},
                    {"name": "LED_OUT", "pads": 2},
                ],
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is currently open in KiCad"}

            nets = []
            netinfo = self.board.GetNetInfo()

            for net_name, net in netinfo.NetsByName().items():
                if net_name:  # Skip empty net names
                    nets.append(
                        {
                            "name": net_name,
                            "code": net.GetNetCode(),
                        }
                    )

            return {"status": "success", "count": len(nets), "nets": nets}

        except Exception as e:
            return {"error": f"Failed to read netlist: {str(e)}"}

    async def _get_board_info(self) -> Dict:
        """Get general board information"""

        if pcbnew is None:
            return {
                "status": "mock",
                "board_name": "example_board",
                "size": {"width_mm": 100, "height_mm": 80},
                "layers": 2,
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is currently open in KiCad"}

            bbox = self.board.GetBoardEdgesBoundingBox()

            return {
                "status": "success",
                "board_name": self.board.GetFileName(),
                "size": {
                    "width_mm": bbox.GetWidth() / 1e6,
                    "height_mm": bbox.GetHeight() / 1e6,
                },
                "layer_count": self.board.GetCopperLayerCount(),
                "component_count": len(list(self.board.GetFootprints())),
            }

        except Exception as e:
            return {"error": f"Failed to get board info: {str(e)}"}

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    server = KiCadMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
