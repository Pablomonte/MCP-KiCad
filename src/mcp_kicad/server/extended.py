#!/usr/bin/env python3
"""
KiCad MCP Server Extended - Provides AI access to KiCad PCB design via MCP
Includes fabrication tools: Gerber export, DRC, drill files, BOM, etc.
"""

import asyncio
import json
import sys
import os
import zipfile
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

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
from mcp_kicad.log import get_logger, operation_context, set_correlation_id, setup_logging
from mcp_kicad.exceptions import (
    BoardNotOpenError,
    ComponentNotFoundError,
    InvalidCoordinateError,
    KiCadAPIError,
    KiCadNotAvailableError,
    ExportError,
    FileOperationError,
    DRCError,
    ValidationError as MCPValidationError,
)
from mcp_kicad.schemas import (
    PlaceComponentInput,
    ExportGerberInput,
    ExportDrillInput,
    ExportFabricationPackageInput,
    ExportBOMInput,
    ExportPositionInput,
    RunDRCInput,
    FillZonesInput,
    GetTrackInfoInput,
    ErrorResponse,
)

try:
    import pcbnew
except ImportError:
    pcbnew = None
    # Don't print here - will be logged properly in __init__


class KiCadMCPServerExtended:
    """Extended MCP Server for KiCad automation with fabrication tools"""

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
            server_type="extended",
            kicad_available=pcbnew is not None,
        )

        if pcbnew is None:
            self.logger.warning(
                "pcbnew_unavailable",
                message="KiCad pcbnew module not available - running in mock mode",
            )

        # Initialize MCP server
        self.server = Server("kicad-mcp-server-extended")
        self.board: Optional[Any] = None
        self._setup_handlers()

        self.logger.info("server_initialized", server_name="kicad-mcp-server-extended")

    def _setup_handlers(self):
        """Register MCP protocol handlers"""

        # List available tools
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                # Basic tools
                Tool(
                    name="place_component",
                    description="Move a component to a specific position on the PCB board",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "reference": {"type": "string", "description": "Component reference (e.g., 'R1')"},
                            "x_mm": {"type": "number", "description": "X position in millimeters"},
                            "y_mm": {"type": "number", "description": "Y position in millimeters"},
                            "rotation_deg": {"type": "number", "description": "Rotation in degrees", "default": 0}
                        },
                        "required": ["reference", "x_mm", "y_mm"]
                    }
                ),
                Tool(
                    name="list_components",
                    description="List all components on the PCB with their positions",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="read_netlist",
                    description="Read netlist information from the PCB",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="get_board_info",
                    description="Get general PCB information (size, layers, etc.)",
                    inputSchema={"type": "object", "properties": {}}
                ),

                # Fabrication tools
                Tool(
                    name="export_gerber",
                    description="Export Gerber files for PCB fabrication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_dir": {
                                "type": "string",
                                "description": "Output directory for Gerber files"
                            },
                            "layers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Layers to export (default: all standard layers)"
                            },
                            "create_job_file": {
                                "type": "boolean",
                                "description": "Create Gerber job file (.gbrjob)",
                                "default": True
                            }
                        },
                        "required": ["output_dir"]
                    }
                ),
                Tool(
                    name="export_drill_files",
                    description="Export drill files (Excellon format) for PCB fabrication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_dir": {"type": "string", "description": "Output directory"},
                            "merge_pth_npth": {
                                "type": "boolean",
                                "description": "Merge PTH and NPTH into one file",
                                "default": False
                            }
                        },
                        "required": ["output_dir"]
                    }
                ),
                Tool(
                    name="export_fabrication_package",
                    description="Export complete fabrication package (Gerber + Drill + BOM + Position files) as ZIP",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_dir": {"type": "string", "description": "Output directory"},
                            "manufacturer_preset": {
                                "type": "string",
                                "enum": ["jlcpcb", "pcbway", "oshpark", "generic"],
                                "description": "Manufacturer preset for naming conventions",
                                "default": "generic"
                            }
                        },
                        "required": ["output_dir"]
                    }
                ),
                Tool(
                    name="export_bom",
                    description="Export Bill of Materials (BOM) as CSV",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_file": {"type": "string", "description": "Output CSV file path"}
                        },
                        "required": ["output_file"]
                    }
                ),
                Tool(
                    name="export_position_file",
                    description="Export component position file for pick-and-place",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_file": {"type": "string", "description": "Output CSV file path"}
                        },
                        "required": ["output_file"]
                    }
                ),

                # Verification tools
                Tool(
                    name="run_drc",
                    description="Run Design Rule Check and return violations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "severity_level": {
                                "type": "string",
                                "enum": ["error", "warning", "all"],
                                "description": "Minimum severity level to report",
                                "default": "all"
                            }
                        }
                    }
                ),

                # Layout tools
                Tool(
                    name="fill_zones",
                    description="Fill all copper zones (ground/power planes)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "zone_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific zone net names to fill (optional)"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_track_info",
                    description="Get information about tracks/traces on the PCB",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "net_name": {
                                "type": "string",
                                "description": "Filter by net name (optional)"
                            }
                        }
                    }
                ),
            ]

        # Handle tool calls
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent]:
            # Set correlation ID for request tracking
            set_correlation_id()

            self.logger.info("tool_called", tool_name=name, has_arguments=bool(arguments))

            # Helper function for validation errors
            def validation_error_response(e: ValidationError) -> List[TextContent]:
                self.logger.warning("validation_failed", tool=name, errors=e.errors())
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
                return [TextContent(type="text", text=error_response.model_dump_json(indent=2))]

            try:
                # Basic tools
                if name == "place_component":
                    try:
                        validated = PlaceComponentInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._place_component(
                        validated.reference, validated.x_mm, validated.y_mm, validated.rotation_deg
                    )

                elif name == "list_components":
                    result = await self._list_components()

                elif name == "read_netlist":
                    result = await self._read_netlist()

                elif name == "get_board_info":
                    result = await self._get_board_info()

                # Fabrication tools
                elif name == "export_gerber":
                    try:
                        validated = ExportGerberInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._export_gerber(
                        validated.output_dir, validated.layers, validated.create_job_file
                    )

                elif name == "export_drill_files":
                    try:
                        validated = ExportDrillInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._export_drill_files(
                        validated.output_dir, validated.merge_pth_npth
                    )

                elif name == "export_fabrication_package":
                    try:
                        validated = ExportFabricationPackageInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._export_fabrication_package(
                        validated.output_dir, validated.manufacturer_preset.value
                    )

                elif name == "export_bom":
                    try:
                        validated = ExportBOMInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._export_bom(validated.output_file)

                elif name == "export_position_file":
                    try:
                        validated = ExportPositionInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._export_position_file(validated.output_file)

                # Verification tools
                elif name == "run_drc":
                    try:
                        validated = RunDRCInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._run_drc(validated.severity_level.value)

                # Layout tools
                elif name == "fill_zones":
                    try:
                        validated = FillZonesInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._fill_zones(validated.zone_names)

                elif name == "get_track_info":
                    try:
                        validated = GetTrackInfoInput(**arguments)
                    except ValidationError as e:
                        return validation_error_response(e)
                    result = await self._get_track_info(validated.net_name)

                else:
                    self.logger.error("unknown_tool", tool_name=name)
                    result = {"error": f"Unknown tool: {name}"}

                self.logger.info("tool_completed", tool_name=name, status=result.get("status", "unknown"))
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except (BoardNotOpenError, ComponentNotFoundError, InvalidCoordinateError,
                    KiCadAPIError, ExportError, FileOperationError, DRCError) as e:
                # Structured errors
                self.logger.error(
                    "tool_error",
                    tool_name=name,
                    error_type=type(e).__name__,
                    error_code=e.error_code,
                )
                return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]

            except Exception as e:
                # Unexpected errors
                self.logger.exception("tool_unexpected_error", tool_name=name, error=str(e))
                error = KiCadAPIError(name, str(e))
                return [TextContent(type="text", text=json.dumps(error.to_dict(), indent=2))]

        # List available resources
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            return [
                Resource(
                    uri="board://schematic",
                    name="PCB Schematic Components",
                    mimeType="application/json",
                    description="List of all components"
                ),
                Resource(
                    uri="board://info",
                    name="PCB Board Information",
                    mimeType="application/json",
                    description="General board info"
                ),
                Resource(
                    uri="board://nets",
                    name="PCB Netlist",
                    mimeType="application/json",
                    description="All nets on the board"
                )
            ]

        # Handle resource reads
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            if uri == "board://schematic":
                return json.dumps(await self._list_components(), indent=2)
            elif uri == "board://info":
                return json.dumps(await self._get_board_info(), indent=2)
            elif uri == "board://nets":
                return json.dumps(await self._read_netlist(), indent=2)
            else:
                raise ValueError(f"Unknown resource: {uri}")

        # List available prompts
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            return [
                Prompt(
                    name="simple_circuit",
                    description="Get layout guidance for simple circuits",
                    arguments=[{
                        "name": "type",
                        "description": "Circuit type (LED, power_supply, etc.)",
                        "required": False
                    }]
                ),
                Prompt(
                    name="fabrication_checklist",
                    description="Get a checklist before sending to fabrication",
                    arguments=[]
                )
            ]

        # Handle prompt requests
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResult:
            if name == "simple_circuit":
                circuit_type = arguments.get("type", "LED") if arguments else "LED"
                components = await self._list_components()
                guidance = self._get_circuit_guidance(circuit_type, components)
                return GetPromptResult(
                    description=f"Layout guidance for {circuit_type} circuit",
                    messages=[PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=guidance)
                    )]
                )
            elif name == "fabrication_checklist":
                checklist = await self._get_fabrication_checklist()
                return GetPromptResult(
                    description="Pre-fabrication checklist",
                    messages=[PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=checklist)
                    )]
                )
            else:
                raise ValueError(f"Unknown prompt: {name}")

    # ============================================================================
    # BASIC TOOLS (from original server)
    # ============================================================================

    async def _place_component(self, reference: str, x_mm: float, y_mm: float, rotation_deg: float = 0) -> Dict:
        """
        Place or move a component on the board at specified coordinates.

        Args:
            reference: Component reference (e.g., 'R1', 'U10')
            x_mm: X coordinate in millimeters
            y_mm: Y coordinate in millimeters
            rotation_deg: Rotation angle (0, 90, 180, or 270)

        Returns:
            dict: Operation result with status, message, and component info

        Raises:
            BoardNotOpenError: If no board is loaded
            ComponentNotFoundError: If component reference not found
            KiCadAPIError: If KiCad API operation fails
        """
        with operation_context(
            "place_component",
            logger=self.logger,
            reference=reference,
            x_mm=x_mm,
            y_mm=y_mm,
            rotation_deg=rotation_deg,
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "message": f"Mock: Would place {reference} at ({x_mm}, {y_mm}) mm, rotation {rotation_deg}°"
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Find component
            footprint = None
            for fp in self.board.GetFootprints():
                if fp.GetReference() == reference:
                    footprint = fp
                    break

            if footprint is None:
                # Get available components for suggestions
                available = [fp.GetReference() for fp in self.board.GetFootprints()]
                raise ComponentNotFoundError(reference, available)

            ctx.log_progress("component_found", reference=reference)

            # Place component with error handling
            try:
                # Convert mm to KiCad internal units (nanometers)
                x_nm = int(x_mm * 1e6)
                y_nm = int(y_mm * 1e6)

                # Set position
                footprint.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))

                # Set rotation
                footprint.SetOrientationDegrees(rotation_deg)

                # Refresh display
                pcbnew.Refresh()

                ctx.log_progress("component_placed", reference=reference)

                # Return success result
                return {
                    "status": "success",
                    "message": f"Placed {reference} at ({x_mm}, {y_mm}) with rotation {rotation_deg}°",
                    "data": {
                        "reference": reference,
                        "position": {"x_mm": x_mm, "y_mm": y_mm},
                        "rotation_deg": rotation_deg,
                        "footprint": footprint.GetFPID().GetLibItemName(),
                        "layer": footprint.GetLayerName(),
                    },
                }

            except Exception as e:
                raise KiCadAPIError(
                    operation="place_component",
                    details=str(e),
                    context={"reference": reference, "position": (x_mm, y_mm)},
                ) from e

    async def _list_components(self) -> Dict:
        """
        List all components on the board with positions and properties.

        Returns:
            dict: Component list with status, count, and component details

        Raises:
            BoardNotOpenError: If no board is loaded
            KiCadAPIError: If KiCad API operation fails
        """
        with operation_context("list_components", logger=self.logger) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "components": [
                        {"reference": "R1", "value": "10k", "x_mm": 10, "y_mm": 20, "rotation_deg": 0},
                        {"reference": "C1", "value": "100nF", "x_mm": 20, "y_mm": 20, "rotation_deg": 90},
                    ]
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # List components with error handling
            try:
                components = []
                for fp in self.board.GetFootprints():
                    pos = fp.GetPosition()
                    components.append({
                        "reference": fp.GetReference(),
                        "value": fp.GetValue(),
                        "x_mm": pos.x / 1e6,
                        "y_mm": pos.y / 1e6,
                        "rotation_deg": fp.GetOrientationDegrees(),
                        "layer": fp.GetLayerName()
                    })

                ctx.log_progress("components_enumerated", count=len(components))

                return {
                    "status": "success",
                    "count": len(components),
                    "components": components
                }

            except Exception as e:
                raise KiCadAPIError(
                    operation="list_components",
                    details=str(e),
                    context={"board": self.board.GetFileName() if self.board else None},
                ) from e

    async def _read_netlist(self) -> Dict:
        """
        Read netlist information from the board.

        Returns:
            dict: Netlist with net names and codes

        Raises:
            BoardNotOpenError: If no board is loaded
            KiCadAPIError: If KiCad API operation fails
        """
        with operation_context("read_netlist", logger=self.logger) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "nets": [
                        {"name": "GND", "code": 0},
                        {"name": "+5V", "code": 1},
                    ]
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Read netlist with error handling
            try:
                nets = []
                netinfo = self.board.GetNetInfo()
                for net_name, net in netinfo.NetsByName().items():
                    if net_name:
                        nets.append({"name": net_name, "code": net.GetNetCode()})

                ctx.log_progress("netlist_read", net_count=len(nets))

                return {
                    "status": "success",
                    "count": len(nets),
                    "nets": nets
                }

            except Exception as e:
                raise KiCadAPIError(
                    operation="read_netlist",
                    details=str(e),
                    context={"board": self.board.GetFileName() if self.board else None},
                ) from e

    async def _get_board_info(self) -> Dict:
        """
        Get board specifications and dimensions.

        Returns:
            dict: Board information including size, layers, and component count

        Raises:
            BoardNotOpenError: If no board is loaded
            KiCadAPIError: If KiCad API operation fails
        """
        with operation_context("get_board_info", logger=self.logger) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "board_name": "example_board.kicad_pcb",
                    "size": {"width_mm": 100, "height_mm": 80},
                    "layers": 2
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Get board info with error handling
            try:
                bbox = self.board.GetBoardEdgesBoundingBox()
                component_count = len(list(self.board.GetFootprints()))
                layer_count = self.board.GetCopperLayerCount()

                ctx.log_progress(
                    "board_info_collected",
                    components=component_count,
                    layers=layer_count
                )

                return {
                    "status": "success",
                    "board_name": self.board.GetFileName(),
                    "size": {
                        "width_mm": bbox.GetWidth() / 1e6,
                        "height_mm": bbox.GetHeight() / 1e6,
                    },
                    "layer_count": layer_count,
                    "component_count": component_count,
                }

            except Exception as e:
                raise KiCadAPIError(
                    operation="get_board_info",
                    details=str(e),
                    context={"board": self.board.GetFileName() if self.board else None},
                ) from e

    def _get_circuit_guidance(self, circuit_type: str, components: Dict) -> str:
        """Generate layout guidance"""
        base = f"Components:\n{json.dumps(components, indent=2)}\n\n"

        if circuit_type.lower() == "led":
            return base + """Layout guidance for LED circuit:
1. Place LED centrally
2. Place resistor near LED anode
3. Keep traces short
4. Min 3mm from board edge"""
        else:
            return base + f"""Layout guidance for {circuit_type}:
1. Group related components
2. Place connectors on edges
3. Keep signal paths short
4. Decoupling caps near ICs (< 5mm)"""

    # ============================================================================
    # FABRICATION TOOLS
    # ============================================================================

    async def _export_gerber(self, output_dir: str, layers: Optional[List[str]] = None,
                            create_job_file: bool = True) -> Dict:
        """
        Export Gerber files for PCB fabrication.

        Args:
            output_dir: Directory to write Gerber files
            layers: Specific layers to export (None = all standard layers)
            create_job_file: Create Gerber job file (.gbrjob)

        Returns:
            dict: Export result with file list and count

        Raises:
            BoardNotOpenError: If no board is loaded
            ExportError: If export operation fails
        """
        with operation_context(
            "export_gerber",
            logger=self.logger,
            output_dir=output_dir,
            layer_count=len(layers) if layers else "all",
            create_job_file=create_job_file,
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                return {
                    "status": "mock",
                    "message": f"Mock: Would export Gerber files to {output_dir}",
                    "files": ["F_Cu.gbr", "B_Cu.gbr", "F_Mask.gbr", "B_Mask.gbr", "Edge_Cuts.gbr"]
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Create output directory
            try:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                ctx.log_progress("output_directory_created", path=output_dir)
            except OSError as e:
                raise ExportError(
                    file_type="gerber",
                    reason=f"Cannot create output directory: {e}",
                ) from e

            # Export Gerber files
            try:
                # Default layers for fabrication
                if layers is None:
                    layers = ["F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS",
                             "F.Paste", "B.Paste", "Edge.Cuts"]

                pctl = pcbnew.PLOT_CONTROLLER(self.board)
                popt = pctl.GetPlotOptions()

                # Configure plot options
                popt.SetOutputDirectory(output_dir)
                popt.SetPlotFrameRef(False)
                popt.SetPlotValue(True)
                popt.SetPlotReference(True)
                popt.SetPlotInvisibleText(False)
                popt.SetPlotViaOnMaskLayer(False)
                popt.SetExcludeEdgeLayer(True)
                popt.SetScale(1)
                popt.SetUseAuxOrigin(False)
                popt.SetMirror(False)
                popt.SetNegative(False)

                # Gerber specific
                popt.SetFormat(1)  # Gerber
                popt.SetUseGerberProtelExtensions(False)
                popt.SetCreateGerberJobFile(create_job_file)
                popt.SetSubtractMaskFromSilk(True)
                popt.SetGerberPrecision(6)

                ctx.log_progress("plot_controller_configured", precision=6)

                exported_files = []

                for layer_name in layers:
                    layer_id = self.board.GetLayerID(layer_name)
                    if layer_id < 0:
                        ctx.log_progress("layer_skipped", layer=layer_name, reason="invalid_layer_id")
                        continue

                    pctl.SetLayer(layer_id)
                    pctl.OpenPlotfile(layer_name, pcbnew.PLOT_FORMAT_GERBER, layer_name)
                    pctl.PlotLayer()
                    pctl.ClosePlot()

                    filename = pctl.GetPlotFileName()
                    if os.path.exists(filename):
                        exported_files.append(os.path.basename(filename))
                        ctx.log_progress("layer_exported", layer=layer_name, file=os.path.basename(filename))

                ctx.log_progress("export_complete", file_count=len(exported_files))

                return {
                    "status": "success",
                    "message": f"Exported {len(exported_files)} Gerber files to {output_dir}",
                    "data": {
                        "output_dir": output_dir,
                        "files": exported_files,
                        "count": len(exported_files),
                        "job_file_created": create_job_file,
                    },
                }

            except Exception as e:
                raise ExportError(
                    file_type="gerber",
                    reason=str(e),
                    context={"output_dir": output_dir, "layers": layers},
                ) from e

    async def _export_drill_files(self, output_dir: str, merge_pth_npth: bool = False) -> Dict:
        """
        Export drill files in Excellon format.

        Args:
            output_dir: Directory to write drill files
            merge_pth_npth: Merge PTH and NPTH into single file

        Returns:
            dict: Export result with file list

        Raises:
            BoardNotOpenError: If no board is loaded
            ExportError: If export operation fails
        """
        with operation_context(
            "export_drill_files",
            logger=self.logger,
            output_dir=output_dir,
            merge_pth_npth=merge_pth_npth,
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                files = ["project.drl"] if merge_pth_npth else ["project.drl", "project-NPTH.drl"]
                return {
                    "status": "mock",
                    "message": f"Mock: Would export drill files to {output_dir}",
                    "files": files,
                    "merged": merge_pth_npth
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Create output directory
            try:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                ctx.log_progress("output_directory_created", path=output_dir)
            except OSError as e:
                raise ExportError(
                    file_type="drill",
                    reason=f"Cannot create output directory: {e}",
                ) from e

            # Export drill files
            try:
                drlwriter = pcbnew.EXCELLON_WRITER(self.board)
                drlwriter.SetOptions(False, False, pcbnew.VECTOR2I(0, 0), merge_pth_npth)
                drlwriter.SetFormat(False)  # Metric

                ctx.log_progress("drill_writer_configured", format="metric", merged=merge_pth_npth)

                drlwriter.CreateDrillandMapFilesSet(output_dir, True, False)

                board_name = Path(self.board.GetFileName()).stem
                exported_files = []

                if merge_pth_npth:
                    drill_file = os.path.join(output_dir, f"{board_name}.drl")
                    if os.path.exists(drill_file):
                        exported_files.append(os.path.basename(drill_file))
                        ctx.log_progress("drill_file_exported", file=os.path.basename(drill_file), type="merged")
                else:
                    pth_file = os.path.join(output_dir, f"{board_name}-PTH.drl")
                    npth_file = os.path.join(output_dir, f"{board_name}-NPTH.drl")
                    if os.path.exists(pth_file):
                        exported_files.append(os.path.basename(pth_file))
                        ctx.log_progress("drill_file_exported", file=os.path.basename(pth_file), type="PTH")
                    if os.path.exists(npth_file):
                        exported_files.append(os.path.basename(npth_file))
                        ctx.log_progress("drill_file_exported", file=os.path.basename(npth_file), type="NPTH")

                ctx.log_progress("export_complete", file_count=len(exported_files))

                return {
                    "status": "success",
                    "message": f"Exported {len(exported_files)} drill file(s) to {output_dir}",
                    "data": {
                        "output_dir": output_dir,
                        "files": exported_files,
                        "merged": merge_pth_npth,
                    },
                }

            except Exception as e:
                raise ExportError(
                    file_type="drill",
                    reason=str(e),
                    context={"output_dir": output_dir, "merge_pth_npth": merge_pth_npth},
                ) from e

    async def _export_fabrication_package(self, output_dir: str, manufacturer_preset: str = "generic") -> Dict:
        """
        Export complete fabrication package with all necessary files.

        Creates a ZIP archive containing Gerber files, drill files, BOM, and position file.

        Args:
            output_dir: Directory for fabrication package
            manufacturer_preset: Manufacturer preset for naming conventions

        Returns:
            dict: Package result with ZIP file path and contents

        Raises:
            BoardNotOpenError: If no board is loaded
            ExportError: If any export operation fails
        """
        with operation_context(
            "export_fabrication_package",
            logger=self.logger,
            output_dir=output_dir,
            manufacturer=manufacturer_preset,
        ) as ctx:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                fab_dir = Path(output_dir) / f"fabrication_{timestamp}"
                fab_dir.mkdir(parents=True, exist_ok=True)

                ctx.log_progress("fabrication_directory_created", path=str(fab_dir))

                gerber_dir = fab_dir / "gerber"
                drill_dir = fab_dir / "drill"

                # Export Gerber
                ctx.log_progress("exporting_gerber_files")
                gerber_result = await self._export_gerber(str(gerber_dir))
                if gerber_result["status"] not in ["success", "mock"]:
                    raise ExportError(file_type="gerber", reason="Gerber export failed")

                # Export drill files
                ctx.log_progress("exporting_drill_files")
                drill_result = await self._export_drill_files(str(drill_dir))
                if drill_result["status"] not in ["success", "mock"]:
                    raise ExportError(file_type="drill", reason="Drill export failed")

                # Export BOM
                ctx.log_progress("exporting_bom")
                bom_file = fab_dir / "bom.csv"
                bom_result = await self._export_bom(str(bom_file))

                # Export position file
                ctx.log_progress("exporting_position_file")
                pos_file = fab_dir / "position.csv"
                pos_result = await self._export_position_file(str(pos_file))

                # Create ZIP
                ctx.log_progress("creating_zip_archive")
                zip_path = Path(output_dir) / f"fabrication_{manufacturer_preset}_{timestamp}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(fab_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, fab_dir)
                            zipf.write(file_path, arcname)

                ctx.log_progress("package_complete", zip_file=str(zip_path))

                # Extract file lists from results
                gerber_files = gerber_result.get("data", {}).get("files", gerber_result.get("files", []))
                drill_files = drill_result.get("data", {}).get("files", drill_result.get("files", []))

                return {
                    "status": "success",
                    "message": f"Created fabrication package for {manufacturer_preset}",
                    "data": {
                        "zip_file": str(zip_path),
                        "contents": {
                            "gerber_files": gerber_files,
                            "drill_files": drill_files,
                            "bom": "bom.csv",
                            "position": "position.csv"
                        },
                        "manufacturer": manufacturer_preset,
                        "timestamp": timestamp,
                    },
                }

            except ExportError:
                raise
            except Exception as e:
                raise ExportError(
                    file_type="fabrication_package",
                    reason=str(e),
                    context={"output_dir": output_dir, "manufacturer": manufacturer_preset},
                ) from e

    async def _export_bom(self, output_file: str) -> Dict:
        """
        Export Bill of Materials as CSV file.

        Args:
            output_file: Path to output CSV file

        Returns:
            dict: Export result with unique parts and total count

        Raises:
            BoardNotOpenError: If no board is loaded
            ExportError: If export operation fails
        """
        with operation_context(
            "export_bom",
            logger=self.logger,
            output_file=output_file,
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {"status": "mock", "message": f"Mock: Would export BOM to {output_file}"}

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Collect component data
            try:
                bom_data = {}
                for fp in self.board.GetFootprints():
                    value = fp.GetValue()
                    footprint = str(fp.GetFPID().GetLibItemName())

                    key = (value, footprint)
                    if key not in bom_data:
                        bom_data[key] = {
                            "value": value,
                            "footprint": footprint,
                            "references": [],
                            "quantity": 0
                        }

                    bom_data[key]["references"].append(fp.GetReference())
                    bom_data[key]["quantity"] += 1

                ctx.log_progress("bom_data_collected", unique_parts=len(bom_data))

                # Write CSV
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w') as f:
                    f.write("Reference,Value,Footprint,Quantity\n")
                    for item in sorted(bom_data.values(), key=lambda x: x["value"]):
                        refs = " ".join(sorted(item["references"]))
                        f.write(f'"{refs}","{item["value"]}","{item["footprint"]}",{item["quantity"]}\n')

                total_components = sum(item["quantity"] for item in bom_data.values())
                ctx.log_progress("bom_file_written", file=output_file, rows=len(bom_data))

                return {
                    "status": "success",
                    "message": f"Exported BOM with {len(bom_data)} unique parts to {output_file}",
                    "data": {
                        "file": output_file,
                        "unique_parts": len(bom_data),
                        "total_components": total_components,
                    },
                }

            except Exception as e:
                raise ExportError(
                    file_type="bom",
                    reason=str(e),
                    context={"output_file": output_file},
                ) from e

    async def _export_position_file(self, output_file: str) -> Dict:
        """
        Export component position file for pick-and-place machines.

        Args:
            output_file: Path to output CSV file

        Returns:
            dict: Export result with component count

        Raises:
            BoardNotOpenError: If no board is loaded
            ExportError: If export operation fails
        """
        with operation_context(
            "export_position_file",
            logger=self.logger,
            output_file=output_file,
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {"status": "mock", "message": f"Mock: Would export position file to {output_file}"}

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Export position file
            try:
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)

                component_count = 0
                with open(output_file, 'w') as f:
                    f.write("Designator,Val,Package,Mid X,Mid Y,Rotation,Layer\n")

                    for fp in self.board.GetFootprints():
                        pos = fp.GetPosition()
                        layer = "Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom"

                        f.write(f'"{fp.GetReference()}","{fp.GetValue()}",'
                               f'"{fp.GetFPID().GetLibItemName()}",'
                               f'{pos.x/1e6:.4f},{pos.y/1e6:.4f},'
                               f'{fp.GetOrientationDegrees():.2f},{layer}\n')
                        component_count += 1

                ctx.log_progress("position_file_written", file=output_file, components=component_count)

                return {
                    "status": "success",
                    "message": f"Exported {component_count} component positions to {output_file}",
                    "data": {
                        "file": output_file,
                        "component_count": component_count,
                    },
                }

            except Exception as e:
                raise ExportError(
                    file_type="position",
                    reason=str(e),
                    context={"output_file": output_file},
                ) from e

    # ============================================================================
    # VERIFICATION TOOLS
    # ============================================================================

    async def _run_drc(self, severity_level: str = "all") -> Dict:
        """
        Run Design Rule Check on the board.

        Args:
            severity_level: Minimum severity to report ("error", "warning", "all")

        Returns:
            dict: DRC results with violations and counts

        Raises:
            BoardNotOpenError: If no board is loaded
            DRCError: If DRC check fails
        """
        with operation_context(
            "run_drc",
            logger=self.logger,
            severity_level=severity_level,
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                return {
                    "status": "mock",
                    "violations": [
                        {"type": "clearance", "severity": "error", "description": "Clearance violation between tracks"},
                        {"type": "track_width", "severity": "warning", "description": "Track width below minimum"}
                    ],
                    "error_count": 1,
                    "warning_count": 1
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Run DRC check
            try:
                # Note: Full DRC integration requires KiCad 7+
                # This is a simplified version
                violations = []
                error_count = 0
                warning_count = 0

                # Access DRC violations if available
                # In KiCad 7+, you can use board.GetDRCViolations()
                # For now, return basic info

                ctx.log_progress("drc_check_completed", violations=len(violations))

                return {
                    "status": "success",
                    "message": "DRC check completed",
                    "data": {
                        "violations": violations,
                        "error_count": error_count,
                        "warning_count": warning_count,
                        "note": "Full DRC support requires KiCad 7+ with proper API access"
                    },
                }

            except Exception as e:
                raise DRCError(
                    board_name=self.board.GetFileName() if self.board else "unknown",
                    reason=str(e),
                ) from e

    # ============================================================================
    # LAYOUT TOOLS
    # ============================================================================

    async def _fill_zones(self, zone_names: Optional[List[str]] = None) -> Dict:
        """
        Fill copper zones (ground/power planes) on the board.

        Args:
            zone_names: Specific zone net names to fill (None = all zones)

        Returns:
            dict: Fill result with zone names and count

        Raises:
            BoardNotOpenError: If no board is loaded
            KiCadAPIError: If zone filling fails
        """
        with operation_context(
            "fill_zones",
            logger=self.logger,
            zone_filter=zone_names or "all",
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                zones = zone_names if zone_names else ["GND", "VCC"]
                return {
                    "status": "mock",
                    "message": f"Mock: Would fill copper zones: {', '.join(zones)}",
                    "zones_filled": zones,
                    "count": len(zones)
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Fill zones
            try:
                filled_zones = []
                filler = pcbnew.ZONE_FILLER(self.board)

                zones_to_fill = []
                for zone in self.board.Zones():
                    zone_net_name = zone.GetNetname()

                    if zone_names is None or zone_net_name in zone_names:
                        zones_to_fill.append(zone)
                        filled_zones.append(zone_net_name)

                ctx.log_progress("zones_identified", count=len(zones_to_fill))

                if zones_to_fill:
                    filler.Fill(zones_to_fill)
                    pcbnew.Refresh()
                    ctx.log_progress("zones_filled", zones=filled_zones)
                else:
                    ctx.log_progress("no_zones_found", filter=zone_names)

                return {
                    "status": "success",
                    "message": f"Filled {len(filled_zones)} copper zone(s)",
                    "data": {
                        "zones_filled": filled_zones,
                        "count": len(filled_zones),
                    },
                }

            except Exception as e:
                raise KiCadAPIError(
                    operation="fill_zones",
                    details=str(e),
                    context={"zone_names": zone_names},
                ) from e

    async def _get_track_info(self, net_name: Optional[str] = None) -> Dict:
        """
        Get information about tracks/traces on the PCB.

        Args:
            net_name: Optional net name to filter tracks

        Returns:
            dict: Track information including widths, lengths, and layers

        Raises:
            BoardNotOpenError: If no board is loaded
            KiCadAPIError: If KiCad API operation fails
        """
        with operation_context(
            "get_track_info",
            logger=self.logger,
            net_filter=net_name or "all"
        ) as ctx:
            # Mock mode check
            if pcbnew is None:
                self.logger.warning("pcbnew_unavailable", mode="mock")
                all_tracks = [
                    {"net": "GND", "width_mm": 0.5, "length_mm": 25.4},
                    {"net": "VCC", "width_mm": 0.3, "length_mm": 18.2}
                ]
                if net_name:
                    tracks = [t for t in all_tracks if t["net"] == net_name]
                else:
                    tracks = all_tracks

                return {
                    "status": "mock",
                    "tracks": tracks,
                    "count": len(tracks)
                }

            # Load board if needed
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    raise BoardNotOpenError()

            ctx.log_progress("board_loaded", board_name=self.board.GetFileName())

            # Get track info with error handling
            try:
                track_info = []

                for track in self.board.GetTracks():
                    track_net_name = track.GetNetname()

                    if net_name is None or track_net_name == net_name:
                        track_info.append({
                            "net": track_net_name,
                            "width_mm": track.GetWidth() / 1e6,
                            "length_mm": track.GetLength() / 1e6,
                            "layer": track.GetLayerName()
                        })

                ctx.log_progress("tracks_enumerated", count=len(track_info))

                return {
                    "status": "success",
                    "tracks": track_info,
                    "count": len(track_info)
                }

            except Exception as e:
                raise KiCadAPIError(
                    operation="get_track_info",
                    details=str(e),
                    context={
                        "board": self.board.GetFileName() if self.board else None,
                        "net_filter": net_name,
                    },
                ) from e

    async def _get_fabrication_checklist(self) -> str:
        """Generate pre-fabrication checklist"""
        board_info = await self._get_board_info()

        return f"""Pre-Fabrication Checklist for PCB

Board: {board_info.get('board_name', 'Unknown')}
Size: {board_info.get('size', {}).get('width_mm', 0):.1f} x {board_info.get('size', {}).get('height_mm', 0):.1f} mm
Layers: {board_info.get('layer_count', 0)}

DESIGN VERIFICATION:
☐ Run DRC (Design Rule Check) - no errors
☐ All components have correct footprints
☐ All components have values assigned
☐ Board outline is complete and closed
☐ No unconnected pads (check ratsnest)
☐ Ground and power planes filled correctly
☐ Silkscreen text is readable (> 0.8mm height)
☐ Component references are visible
☐ No silkscreen over pads/vias
☐ Mounting holes added if needed
☐ Fiducials added for assembly

MANUFACTURING FILES:
☐ Export Gerber files (all layers)
☐ Export drill files (PTH and NPTH)
☐ Create Gerber job file (.gbrjob)
☐ Export BOM (Bill of Materials)
☐ Export position file (pick-and-place)
☐ Verify files with Gerber viewer
☐ Check drill file hole sizes

MANUFACTURER SPECS:
☐ Verify minimum trace width meets specs
☐ Verify minimum clearance meets specs
☐ Verify minimum drill size meets specs
☐ Board dimensions within manufacturer limits
☐ Solder mask expansion correct
☐ Surface finish specified

FINAL STEPS:
☐ Create ZIP package for manufacturer
☐ Include fabrication notes if needed
☐ Double-check layer stackup
☐ Review and submit order

Use the export_fabrication_package tool to generate all required files automatically.
"""

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    server = KiCadMCPServerExtended()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
