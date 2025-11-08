"""
Pydantic schemas for MCP-KiCad tool input validation.

Provides type-safe, validated schemas for all tool inputs with:
- Comprehensive validation rules
- Clear error messages
- Default values
- Documentation
- Examples
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# Enums for constrained choices

class LayerType(str, Enum):
    """Board layer types following KiCad naming conventions."""

    F_CU = "F.Cu"  # Front copper
    B_CU = "B.Cu"  # Back copper
    F_SILKSCREEN = "F.SilkS"  # Front silkscreen
    B_SILKSCREEN = "B.SilkS"  # Back silkscreen
    F_MASK = "F.Mask"  # Front solder mask
    B_MASK = "B.Mask"  # Back solder mask
    F_PASTE = "F.Paste"  # Front solder paste
    B_PASTE = "B.Paste"  # Back solder paste
    EDGE_CUTS = "Edge.Cuts"  # Board outline


class ManufacturerPreset(str, Enum):
    """Manufacturer-specific export presets."""

    JLCPCB = "jlcpcb"
    PCBWAY = "pcbway"
    OSHPARK = "oshpark"
    GENERIC = "generic"


class SeverityLevel(str, Enum):
    """DRC severity levels."""

    ERROR = "error"
    WARNING = "warning"
    ALL = "all"


# Input Schemas

class PlaceComponentInput(BaseModel):
    """
    Input schema for place_component tool.

    Places or moves a component on the PCB board to a specific position
    with optional rotation.
    """

    reference: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Component reference designator (e.g., 'R1', 'U1', 'C5')",
        examples=["R1", "U10", "C22", "D3"],
    )

    x_mm: float = Field(
        ...,
        ge=-1000.0,
        le=1000.0,
        description="X coordinate in millimeters",
        examples=[10.0, 50.5, 100.0],
    )

    y_mm: float = Field(
        ...,
        ge=-1000.0,
        le=1000.0,
        description="Y coordinate in millimeters",
        examples=[20.0, 30.5, 75.0],
    )

    rotation_deg: float = Field(
        default=0.0,
        description="Rotation angle in degrees (0, 90, 180, or 270)",
        examples=[0.0, 90.0, 180.0, 270.0],
    )

    @field_validator('reference')
    @classmethod
    def validate_reference(cls, v: str) -> str:
        """Validate component reference format."""
        # Standard pattern: Letters followed by numbers (e.g., R1, U10, C22)
        pattern = r'^[A-Z]+\d+$'
        if not re.match(pattern, v, re.IGNORECASE):
            raise ValueError(
                f"Invalid reference '{v}'. Must match pattern like 'R1', 'U10', 'C5'"
            )
        return v.upper()

    @field_validator('rotation_deg')
    @classmethod
    def validate_rotation(cls, v: float) -> float:
        """Ensure rotation is in standard angles."""
        valid_angles = [0.0, 90.0, 180.0, 270.0]
        if v not in valid_angles:
            # Try to round to nearest valid angle
            closest = min(valid_angles, key=lambda x: abs(x - v))
            if abs(closest - v) > 5.0:  # Only auto-correct if within 5 degrees
                raise ValueError(
                    f"Rotation must be 0, 90, 180, or 270 degrees. Got {v}. "
                    f"Did you mean {closest}?"
                )
            return closest
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reference": "R1",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "rotation_deg": 0.0,
                },
                {
                    "reference": "U1",
                    "x_mm": 50.5,
                    "y_mm": 30.5,
                    "rotation_deg": 90.0,
                },
            ]
        }
    }


class ExportGerberInput(BaseModel):
    """Input schema for export_gerber tool."""

    output_dir: str = Field(
        ...,
        description="Output directory for Gerber files",
        examples=["./gerbers", "/tmp/exports/gerber"],
    )

    layers: Optional[List[str]] = Field(
        default=None,
        description="Specific layers to export (None = all standard layers)",
        examples=[["F.Cu", "B.Cu", "Edge.Cuts"], None],
    )

    create_job_file: bool = Field(
        default=True,
        description="Create Gerber job file (.gbrjob)",
    )

    @field_validator('output_dir')
    @classmethod
    def validate_output_dir(cls, v: str) -> str:
        """Validate and normalize output directory path."""
        path = Path(v).expanduser()

        # Security: Check for path traversal attempts
        try:
            path.resolve().relative_to(Path.cwd().resolve().parent)
        except ValueError:
            # Path is outside current working directory tree
            # This is allowed but should be logged
            pass

        # Ensure parent directory exists
        if not path.parent.exists():
            raise ValueError(
                f"Parent directory does not exist: {path.parent}. "
                f"Create it first or use an existing directory."
            )

        return str(path)

    @field_validator('layers')
    @classmethod
    def validate_layers(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate layer names if provided."""
        if v is not None:
            valid_patterns = [
                r'^F\.Cu$', r'^B\.Cu$',
                r'^F\.SilkS$', r'^B\.SilkS$',
                r'^F\.Mask$', r'^B\.Mask$',
                r'^F\.Paste$', r'^B\.Paste$',
                r'^Edge\.Cuts$',
                r'^In\d+\.Cu$',  # Internal layers
            ]

            for layer in v:
                if not any(re.match(pattern, layer) for pattern in valid_patterns):
                    raise ValueError(
                        f"Invalid layer name '{layer}'. Must be a valid KiCad layer "
                        f"like 'F.Cu', 'B.Cu', 'Edge.Cuts', etc."
                    )

        return v


