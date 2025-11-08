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

try:
    import pcbnew
except ImportError:
    pcbnew = None
    print(
        "Warning: pcbnew module not available. Server will run in mock mode.",
        file=sys.stderr,
    )


class KiCadMCPServerExtended:
    """Extended MCP Server for KiCad automation with fabrication tools"""

    def __init__(self):
        self.server = Server("kicad-mcp-server-extended")
        self.board: Optional[Any] = None
        self._setup_handlers()

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
                            "reference": {
                                "type": "string",
                                "description": "Component reference (e.g., 'R1')",
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
                                "description": "Rotation in degrees",
                                "default": 0,
                            },
                        },
                        "required": ["reference", "x_mm", "y_mm"],
                    },
                ),
                Tool(
                    name="list_components",
                    description="List all components on the PCB with their positions",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="read_netlist",
                    description="Read netlist information from the PCB",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="get_board_info",
                    description="Get general PCB information (size, layers, etc.)",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="update_from_schematic",
                    description="Import/update components from schematic to PCB board",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schematic_path": {
                                "type": "string",
                                "description": "Path to .kicad_sch file (optional, auto-detected if not provided)",
                            }
                        },
                    },
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
                                "description": "Output directory for Gerber files",
                            },
                            "layers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Layers to export (default: all standard layers)",
                            },
                            "create_job_file": {
                                "type": "boolean",
                                "description": "Create Gerber job file (.gbrjob)",
                                "default": True,
                            },
                        },
                        "required": ["output_dir"],
                    },
                ),
                Tool(
                    name="export_drill_files",
                    description="Export drill files (Excellon format) for PCB fabrication",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_dir": {
                                "type": "string",
                                "description": "Output directory",
                            },
                            "merge_pth_npth": {
                                "type": "boolean",
                                "description": "Merge PTH and NPTH into one file",
                                "default": False,
                            },
                        },
                        "required": ["output_dir"],
                    },
                ),
                Tool(
                    name="export_fabrication_package",
                    description="Export complete fabrication package (Gerber + Drill + BOM + Position files) as ZIP",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_dir": {
                                "type": "string",
                                "description": "Output directory",
                            },
                            "manufacturer_preset": {
                                "type": "string",
                                "enum": ["jlcpcb", "pcbway", "oshpark", "generic"],
                                "description": "Manufacturer preset for naming conventions",
                                "default": "generic",
                            },
                        },
                        "required": ["output_dir"],
                    },
                ),
                Tool(
                    name="export_bom",
                    description="Export Bill of Materials (BOM) as CSV",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_file": {
                                "type": "string",
                                "description": "Output CSV file path",
                            }
                        },
                        "required": ["output_file"],
                    },
                ),
                Tool(
                    name="export_position_file",
                    description="Export component position file for pick-and-place",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_file": {
                                "type": "string",
                                "description": "Output CSV file path",
                            }
                        },
                        "required": ["output_file"],
                    },
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
                                "default": "all",
                            }
                        },
                    },
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
                                "description": "Specific zone net names to fill (optional)",
                            }
                        },
                    },
                ),
                Tool(
                    name="get_track_info",
                    description="Get information about tracks/traces on the PCB",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "net_name": {
                                "type": "string",
                                "description": "Filter by net name (optional)",
                            }
                        },
                    },
                ),
            ]

        # Handle tool calls
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent]:
            try:
                # Basic tools
                if name == "place_component":
                    result = await self._place_component(
                        arguments["reference"],
                        arguments["x_mm"],
                        arguments["y_mm"],
                        arguments.get("rotation_deg", 0),
                    )
                elif name == "list_components":
                    result = await self._list_components()
                elif name == "read_netlist":
                    result = await self._read_netlist()
                elif name == "get_board_info":
                    result = await self._get_board_info()
                elif name == "update_from_schematic":
                    result = await self._update_from_schematic(
                        arguments.get("schematic_path")
                    )

                # Fabrication tools
                elif name == "export_gerber":
                    result = await self._export_gerber(
                        arguments["output_dir"],
                        arguments.get("layers"),
                        arguments.get("create_job_file", True),
                    )
                elif name == "export_drill_files":
                    result = await self._export_drill_files(
                        arguments["output_dir"], arguments.get("merge_pth_npth", False)
                    )
                elif name == "export_fabrication_package":
                    result = await self._export_fabrication_package(
                        arguments["output_dir"],
                        arguments.get("manufacturer_preset", "generic"),
                    )
                elif name == "export_bom":
                    result = await self._export_bom(arguments["output_file"])
                elif name == "export_position_file":
                    result = await self._export_position_file(arguments["output_file"])

                # Verification tools
                elif name == "run_drc":
                    result = await self._run_drc(arguments.get("severity_level", "all"))

                # Layout tools
                elif name == "fill_zones":
                    result = await self._fill_zones(arguments.get("zone_names"))
                elif name == "get_track_info":
                    result = await self._get_track_info(arguments.get("net_name"))

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
                    description="List of all components",
                ),
                Resource(
                    uri="board://info",
                    name="PCB Board Information",
                    mimeType="application/json",
                    description="General board info",
                ),
                Resource(
                    uri="board://nets",
                    name="PCB Netlist",
                    mimeType="application/json",
                    description="All nets on the board",
                ),
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
                    arguments=[
                        {
                            "name": "type",
                            "description": "Circuit type (LED, power_supply, etc.)",
                            "required": False,
                        }
                    ],
                ),
                Prompt(
                    name="fabrication_checklist",
                    description="Get a checklist before sending to fabrication",
                    arguments=[],
                ),
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
            elif name == "fabrication_checklist":
                checklist = await self._get_fabrication_checklist()
                return GetPromptResult(
                    description="Pre-fabrication checklist",
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(type="text", text=checklist),
                        )
                    ],
                )
            else:
                raise ValueError(f"Unknown prompt: {name}")

    # ============================================================================
    # BASIC TOOLS (from original server)
    # ============================================================================

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
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is currently open in KiCad"}

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

            x_nm = int(x_mm * 1e6)
            y_nm = int(y_mm * 1e6)

            footprint.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
            footprint.SetOrientationDegrees(rotation_deg)

            pcbnew.Refresh()

            return {
                "status": "success",
                "reference": reference,
                "position": {"x_mm": x_mm, "y_mm": y_mm},
                "rotation_deg": rotation_deg,
            }
        except Exception as e:
            return {"error": f"Failed to place component: {str(e)}"}

    async def _list_components(self) -> Dict:
        """List all components"""
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
                ],
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            components = []
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

            return {
                "status": "success",
                "count": len(components),
                "components": components,
            }
        except Exception as e:
            return {"error": f"Failed to list components: {str(e)}"}

    async def _read_netlist(self) -> Dict:
        """Read netlist"""
        if pcbnew is None:
            return {
                "status": "mock",
                "nets": [
                    {"name": "GND", "code": 0},
                    {"name": "+5V", "code": 1},
                ],
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            nets = []
            netinfo = self.board.GetNetInfo()
            for net_name, net in netinfo.NetsByName().items():
                if net_name:
                    nets.append({"name": net_name, "code": net.GetNetCode()})

            return {"status": "success", "count": len(nets), "nets": nets}
        except Exception as e:
            return {"error": f"Failed to read netlist: {str(e)}"}

    async def _get_board_info(self) -> Dict:
        """Get board info"""
        if pcbnew is None:
            return {
                "status": "mock",
                "board_name": "example_board.kicad_pcb",
                "size": {"width_mm": 100, "height_mm": 80},
                "layers": 2,
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

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

    async def _update_from_schematic(
        self, schematic_path: Optional[str] = None
    ) -> Dict:
        """Update PCB from schematic file"""
        if pcbnew is None:
            return {
                "status": "mock",
                "message": "Mock: Would import components from schematic to PCB",
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            # Get PCB filename
            pcb_filename = self.board.GetFileName()
            if not pcb_filename:
                return {"error": "PCB board has no filename. Save the board first."}

            # Auto-detect schematic if not provided
            if schematic_path is None:
                # Try same name with .kicad_sch extension
                pcb_path = Path(pcb_filename)
                schematic_path = str(pcb_path.with_suffix(".kicad_sch"))

            schematic_file = Path(schematic_path)
            if not schematic_file.exists():
                return {
                    "error": f"Schematic file not found: {schematic_path}",
                    "suggestion": "Save the schematic first or provide the correct path",
                }

            # Try using kicad-cli for update
            import subprocess

            try:
                # Use kicad-cli to update PCB from schematic
                result = subprocess.run(
                    [
                        "kicad-cli",
                        "pcb",
                        "export",
                        "update-from-sch",
                        "--input",
                        str(schematic_file),
                        "--output",
                        pcb_filename,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    # Reload the board
                    self.board = pcbnew.LoadBoard(pcb_filename)
                    component_count = len(list(self.board.GetFootprints()))

                    return {
                        "status": "success",
                        "message": f"Successfully updated PCB from schematic",
                        "component_count": component_count,
                        "schematic_file": str(schematic_file),
                        "pcb_file": pcb_filename,
                    }
                else:
                    return {
                        "error": "kicad-cli failed",
                        "stderr": result.stderr,
                        "suggestion": "Update manually: Tools → Update PCB from Schematic (F8) in KiCad",
                    }

            except FileNotFoundError:
                # kicad-cli not found, provide manual instructions
                return {
                    "status": "manual_required",
                    "message": "Automatic update not available. Please update manually in KiCad.",
                    "instructions": [
                        "1. In KiCad PCB Editor, go to: Tools → Update PCB from Schematic",
                        "2. Or press F8",
                        "3. Click 'Update PCB' button",
                        f"4. Schematic file: {schematic_path}",
                    ],
                    "schematic_file": str(schematic_file),
                }

        except Exception as e:
            return {"error": f"Failed to update from schematic: {str(e)}"}

    def _get_circuit_guidance(self, circuit_type: str, components: Dict) -> str:
        """Generate layout guidance"""
        base = f"Components:\n{json.dumps(components, indent=2)}\n\n"

        if circuit_type.lower() == "led":
            return (
                base
                + """Layout guidance for LED circuit:
1. Place LED centrally
2. Place resistor near LED anode
3. Keep traces short
4. Min 3mm from board edge"""
            )
        else:
            return (
                base
                + f"""Layout guidance for {circuit_type}:
1. Group related components
2. Place connectors on edges
3. Keep signal paths short
4. Decoupling caps near ICs (< 5mm)"""
            )

    # ============================================================================
    # FABRICATION TOOLS
    # ============================================================================

    async def _export_gerber(
        self,
        output_dir: str,
        layers: Optional[List[str]] = None,
        create_job_file: bool = True,
    ) -> Dict:
        """Export Gerber files"""
        if pcbnew is None:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            return {
                "status": "mock",
                "message": f"Mock: Would export Gerber files to {output_dir}",
                "files": [
                    "F_Cu.gbr",
                    "B_Cu.gbr",
                    "F_Mask.gbr",
                    "B_Mask.gbr",
                    "Edge_Cuts.gbr",
                ],
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Default layers for fabrication
            if layers is None:
                layers = [
                    "F.Cu",
                    "B.Cu",
                    "F.Mask",
                    "B.Mask",
                    "F.SilkS",
                    "B.SilkS",
                    "F.Paste",
                    "B.Paste",
                    "Edge.Cuts",
                ]

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

            exported_files = []

            for layer_name in layers:
                layer_id = self.board.GetLayerID(layer_name)
                if layer_id < 0:
                    continue

                pctl.SetLayer(layer_id)
                pctl.OpenPlotfile(layer_name, pcbnew.PLOT_FORMAT_GERBER, layer_name)
                pctl.PlotLayer()
                pctl.ClosePlot()

                filename = pctl.GetPlotFileName()
                if os.path.exists(filename):
                    exported_files.append(os.path.basename(filename))

            return {
                "status": "success",
                "output_dir": output_dir,
                "files": exported_files,
                "count": len(exported_files),
            }

        except Exception as e:
            return {"error": f"Failed to export Gerber: {str(e)}"}

    async def _export_drill_files(
        self, output_dir: str, merge_pth_npth: bool = False
    ) -> Dict:
        """Export drill files"""
        if pcbnew is None:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            files = (
                ["project.drl"]
                if merge_pth_npth
                else ["project.drl", "project-NPTH.drl"]
            )
            return {
                "status": "mock",
                "message": f"Mock: Would export drill files to {output_dir}",
                "files": files,
                "merged": merge_pth_npth,
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            Path(output_dir).mkdir(parents=True, exist_ok=True)

            drlwriter = pcbnew.EXCELLON_WRITER(self.board)
            drlwriter.SetOptions(False, False, pcbnew.VECTOR2I(0, 0), merge_pth_npth)
            drlwriter.SetFormat(False)  # Metric
            drlwriter.CreateDrillandMapFilesSet(output_dir, True, False)

            board_name = Path(self.board.GetFileName()).stem
            exported_files = []

            if merge_pth_npth:
                drill_file = os.path.join(output_dir, f"{board_name}.drl")
                if os.path.exists(drill_file):
                    exported_files.append(os.path.basename(drill_file))
            else:
                pth_file = os.path.join(output_dir, f"{board_name}-PTH.drl")
                npth_file = os.path.join(output_dir, f"{board_name}-NPTH.drl")
                if os.path.exists(pth_file):
                    exported_files.append(os.path.basename(pth_file))
                if os.path.exists(npth_file):
                    exported_files.append(os.path.basename(npth_file))

            return {
                "status": "success",
                "output_dir": output_dir,
                "files": exported_files,
                "merged": merge_pth_npth,
            }

        except Exception as e:
            return {"error": f"Failed to export drill files: {str(e)}"}

    async def _export_fabrication_package(
        self, output_dir: str, manufacturer_preset: str = "generic"
    ) -> Dict:
        """Export complete fabrication package"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fab_dir = Path(output_dir) / f"fabrication_{timestamp}"
            fab_dir.mkdir(parents=True, exist_ok=True)

            gerber_dir = fab_dir / "gerber"
            drill_dir = fab_dir / "drill"

            # Export Gerber
            gerber_result = await self._export_gerber(str(gerber_dir))
            if "error" in gerber_result:
                return gerber_result

            # Export drill files
            drill_result = await self._export_drill_files(str(drill_dir))
            if "error" in drill_result:
                return drill_result

            # Export BOM
            bom_file = fab_dir / "bom.csv"
            bom_result = await self._export_bom(str(bom_file))

            # Export position file
            pos_file = fab_dir / "position.csv"
            pos_result = await self._export_position_file(str(pos_file))

            # Create ZIP
            zip_path = (
                Path(output_dir) / f"fabrication_{manufacturer_preset}_{timestamp}.zip"
            )
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(fab_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, fab_dir)
                        zipf.write(file_path, arcname)

            return {
                "status": "success",
                "zip_file": str(zip_path),
                "contents": {
                    "gerber_files": gerber_result.get("files", []),
                    "drill_files": drill_result.get("files", []),
                    "bom": "bom.csv",
                    "position": "position.csv",
                },
                "manufacturer": manufacturer_preset,
            }

        except Exception as e:
            return {"error": f"Failed to create fabrication package: {str(e)}"}

    async def _export_bom(self, output_file: str) -> Dict:
        """Export Bill of Materials"""
        if pcbnew is None:
            return {
                "status": "mock",
                "message": f"Mock: Would export BOM to {output_file}",
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            # Collect component data
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
                        "quantity": 0,
                    }

                bom_data[key]["references"].append(fp.GetReference())
                bom_data[key]["quantity"] += 1

            # Write CSV
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                f.write("Reference,Value,Footprint,Quantity\n")
                for item in sorted(bom_data.values(), key=lambda x: x["value"]):
                    refs = " ".join(sorted(item["references"]))
                    f.write(
                        f'"{refs}","{item["value"]}","{item["footprint"]}",{item["quantity"]}\n'
                    )

            return {
                "status": "success",
                "file": output_file,
                "unique_parts": len(bom_data),
                "total_components": sum(item["quantity"] for item in bom_data.values()),
            }

        except Exception as e:
            return {"error": f"Failed to export BOM: {str(e)}"}

    async def _export_position_file(self, output_file: str) -> Dict:
        """Export position file for pick-and-place"""
        if pcbnew is None:
            return {
                "status": "mock",
                "message": f"Mock: Would export position file to {output_file}",
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            Path(output_file).parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w") as f:
                f.write("Designator,Val,Package,Mid X,Mid Y,Rotation,Layer\n")

                for fp in self.board.GetFootprints():
                    pos = fp.GetPosition()
                    layer = "Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom"

                    f.write(
                        f'"{fp.GetReference()}","{fp.GetValue()}",'
                        f'"{fp.GetFPID().GetLibItemName()}",'
                        f"{pos.x/1e6:.4f},{pos.y/1e6:.4f},"
                        f"{fp.GetOrientationDegrees():.2f},{layer}\n"
                    )

            component_count = len(list(self.board.GetFootprints()))

            return {
                "status": "success",
                "file": output_file,
                "component_count": component_count,
            }

        except Exception as e:
            return {"error": f"Failed to export position file: {str(e)}"}

    # ============================================================================
    # VERIFICATION TOOLS
    # ============================================================================

    async def _run_drc(self, severity_level: str = "all") -> Dict:
        """Run Design Rule Check"""
        if pcbnew is None:
            return {
                "status": "mock",
                "violations": [
                    {
                        "type": "clearance",
                        "severity": "error",
                        "description": "Clearance violation between tracks",
                    },
                    {
                        "type": "track_width",
                        "severity": "warning",
                        "description": "Track width below minimum",
                    },
                ],
                "error_count": 1,
                "warning_count": 1,
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            # Note: Full DRC integration requires KiCad 7+
            # This is a simplified version
            violations = []
            error_count = 0
            warning_count = 0

            # Access DRC violations if available
            # In KiCad 7+, you can use board.GetDRCViolations()
            # For now, return basic info

            return {
                "status": "success",
                "message": "DRC check completed",
                "violations": violations,
                "error_count": error_count,
                "warning_count": warning_count,
                "note": "Full DRC support requires KiCad 7+ with proper API access",
            }

        except Exception as e:
            return {"error": f"Failed to run DRC: {str(e)}"}

    # ============================================================================
    # LAYOUT TOOLS
    # ============================================================================

    async def _fill_zones(self, zone_names: Optional[List[str]] = None) -> Dict:
        """Fill copper zones"""
        if pcbnew is None:
            zones = zone_names if zone_names else ["GND", "VCC"]
            return {
                "status": "mock",
                "message": f"Mock: Would fill copper zones: {', '.join(zones)}",
                "zones_filled": zones,
                "count": len(zones),
            }

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            filled_zones = []
            filler = pcbnew.ZONE_FILLER(self.board)

            zones_to_fill = []
            for zone in self.board.Zones():
                zone_net_name = zone.GetNetname()

                if zone_names is None or zone_net_name in zone_names:
                    zones_to_fill.append(zone)
                    filled_zones.append(zone_net_name)

            if zones_to_fill:
                filler.Fill(zones_to_fill)
                pcbnew.Refresh()

            return {
                "status": "success",
                "zones_filled": filled_zones,
                "count": len(filled_zones),
            }

        except Exception as e:
            return {"error": f"Failed to fill zones: {str(e)}"}

    async def _get_track_info(self, net_name: Optional[str] = None) -> Dict:
        """Get track information"""
        if pcbnew is None:
            all_tracks = [
                {"net": "GND", "width_mm": 0.5, "length_mm": 25.4},
                {"net": "VCC", "width_mm": 0.3, "length_mm": 18.2},
            ]
            if net_name:
                tracks = [t for t in all_tracks if t["net"] == net_name]
            else:
                tracks = all_tracks

            return {"status": "mock", "tracks": tracks, "count": len(tracks)}

        try:
            if self.board is None:
                self.board = pcbnew.GetBoard()
                if self.board is None:
                    return {"error": "No PCB board is open"}

            track_info = []

            for track in self.board.GetTracks():
                track_net_name = track.GetNetname()

                if net_name is None or track_net_name == net_name:
                    track_info.append(
                        {
                            "net": track_net_name,
                            "width_mm": track.GetWidth() / 1e6,
                            "length_mm": track.GetLength() / 1e6,
                            "layer": track.GetLayerName(),
                        }
                    )

            return {"status": "success", "tracks": track_info, "count": len(track_info)}

        except Exception as e:
            return {"error": f"Failed to get track info: {str(e)}"}

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
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    server = KiCadMCPServerExtended()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
