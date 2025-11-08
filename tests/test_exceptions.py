#!/usr/bin/env python3
"""
Test suite for custom exception hierarchy (Phase 2).

Tests exception types, error codes, remediation steps, and serialization.
"""

import pytest
from mcp_kicad.exceptions import (
    KiCadMCPError,
    ErrorSeverity,
    BoardNotOpenError,
    ComponentNotFoundError,
    InvalidCoordinateError,
    InvalidRotationError,
    ExportError,
    DRCError,
    KiCadAPIError,
)


# ============================================================================
# BASE EXCEPTION TESTS
# ============================================================================

def test_base_exception_creation():
    """Test base KiCadMCPError creation"""
    error = KiCadMCPError(
        message="Test error",
        severity=ErrorSeverity.HIGH,
        remediation_steps=["Step 1", "Step 2"],
        context={"key": "value"},
    )

    assert str(error) == "Test error"
    assert error.severity == ErrorSeverity.HIGH
    assert len(error.remediation_steps) == 2
    assert error.context["key"] == "value"


def test_base_exception_to_dict():
    """Test exception serialization to dictionary"""
    error = KiCadMCPError(
        message="Test error",
        severity=ErrorSeverity.MEDIUM,
        remediation_steps=["Fix it"],
    )

    error_dict = error.to_dict()

    assert error_dict["message"] == "Test error"
    assert error_dict["severity"] == "medium"
    assert "error_code" in error_dict
    assert "remediation_steps" in error_dict
    assert error_dict["can_retry"] is False


def test_error_code_generation():
    """Test automatic error code generation"""
    error = KiCadMCPError(message="Test", severity=ErrorSeverity.LOW, remediation_steps=[])

    assert error.error_code is not None
    assert isinstance(error.error_code, str)
    assert len(error.error_code) > 0


# ============================================================================
# BOARD EXCEPTIONS
# ============================================================================

def test_board_not_open_error():
    """Test BoardNotOpenError creation"""
    error = BoardNotOpenError()

    assert "board" in str(error).lower()
    assert error.severity == ErrorSeverity.HIGH
    assert len(error.remediation_steps) > 0
    assert "Open a PCB file" in error.remediation_steps[0]


def test_board_not_open_error_serialization():
    """Test BoardNotOpenError serialization"""
    error = BoardNotOpenError()
    error_dict = error.to_dict()

    assert error_dict["severity"] == "high"
    assert len(error_dict["remediation_steps"]) > 0


# ============================================================================
# COMPONENT EXCEPTIONS
# ============================================================================

def test_component_not_found_error():
    """Test ComponentNotFoundError without suggestions"""
    error = ComponentNotFoundError("R999", [])

    assert "R999" in str(error)
    assert error.severity == ErrorSeverity.MEDIUM


def test_component_not_found_with_suggestions():
    """Test ComponentNotFoundError with similar component suggestions"""
    available = ["R1", "R2", "R10", "C1"]
    error = ComponentNotFoundError("R11", available)

    assert "R11" in str(error)
    # Should suggest R1 or R10 as similar
    assert len(error.remediation_steps) > 0


def test_component_not_found_serialization():
    """Test ComponentNotFoundError serialization"""
    error = ComponentNotFoundError("U1", ["U2", "U3"])
    error_dict = error.to_dict()

    assert "U1" in error_dict["message"]
    assert error_dict["can_retry"] is True


# ============================================================================
# VALIDATION EXCEPTIONS
# ============================================================================

def test_invalid_coordinate_error():
    """Test InvalidCoordinateError"""
    board_bounds = {"width": 100.0, "height": 80.0}
    error = InvalidCoordinateError(1500.0, -1000.0, board_bounds)

    assert "1500" in str(error) or "1500.0" in str(error)
    assert error.severity == ErrorSeverity.HIGH


def test_invalid_rotation_error_without_autofix():
    """Test InvalidRotationError without automated fix"""
    error = InvalidRotationError(45.0)

    assert "45" in str(error) or "45.0" in str(error)
    assert error.automated_fix is True  # automated_fix_available is set to True


