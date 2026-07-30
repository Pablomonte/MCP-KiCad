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
from pydantic import ValidationError

from mcp_kicad.config import get_settings
from mcp_kicad.log import (
    get_logger,
    operation_context,
    set_correlation_id,
    setup_logging,
)
from mcp_kicad.exceptions import (
    BoardNotOpenError,
    ComponentNotFoundError,
    InvalidCoordinateError,
    KiCadAPIError,
    KiCadNotAvailableError,
    ValidationError as MCPValidationError,
)
from mcp_kicad.schemas import (
    PlaceComponentInput,
    ErrorResponse,
)

try:
    import pcbnew
except ImportError:
    pcbnew = None
    # Don't print here - will be logged properly in __init__


class KiCadMCPServer:
    """MCP Server for KiCad automation"""

    def __init__(self):
        # Load settings
        self.settings = get_settings()

        # Setup logging
        setup_logging(
            log_level=self.settings.log_level,
            log_dir=self.settings.log_dir,
            log_to_file=self.settings.log_to_file,
            log_to_console=self.settings.log_to_console,
            json_format=self.settings.log_json,
        )
        self.logger = get_logger(__name__)

        # Log initialization
        self.logger.info(
            "server_initializing",
            server_type="basic",
            kicad_available=pcbnew is not None,
        )

        if pcbnew is None:
            self.logger.warning(
                "pcbnew_unavailable",
                message="KiCad pcbnew module not available - running in mock mode",
            )

        # Initialize MCP server
        self.server = Server(self.settings.server_name)
        self.board: Optional[Any] = None
        self._setup_handlers()

        self.logger.info("server_initialized", server_name=self.settings.server_name)

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
            # Set correlation ID for request tracking
            set_correlation_id()

            self.logger.info(
                "tool_called", tool_name=name, has_arguments=bool(arguments)
            )

            try:
                if name == "place_component":
                    # Validate input with Pydantic
                    try:
                        validated = PlaceComponentInput(**arguments)
                    except ValidationError as e:
                        self.logger.warning(
                            "validation_failed", tool=name, errors=e.errors()
                        )
                        error_response = ErrorResponse(
                            error="Input validation failed",
                            error_code="VALIDATION_ERROR",
                            severity="medium",
                            remediation_steps=[
                                "Check input parameters match schema",
                                "Review tool documentation for valid formats",
                                f"Validation errors: {e.errors()}",
                            ],
                            context={"validation_errors": e.errors()},
                            can_retry=True,
                        )
                        return [
                            TextContent(
                                type="text",
                                text=error_response.model_dump_json(indent=2),
                            )
                        ]

                    # Call with validated data
                    result = await self._place_component(
                        validated.reference,
                        validated.x_mm,
                        validated.y_mm,
                        validated.rotation_deg,
                    )
                elif name == "read_netlist":
                    result = await self._read_netlist()
                elif name == "list_components":
                    result = await self._list_components()
                elif name == "get_board_info":
                    result = await self._get_board_info()
                else:
                    self.logger.error("unknown_tool", tool_name=name)
                    result = {"error": f"Unknown tool: {name}"}

                self.logger.info(
                    "tool_completed",
                    tool_name=name,
                    status=result.get("status", "unknown"),
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except (
                BoardNotOpenError,
                ComponentNotFoundError,
                InvalidCoordinateError,
                KiCadAPIError,
            ) as e:
                # Structured errors
                self.logger.error(
                    "tool_error",
                    tool_name=name,
                    error_type=type(e).__name__,
                    error_code=e.error_code,
                )
                return [
                    TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))
                ]

            except Exception as e:
                # Unexpected errors
                self.logger.exception(
                    "tool_unexpected_error", tool_name=name, error=str(e)
                )
                error = KiCadAPIError(name, str(e))
                return [
                    TextContent(type="text", text=json.dumps(error.to_dict(), indent=2))
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
            return base_text + """
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
        elif circuit_type.lower() in ["power_supply", "power"]:
            return base_text + """
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
        else:
            return base_text + f"""
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

    async def _place_component(
        self, reference: str, x_mm: float, y_mm: float, rotation_deg: float = 0
    ) -> Dict:
        """
        Place/move a component on the board.

        Args:
            reference: Component reference designator (e.g., 'R1', 'U1')
            x_mm: X coordinate in millimeters
            y_mm: Y coordinate in millimeters
            rotation_deg: Rotation angle in degrees (0, 90, 180, 270)

        Returns:
            Operation result dictionary

        Raises:
            BoardNotOpenError: If no board is open
            ComponentNotFoundError: If component not found
            KiCadAPIError: If KiCad API call fails
        """
        with operation_context(
            "place_component",
            logger=self.logger,
            reference=reference,
            x_mm=x_mm,
            y_mm=y_mm,
            rotation_deg=rotation_deg,
        ) as ctx:
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "message": f"Mock: Would place {reference} at ({x_mm}, {y_mm}) mm, rotation {rotation_deg}°",
                }

            # Load board
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Find the footprint
            footprint = None
            for fp in self.board.GetFootprints():
                if fp.GetReference() == reference:
                    footprint = fp
                    break

            if footprint is None:
                available = [fp.GetReference() for fp in self.board.GetFootprints()]
                raise ComponentNotFoundError(reference, available)

            ctx.log_progress("component_found", footprint=str(footprint.GetFPID()))

            # Convert mm to KiCad internal units (nanometers)
            x_nm = int(x_mm * 1e6)
            y_nm = int(y_mm * 1e6)

            # Set position
            try:
                footprint.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
                footprint.SetOrientationDegrees(rotation_deg)
                pcbnew.Refresh()
            except Exception as e:
                raise KiCadAPIError("SetPosition/SetOrientation", str(e))

            ctx.log_progress("component_placed")

            return {
                "status": "success",
                "reference": reference,
                "position": {"x_mm": x_mm, "y_mm": y_mm},
                "rotation_deg": rotation_deg,
                "message": f"Placed {reference} at ({x_mm}, {y_mm}) mm with {rotation_deg}° rotation",
            }

    async def _list_components(self) -> Dict:
        """List all components on the board with their current positions."""
        with operation_context("list_components", logger=self.logger) as ctx:
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
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

            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            components = []
            try:
                for fp in self.board.GetFootprints():
                    pos = fp.GetPosition()
                    components.append(
                        {
                            "reference": fp.GetReference(),
                            "value": fp.GetValue(),
                            "x_mm": pos.x / 1e6,
                            "y_mm": pos.y / 1e6,
                            "rotation_deg": fp.GetOrientationDegrees(),
                            "layer": fp.GetLayerName(),
                        }
                    )
            except Exception as e:
                raise KiCadAPIError("GetFootprints", str(e))

            ctx.log_progress("components_listed", count=len(components))

            return {
                "status": "success",
                "count": len(components),
                "components": components,
            }

    async def _read_netlist(self) -> Dict:
        """Read netlist information from the board."""
        with operation_context("read_netlist", logger=self.logger) as ctx:
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "nets": [
                        {"name": "GND", "pads": 5},
                        {"name": "+5V", "pads": 3},
                        {"name": "LED_OUT", "pads": 2},
                    ],
                }

            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded")

            nets = []
            try:
                netinfo = self.board.GetNetInfo()
                for net_name, net in netinfo.NetsByName().items():
                    if net_name:
                        nets.append(
                            {
                                "name": net_name,
                                "code": net.GetNetCode(),
                            }
                        )
            except Exception as e:
                raise KiCadAPIError("GetNetInfo", str(e))

            ctx.log_progress("netlist_read", net_count=len(nets))

            return {"status": "success", "count": len(nets), "nets": nets}

    async def _get_board_info(self) -> Dict:
        """Get general board information."""
        with operation_context("get_board_info", logger=self.logger) as ctx:
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "board_name": "example_board",
                    "size": {"width_mm": 100, "height_mm": 80},
                    "layers": 2,
                }

            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            try:
                bbox = self.board.GetBoardEdgesBoundingBox()
                board_name = self.board.GetFileName()
                layer_count = self.board.GetCopperLayerCount()
                component_count = len(list(self.board.GetFootprints()))
            except Exception as e:
                raise KiCadAPIError("GetBoardInfo", str(e))

            ctx.log_progress(
                "board_info_retrieved", components=component_count, layers=layer_count
            )

            return {
                "status": "success",
                "board_name": board_name,
                "size": {
                    "width_mm": bbox.GetWidth() / 1e6,
                    "height_mm": bbox.GetHeight() / 1e6,
                },
                "layer_count": layer_count,
                "component_count": component_count,
            }

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def _run_server() -> None:
    """Run the basic server event loop."""
    server = KiCadMCPServer()
    await server.run()


def main() -> None:
    """Console entry point."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("usage: mcp-kicad-basic\n\nRun the basic KiCad MCP server over stdio.")
        return
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
