"""
Pydantic schemas for input validation and data modeling.

Provides type-safe schemas for all MCP tool inputs with comprehensive
validation rules and error messages.
"""

from mcp_kicad.schemas.tools import (
    # Enums
    LayerType,
    ManufacturerPreset,
    SeverityLevel,
    # Input schemas
    PlaceComponentInput,
    ExportGerberInput,
    ExportDrillInput,
    ExportFabricationPackageInput,
    ExportBOMInput,
    ExportPositionInput,
    RunDRCInput,
    FillZonesInput,
    GetTrackInfoInput,
    # Output schemas
    ComponentInfo,
    OperationResponse,
    ErrorResponse,
)

__all__ = [
    # Enums
    "LayerType",
    "ManufacturerPreset",
    "SeverityLevel",
    # Input schemas
    "PlaceComponentInput",
    "ExportGerberInput",
    "ExportDrillInput",
    "ExportFabricationPackageInput",
    "ExportBOMInput",
    "ExportPositionInput",
    "RunDRCInput",
    "FillZonesInput",
    "GetTrackInfoInput",
    # Output schemas
    "ComponentInfo",
    "OperationResponse",
    "ErrorResponse",
]
