#!/usr/bin/env python3
"""
Test suite for Pydantic input validation schemas (Phase 2).

Tests all tool input schemas, validators, and error handling.
"""

import pytest
from pathlib import Path
from pydantic import ValidationError
from mcp_kicad.schemas.tools import (
    PlaceComponentInput,
    ExportGerberInput,
    ExportDrillInput,
    ExportFabricationPackageInput,
    ExportBOMInput,
    ExportPositionInput,
    RunDRCInput,
    FillZonesInput,
    GetTrackInfoInput,
    LayerType,
    ManufacturerPreset,
    SeverityLevel,
    ComponentInfo,
    OperationResponse,
    ErrorResponse,
)

# ============================================================================
# PlaceComponentInput TESTS
# ============================================================================


def test_place_component_valid_input():
    """Test PlaceComponentInput with valid data"""
    input_data = PlaceComponentInput(
        reference="R1", x_mm=10.0, y_mm=20.0, rotation_deg=90.0
    )

    assert input_data.reference == "R1"
    assert input_data.x_mm == 10.0
    assert input_data.y_mm == 20.0
    assert input_data.rotation_deg == 90.0


def test_place_component_reference_uppercase():
    """Test that reference is converted to uppercase"""
    input_data = PlaceComponentInput(reference="r1", x_mm=10.0, y_mm=20.0)

    assert input_data.reference == "R1"


def test_place_component_invalid_reference():
    """Test reference validation with invalid format"""
    with pytest.raises(ValidationError) as exc_info:
        PlaceComponentInput(reference="INVALID", x_mm=10.0, y_mm=20.0)  # Missing number

    assert "Invalid reference" in str(exc_info.value)


def test_place_component_reference_patterns():
    """Test various valid reference patterns"""
    valid_refs = ["R1", "U10", "C22", "D3", "LED5", "SW1"]

    for ref in valid_refs:
        input_data = PlaceComponentInput(reference=ref, x_mm=10.0, y_mm=20.0)
        assert input_data.reference == ref.upper()


def test_place_component_rotation_validation():
    """Test rotation angle validation"""
    # Valid rotations
    valid_rotations = [0.0, 90.0, 180.0, 270.0]

    for rotation in valid_rotations:
        input_data = PlaceComponentInput(
            reference="R1", x_mm=10.0, y_mm=20.0, rotation_deg=rotation
        )
        assert input_data.rotation_deg == rotation


def test_place_component_rotation_auto_correction():
    """Test rotation auto-correction for close angles"""
    # Should auto-correct 92.0 to 90.0
    input_data = PlaceComponentInput(
        reference="R1", x_mm=10.0, y_mm=20.0, rotation_deg=92.0
    )
    assert input_data.rotation_deg == 90.0


def test_place_component_rotation_invalid():
    """Test invalid rotation angle"""
    with pytest.raises(ValidationError) as exc_info:
        PlaceComponentInput(
            reference="R1",
            x_mm=10.0,
            y_mm=20.0,
            rotation_deg=45.0,  # Not a standard angle
        )

    assert "Rotation must be" in str(exc_info.value)


def test_place_component_coordinate_ranges():
    """Test coordinate range validation"""
    # Valid coordinates
    input_data = PlaceComponentInput(reference="R1", x_mm=999.9, y_mm=-999.9)
    assert input_data.x_mm == 999.9
    assert input_data.y_mm == -999.9

    # Invalid coordinates (out of range)
    with pytest.raises(ValidationError):
        PlaceComponentInput(reference="R1", x_mm=1001.0, y_mm=20.0)  # > 1000


def test_place_component_default_rotation():
    """Test default rotation value"""
    input_data = PlaceComponentInput(reference="R1", x_mm=10.0, y_mm=20.0)
    assert input_data.rotation_deg == 0.0


# ============================================================================
# ExportGerberInput TESTS
# ============================================================================