class ExportDrillInput(BaseModel):
    """Input schema for export_drill_files tool."""

    output_dir: str = Field(
        ...,
        description="Output directory for drill files",
        examples=["./drill", "/tmp/exports/drill"],
    )

    merge_pth_npth: bool = Field(
        default=False,
        description="Merge plated (PTH) and non-plated (NPTH) holes into one file",
    )

    @field_validator('output_dir')
    @classmethod
    def validate_output_dir(cls, v: str) -> str:
        """Validate output directory."""
        path = Path(v).expanduser()
        if not path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {path.parent}")
        return str(path)


class ExportFabricationPackageInput(BaseModel):
    """Input schema for export_fabrication_package tool."""

    output_dir: str = Field(
        ...,
        description="Output directory for fabrication package",
        examples=["./fabrication", "/tmp/exports/fab"],
    )

    manufacturer_preset: ManufacturerPreset = Field(
        default=ManufacturerPreset.GENERIC,
        description="Manufacturer preset for naming conventions and file organization",
    )

    @field_validator('output_dir')
    @classmethod
    def validate_output_dir(cls, v: str) -> str:
        """Validate output directory."""
        path = Path(v).expanduser()
        if not path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {path.parent}")
        return str(path)


class ExportBOMInput(BaseModel):
    """Input schema for export_bom tool."""

    output_file: str = Field(
        ...,
        description="Output CSV file path for Bill of Materials",
        examples=["./bom.csv", "/tmp/project_bom.csv"],
    )

    @field_validator('output_file')
    @classmethod
    def validate_output_file(cls, v: str) -> str:
        """Validate output file path."""
        path = Path(v).expanduser()

        # Check extension
        if path.suffix.lower() != '.csv':
            raise ValueError(
                f"Output file must have .csv extension, got: {path.suffix}"
            )

        # Check parent directory exists
        if not path.parent.exists():
            raise ValueError(
                f"Parent directory does not exist: {path.parent}"
            )

        return str(path)


class ExportPositionInput(BaseModel):
    """Input schema for export_position_file tool."""

    output_file: str = Field(
        ...,
        description="Output CSV file path for component positions",
        examples=["./positions.csv", "/tmp/project_positions.csv"],
    )

    @field_validator('output_file')
    @classmethod
    def validate_output_file(cls, v: str) -> str:
        """Validate output file path."""
        path = Path(v).expanduser()

        if path.suffix.lower() != '.csv':
            raise ValueError(
                f"Output file must have .csv extension, got: {path.suffix}"
            )

        if not path.parent.exists():
            raise ValueError(
                f"Parent directory does not exist: {path.parent}"
            )

        return str(path)


class RunDRCInput(BaseModel):
    """Input schema for run_drc tool."""

    severity_level: SeverityLevel = Field(
        default=SeverityLevel.ALL,
        description="Minimum severity level to report",
    )


class FillZonesInput(BaseModel):
    """Input schema for fill_zones tool."""

    zone_names: Optional[List[str]] = Field(
        default=None,
        description="Specific zone net names to fill (None = all zones)",
        examples=[["GND", "VCC"], None],
    )

    @field_validator('zone_names')
    @classmethod
    def validate_zone_names(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate zone names if provided."""
        if v is not None:
            for name in v:
                if not isinstance(name, str) or len(name) == 0:
                    raise ValueError(f"Invalid zone name: {name}")
        return v


class GetTrackInfoInput(BaseModel):
    """Input schema for get_track_info tool."""

    net_name: Optional[str] = Field(
        default=None,
        description="Filter tracks by net name (None = all tracks)",
        examples=["GND", "VCC", "+3V3", None],
    )


# Output Schemas

class ComponentInfo(BaseModel):
    """Schema for component information."""

    reference: str = Field(description="Component reference designator")
    value: str = Field(description="Component value")
    footprint: str = Field(description="Footprint name")
    x_mm: float = Field(description="X coordinate in mm")
    y_mm: float = Field(description="Y coordinate in mm")
    rotation_deg: float = Field(description="Rotation angle in degrees")
    layer: str = Field(description="Layer name")


class OperationResponse(BaseModel):
    """Standard response for all operations."""

    status: str = Field(
        description="Operation status (success, error, mock)"
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable message"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Operation-specific data"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-critical warnings"
    )
    duration_ms: Optional[float] = Field(
        default=None,
        description="Operation duration in milliseconds"
    )
    visual_diff_url: Optional[str] = Field(
        default=None,
        description="URL to visual diff image if available"
    )


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")
    severity: Optional[str] = Field(default=None, description="Error severity")
    remediation_steps: List[str] = Field(default_factory=list, description="Steps to resolve")
    context: Dict[str, Any] = Field(default_factory=dict, description="Error context")
    can_retry: bool = Field(default=False, description="Whether retry might succeed")