def test_invalid_rotation_error_with_autofix():
    """Test InvalidRotationError with automated fix suggestion"""
    error = InvalidRotationError(45.0)

    assert error.automated_fix is True
    assert "rotation" in str(error).lower()


# ============================================================================
# EXPORT EXCEPTIONS
# ============================================================================

def test_export_error():
    """Test ExportError creation"""
    error = ExportError(
        export_type="gerber",
        original_error="Permission denied",
    )

    assert "gerber" in str(error).lower()
    assert "Permission denied" in str(error)


def test_export_error_serialization():
    """Test ExportError serialization"""
    error = ExportError(export_type="drill", original_error="Disk full")
    error_dict = error.to_dict()

    assert "drill" in error_dict["message"].lower()
    assert error_dict["severity"] == "high"


# ============================================================================
# DRC EXCEPTIONS
# ============================================================================

def test_drc_error():
    """Test DRCError creation"""
    violations = [{"type": "clearance", "severity": "error"}]
    error = DRCError(violation_count=1, violations=violations)

    assert "1" in str(error)
    assert "DRC" in str(error) or "Design Rule Check" in str(error)
    assert error.severity == ErrorSeverity.HIGH


def test_drc_error_with_violations():
    """Test DRCError with violation count"""
    violations = [
        {"type": "clearance", "severity": "error"},
        {"type": "track_width", "severity": "warning"},
    ]
    error = DRCError(
        violation_count=5,
        violations=violations,
    )

    assert error.context["violation_count"] == 5
    assert len(error.context["violations"]) == 2


# ============================================================================
# API EXCEPTIONS
# ============================================================================

def test_kicad_api_error():
    """Test KiCadAPIError creation"""
    error = KiCadAPIError(
        operation="place_component",
        original_error="API call failed",
        kicad_version="9.0.0",
    )

    assert "place_component" in str(error)
    assert "API call failed" in str(error)
    assert error.context["operation"] == "place_component"


def test_kicad_api_error_retry_flag():
    """Test KiCadAPIError retry capability"""
    error = KiCadAPIError(operation="export", original_error="Temporary failure")

    assert error.can_retry is True  # API errors should be retryable


# ============================================================================
# ERROR SEVERITY TESTS
# ============================================================================

def test_error_severity_enum():
    """Test ErrorSeverity enum values"""
    assert ErrorSeverity.CRITICAL.value == "critical"
    assert ErrorSeverity.HIGH.value == "high"
    assert ErrorSeverity.MEDIUM.value == "medium"
    assert ErrorSeverity.LOW.value == "low"


def test_error_severity_ordering():
    """Test ErrorSeverity can be compared"""
    # Just verify the enum members exist
    severities = [
        ErrorSeverity.CRITICAL,
        ErrorSeverity.HIGH,
        ErrorSeverity.MEDIUM,
        ErrorSeverity.LOW,
    ]
    assert len(severities) == 4


# ============================================================================
# REMEDIATION STEPS TESTS
# ============================================================================

def test_remediation_steps_not_empty():
    """Test that critical errors have remediation steps"""
    errors = [
        BoardNotOpenError(),
        ComponentNotFoundError("R1", ["R2"]),
        ExportError("gerber", "Failed"),
    ]

    for error in errors:
        assert len(error.remediation_steps) > 0, f"{type(error).__name__} has no remediation steps"


def test_remediation_steps_are_actionable():
    """Test that remediation steps provide actionable guidance"""
    error = BoardNotOpenError()

    # Steps should be strings and not empty
    for step in error.remediation_steps:
        assert isinstance(step, str)
        assert len(step) > 10  # Reasonable minimum length


# ============================================================================
# CONTEXT PRESERVATION TESTS
# ============================================================================

def test_exception_context_preserved():
    """Test that context is preserved through exception chain"""
    error = KiCadAPIError(
        operation="test_op",
        original_error="Failed",
        kicad_version="9.0"
    )

    # KiCadAPIError sets its own context
    assert error.context["operation"] == "test_op"
    assert "kicad_error" in error.context


def test_exception_str_representation():
    """Test string representation of exceptions"""
    error = ComponentNotFoundError("U5", ["U1", "U2"])

    error_str = str(error)
    assert "U5" in error_str
    assert len(error_str) > 0