def test_export_gerber_valid_input(tmp_path):
    """Test ExportGerberInput with valid data"""
    output_dir = tmp_path / "gerber"

    input_data = ExportGerberInput(output_dir=str(output_dir), create_job_file=True)

    assert input_data.create_job_file is True


def test_export_gerber_with_layers():
    """Test ExportGerberInput with specific layers"""
    input_data = ExportGerberInput(
        output_dir="./gerber", layers=["F.Cu", "B.Cu", "Edge.Cuts"]
    )

    assert len(input_data.layers) == 3
    assert "F.Cu" in input_data.layers


def test_export_gerber_invalid_layer():
    """Test layer name validation"""
    with pytest.raises(ValidationError) as exc_info:
        ExportGerberInput(output_dir="./gerber", layers=["InvalidLayer"])

    assert "Invalid layer name" in str(exc_info.value)


def test_export_gerber_internal_layers():
    """Test internal copper layer validation"""
    input_data = ExportGerberInput(output_dir="./gerber", layers=["In1.Cu", "In2.Cu"])

    assert input_data.layers == ["In1.Cu", "In2.Cu"]


def test_export_gerber_default_job_file():
    """Test default create_job_file value"""
    input_data = ExportGerberInput(output_dir="./gerber")
    assert input_data.create_job_file is True


# ============================================================================
# ExportDrillInput TESTS
# ============================================================================


def test_export_drill_valid_input(tmp_path):
    """Test ExportDrillInput with valid data"""
    output_dir = tmp_path / "drill"

    input_data = ExportDrillInput(output_dir=str(output_dir), merge_pth_npth=True)

    assert input_data.merge_pth_npth is True


def test_export_drill_default_merge():
    """Test default merge_pth_npth value"""
    input_data = ExportDrillInput(output_dir="./drill")
    assert input_data.merge_pth_npth is False


# ============================================================================
# ExportFabricationPackageInput TESTS
# ============================================================================


def test_export_fabrication_package_valid_input(tmp_path):
    """Test ExportFabricationPackageInput with valid data"""
    output_dir = tmp_path / "fab"

    input_data = ExportFabricationPackageInput(
        output_dir=str(output_dir), manufacturer_preset=ManufacturerPreset.JLCPCB
    )

    assert input_data.manufacturer_preset == ManufacturerPreset.JLCPCB


def test_export_fabrication_package_presets():
    """Test all manufacturer presets"""
    presets = [
        ManufacturerPreset.JLCPCB,
        ManufacturerPreset.PCBWAY,
        ManufacturerPreset.OSHPARK,
        ManufacturerPreset.GENERIC,
    ]

    for preset in presets:
        input_data = ExportFabricationPackageInput(
            output_dir="./fab", manufacturer_preset=preset
        )
        assert input_data.manufacturer_preset == preset


def test_export_fabrication_package_default_preset():
    """Test default manufacturer preset"""
    input_data = ExportFabricationPackageInput(output_dir="./fab")
    assert input_data.manufacturer_preset == ManufacturerPreset.GENERIC


# ============================================================================
# ExportBOMInput TESTS
# ============================================================================


def test_export_bom_valid_input(tmp_path):
    """Test ExportBOMInput with valid CSV file"""
    output_file = tmp_path / "bom.csv"

    input_data = ExportBOMInput(output_file=str(output_file))
    assert output_file.suffix == ".csv"


def test_export_bom_invalid_extension(tmp_path):
    """Test BOM output file extension validation"""
    with pytest.raises(ValidationError) as exc_info:
        ExportBOMInput(output_file=str(tmp_path / "bom.txt"))

    assert ".csv extension" in str(exc_info.value)


def test_export_bom_expanduser():
    """Test that ~ is expanded in paths"""
    input_data = ExportBOMInput(output_file="~/bom.csv")
    assert "~" not in input_data.output_file


# ============================================================================
# ExportPositionInput TESTS
# ============================================================================


def test_export_position_valid_input(tmp_path):
    """Test ExportPositionInput with valid CSV file"""
    output_file = tmp_path / "positions.csv"

    input_data = ExportPositionInput(output_file=str(output_file))
    assert output_file.suffix == ".csv"


def test_export_position_invalid_extension(tmp_path):
    """Test position file extension validation"""
    with pytest.raises(ValidationError) as exc_info:
        ExportPositionInput(output_file=str(tmp_path / "pos.xlsx"))

    assert ".csv extension" in str(exc_info.value)


# ============================================================================
# RunDRCInput TESTS
# ============================================================================


def test_run_drc_valid_input():
    """Test RunDRCInput with valid severity"""
    input_data = RunDRCInput(severity_level=SeverityLevel.ERROR)
    assert input_data.severity_level == SeverityLevel.ERROR


def test_run_drc_severity_levels():
    """Test all severity levels"""
    levels = [SeverityLevel.ERROR, SeverityLevel.WARNING, SeverityLevel.ALL]

    for level in levels:
        input_data = RunDRCInput(severity_level=level)
        assert input_data.severity_level == level


def test_run_drc_default_severity():
    """Test default severity level"""
    input_data = RunDRCInput()
    assert input_data.severity_level == SeverityLevel.ALL


# ============================================================================
# FillZonesInput TESTS
# ============================================================================


def test_fill_zones_valid_input():
    """Test FillZonesInput with zone names"""
    input_data = FillZonesInput(zone_names=["GND", "VCC"])
    assert len(input_data.zone_names) == 2
    assert "GND" in input_data.zone_names


def test_fill_zones_all_zones():
    """Test FillZonesInput for all zones"""
    input_data = FillZonesInput(zone_names=None)
    assert input_data.zone_names is None


def test_fill_zones_invalid_names():
    """Test zone name validation"""
    with pytest.raises(ValidationError) as exc_info:
        FillZonesInput(zone_names=[""])

    assert "Invalid zone name" in str(exc_info.value)


def test_fill_zones_default():
    """Test default zone names"""
    input_data = FillZonesInput()
    assert input_data.zone_names is None


# ============================================================================
# GetTrackInfoInput TESTS
# ============================================================================


def test_get_track_info_valid_input():
    """Test GetTrackInfoInput with net name"""
    input_data = GetTrackInfoInput(net_name="GND")
    assert input_data.net_name == "GND"


def test_get_track_info_all_tracks():
    """Test GetTrackInfoInput for all tracks"""
    input_data = GetTrackInfoInput(net_name=None)
    assert input_data.net_name is None


def test_get_track_info_default():
    """Test default net name"""
    input_data = GetTrackInfoInput()
    assert input_data.net_name is None


# ============================================================================
# ENUM TESTS
# ============================================================================


def test_layer_type_enum():
    """Test LayerType enum values"""
    assert LayerType.F_CU.value == "F.Cu"
    assert LayerType.B_CU.value == "B.Cu"
    assert LayerType.EDGE_CUTS.value == "Edge.Cuts"


def test_manufacturer_preset_enum():
    """Test ManufacturerPreset enum values"""
    assert ManufacturerPreset.JLCPCB.value == "jlcpcb"
    assert ManufacturerPreset.PCBWAY.value == "pcbway"
    assert ManufacturerPreset.OSHPARK.value == "oshpark"
    assert ManufacturerPreset.GENERIC.value == "generic"


def test_severity_level_enum():
    """Test SeverityLevel enum values"""
    assert SeverityLevel.ERROR.value == "error"
    assert SeverityLevel.WARNING.value == "warning"
    assert SeverityLevel.ALL.value == "all"


# ============================================================================
# OUTPUT SCHEMA TESTS
# ============================================================================


def test_component_info_schema():
    """Test ComponentInfo output schema"""
    component = ComponentInfo(
        reference="R1",
        value="10k",
        footprint="R_0805_2012Metric",
        x_mm=10.0,
        y_mm=20.0,
        rotation_deg=90.0,
        layer="F.Cu",
    )

    assert component.reference == "R1"
    assert component.value == "10k"
    assert component.footprint == "R_0805_2012Metric"


def test_operation_response_schema():
    """Test OperationResponse schema"""
    response = OperationResponse(
        status="success",
        message="Operation completed",
        data={"count": 5},
        warnings=["Warning 1"],
        duration_ms=123.45,
    )

    assert response.status == "success"
    assert response.message == "Operation completed"
    assert response.data["count"] == 5
    assert len(response.warnings) == 1
    assert response.duration_ms == 123.45


def test_operation_response_minimal():
    """Test OperationResponse with minimal fields"""
    response = OperationResponse(status="success")

    assert response.status == "success"
    assert response.message is None
    assert response.data is None
    assert response.warnings == []
    assert response.duration_ms is None


def test_error_response_schema():
    """Test ErrorResponse schema"""
    error = ErrorResponse(
        error="Test error",
        error_code="TEST_001",
        severity="high",
        remediation_steps=["Step 1", "Step 2"],
        context={"key": "value"},
        can_retry=True,
    )

    assert error.error == "Test error"
    assert error.error_code == "TEST_001"
    assert error.severity == "high"
    assert len(error.remediation_steps) == 2
    assert error.context["key"] == "value"
    assert error.can_retry is True


def test_error_response_minimal():
    """Test ErrorResponse with minimal fields"""
    error = ErrorResponse(error="Simple error")

    assert error.error == "Simple error"
    assert error.error_code is None
    assert error.severity is None
    assert error.remediation_steps == []
    assert error.context == {}
    assert error.can_retry is False


# ============================================================================
# TYPE COERCION TESTS
# ============================================================================


def test_type_coercion_string_to_float():
    """Test automatic type coercion from string to float"""
    input_data = PlaceComponentInput(
        reference="R1",
        x_mm="10.5",  # String instead of float
        y_mm="20.3",
        rotation_deg="90.0",
    )

    assert isinstance(input_data.x_mm, float)
    assert input_data.x_mm == 10.5


def test_type_coercion_int_to_float():
    """Test automatic type coercion from int to float"""
    input_data = PlaceComponentInput(
        reference="R1", x_mm=10, y_mm=20  # Int instead of float
    )

    assert isinstance(input_data.x_mm, float)
    assert input_data.x_mm == 10.0


def test_type_coercion_bool():
    """Test boolean type coercion"""
    # String "true" should be coerced to bool
    input_data = ExportGerberInput(output_dir="./gerber", create_job_file="true")

    assert isinstance(input_data.create_job_file, bool)


# ============================================================================
# VALIDATION ERROR MESSAGE TESTS
# ============================================================================


def test_validation_error_messages():
    """Test that validation errors contain helpful messages"""
    with pytest.raises(ValidationError) as exc_info:
        PlaceComponentInput(reference="INVALID_REF", x_mm=10.0, y_mm=20.0)

    error_dict = exc_info.value.errors()[0]
    assert "reference" in str(error_dict)


def test_multiple_validation_errors():
    """Test that multiple validation errors are reported"""
    with pytest.raises(ValidationError) as exc_info:
        PlaceComponentInput(
            reference="BAD",
            x_mm=2000.0,  # Out of range
            y_mm=20.0,
            rotation_deg=45.0,  # Invalid angle
        )

    errors = exc_info.value.errors()
    assert len(errors) >= 2  # At least 2 validation errors


# ============================================================================
# PATH VALIDATION TESTS
# ============================================================================


def test_path_expansion(tmp_path):
    """Test that paths are expanded and normalized"""
    # Create a test directory
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    input_data = ExportGerberInput(output_dir=str(test_dir))

    # Path should be absolute
    assert Path(input_data.output_dir).is_absolute()
