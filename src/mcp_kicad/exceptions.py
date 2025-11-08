"""
Exception hierarchy for MCP-KiCad with agent-friendly error handling.

Provides structured exceptions with error codes, severity levels,
remediation steps, and contextual information to help AI agents
recover from errors gracefully.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ErrorSeverity(str, Enum):
    """Error severity levels for categorization and handling."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KiCadMCPError(Exception):
    """
    Base exception for all MCP-KiCad errors.

    Provides structured error information including:
    - Unique error code for tracking
    - Severity level
    - Remediation steps for recovery
    - Contextual information
    - Retry capability flag
    - Automated fix availability flag
    """

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        remediation_steps: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        can_retry: bool = False,
        automated_fix_available: bool = False,
    ):
        """
        Initialize KiCad MCP error.

        Args:
            message: Human-readable error description
            severity: Error severity level
            remediation_steps: List of steps to resolve the error
            context: Additional context information (dict)
            can_retry: Whether retrying the operation might succeed
            automated_fix_available: Whether an automated fix is available
        """
        super().__init__(message)
        self.error_code = self._generate_error_code()
        self.severity = severity
        self.remediation_steps = remediation_steps or []
        self.context = context or {}
        self.can_retry = can_retry
        self.automated_fix = automated_fix_available

    def _generate_error_code(self) -> str:
        """Generate unique error code for tracking."""
        class_name = self.__class__.__name__
        return f"{class_name.upper()}_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to dictionary for JSON response."""
        return {
            "error_code": self.error_code,
            "error_type": self.__class__.__name__,
            "message": str(self),
            "severity": self.severity.value,
            "remediation_steps": self.remediation_steps,
            "context": self.context,
            "can_retry": self.can_retry,
            "automated_fix_available": self.automated_fix,
        }


# Board-related errors


class BoardNotOpenError(KiCadMCPError):
    """Raised when no PCB board is currently open in KiCad."""

    def __init__(self):
        message = "No PCB board is currently open in KiCad"
        remediation = [
            "Open a PCB file (.kicad_pcb) in KiCad",
            "Ensure KiCad is running with a project loaded",
            "Verify the MCP server can connect to KiCad instance",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.HIGH,
            remediation_steps=remediation,
            can_retry=True,
        )


class BoardLoadError(KiCadMCPError):
    """Raised when board file cannot be loaded."""

    def __init__(self, file_path: str, original_error: str):
        message = f"Failed to load board from '{file_path}': {original_error}"
        remediation = [
            "Verify the file path is correct and file exists",
            "Check file permissions (must be readable)",
            "Ensure file is a valid KiCad PCB file (.kicad_pcb)",
            "Try opening the file directly in KiCad to verify it's not corrupted",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            remediation_steps=remediation,
            context={"file_path": file_path, "original_error": original_error},
            can_retry=False,
        )


# Component-related errors


class ComponentNotFoundError(KiCadMCPError):
    """Raised when a component reference doesn't exist on the board."""

    def __init__(self, reference: str, available_components: List[str]):
        message = (
            f"Component '{reference}' not found on board. "
            f"The board contains {len(available_components)} components."
        )

        remediation = [
            "Check component reference spelling - should match pattern like 'U1', 'R10', 'C5'",
            "List available components using list_components tool",
            "If component should exist, verify board file is saved and up-to-date",
        ]

        # Add suggestions for similar references
        from difflib import get_close_matches

        suggestions = get_close_matches(
            reference, available_components, n=3, cutoff=0.6
        )
        if suggestions:
            remediation.insert(0, f"Did you mean: {', '.join(suggestions)}?")

        super().__init__(
            message=message,
            severity=ErrorSeverity.MEDIUM,
            remediation_steps=remediation,
            context={
                "requested_reference": reference,
                "available_components": available_components[:20],  # First 20
                "total_components": len(available_components),
                "suggestions": suggestions,
            },
            can_retry=True,
        )


class InvalidComponentDataError(KiCadMCPError):
    """Raised when component data is invalid or corrupted."""

    def __init__(self, reference: str, issue: str):
        message = f"Invalid data for component '{reference}': {issue}"
        remediation = [
            "Verify component footprint is properly assigned",
            "Check component properties in KiCad schematic",
            "Try updating component from library",
            "Verify library files are not corrupted",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.MEDIUM,
            remediation_steps=remediation,
            context={"reference": reference, "issue": issue},
            can_retry=False,
        )


# Coordinate and geometry errors


class InvalidCoordinateError(KiCadMCPError):
    """Raised when coordinates are outside board bounds or invalid."""

    def __init__(
        self,
        x: float,
        y: float,
        board_bounds: Optional[Dict[str, float]] = None,
    ):
        if board_bounds:
            message = (
                f"Coordinates ({x:.2f}, {y:.2f}) mm are outside board bounds. "
                f"Board size: {board_bounds.get('width', 0):.2f} x "
                f"{board_bounds.get('height', 0):.2f} mm"
            )
            remediation = [
                f"Use coordinates within board bounds: "
                f"X: 0 to {board_bounds.get('width', 0):.2f} mm, "
                f"Y: 0 to {board_bounds.get('height', 0):.2f} mm",
                "Get current board dimensions using get_board_info tool",
                "Consider resizing board if design requires larger area",
            ]
        else:
            message = f"Invalid coordinates: ({x:.2f}, {y:.2f}) mm"
            remediation = [
                "Ensure coordinates are positive numbers",
                "Verify units are in millimeters",
                "Get board dimensions using get_board_info tool",
            ]

        super().__init__(
            message=message,
            severity=ErrorSeverity.HIGH,
            remediation_steps=remediation,
            context={
                "requested_x": x,
                "requested_y": y,
                "board_bounds": board_bounds or {},
            },
            can_retry=True,
            automated_fix_available=True,  # Could auto-clamp to bounds
        )


class InvalidRotationError(KiCadMCPError):
    """Raised when rotation angle is invalid."""

    def __init__(self, rotation: float):
        message = f"Invalid rotation angle: {rotation}°. Must be 0, 90, 180, or 270."
        remediation = [
            "Use standard rotation angles: 0, 90, 180, or 270 degrees",
            "Rotation is specified in degrees (not radians)",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.MEDIUM,
            remediation_steps=remediation,
            context={"requested_rotation": rotation},
            can_retry=True,
            automated_fix_available=True,  # Could round to nearest valid angle
        )


# Validation errors


class ValidationError(KiCadMCPError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, reason: str):
        message = f"Validation failed for '{field}': {reason}"
        remediation = [
            f"Check the value for '{field}': {value}",
            "Review tool documentation for valid input format",
            "Ensure all required fields are provided",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.MEDIUM,
            remediation_steps=remediation,
            context={"field": field, "value": value, "reason": reason},
            can_retry=True,
        )


# File operation errors


class FileOperationError(KiCadMCPError):
    """Raised when file operation fails."""

    def __init__(self, operation: str, file_path: str, original_error: str):
        message = f"Failed to {operation} file '{file_path}': {original_error}"
        remediation = [
            "Verify file path is correct",
            "Check directory exists and is writable",
            "Ensure you have necessary permissions",
            "Check disk space is available",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.HIGH,
            remediation_steps=remediation,
            context={
                "operation": operation,
                "file_path": file_path,
                "original_error": original_error,
            },
            can_retry=True,
        )


class PathTraversalError(KiCadMCPError):
    """Raised when path traversal attempt is detected (security)."""

    def __init__(self, requested_path: str, allowed_base: str):
        message = (
            f"Path traversal detected: '{requested_path}' is outside "
            f"allowed directory '{allowed_base}'"
        )
        remediation = [
            f"Use paths within allowed directory: {allowed_base}",
            "Avoid using '..' in file paths",
            "Use absolute paths within project directory",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            remediation_steps=remediation,
            context={
                "requested_path": requested_path,
                "allowed_base": allowed_base,
            },
            can_retry=False,
        )


# Export errors


class ExportError(KiCadMCPError):
    """Raised when export operation fails."""

    def __init__(self, export_type: str, original_error: str):
        message = f"Failed to export {export_type}: {original_error}"
        remediation = [
            "Verify board is in valid state for export",
            "Check output directory exists and is writable",
            "Ensure all required layers are defined",
            "Try exporting manually in KiCad to verify board validity",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.HIGH,
            remediation_steps=remediation,
            context={"export_type": export_type, "original_error": original_error},
            can_retry=True,
        )


# KiCad API errors


class KiCadAPIError(KiCadMCPError):
    """Raised when KiCad API call fails."""

    def __init__(
        self, operation: str, original_error: str, kicad_version: str = "unknown"
    ):
        message = (
            f"KiCad API operation '{operation}' failed: {original_error}. "
            f"KiCad version: {kicad_version}"
        )

        remediation = [
            "Verify KiCad installation is complete and functional",
            "Check if Python pcbnew module is properly installed: "
            "python3 -c 'import pcbnew; print(pcbnew.GetBuildVersion())'",
            f"Ensure KiCad version {kicad_version} is compatible (requires 9.0+)",
            "Review KiCad logs for detailed error information",
            "Try restarting KiCad application",
        ]

        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            remediation_steps=remediation,
            context={
                "operation": operation,
                "kicad_error": original_error,
                "kicad_version": kicad_version,
            },
            can_retry=True,
        )


class KiCadNotAvailableError(KiCadMCPError):
    """Raised when KiCad/pcbnew is not available."""

    def __init__(self):
        message = "KiCad pcbnew module is not available - running in mock mode"
        remediation = [
            "Install KiCad 9.0 or later",
            "Verify Python bindings are installed with KiCad",
            "For Flatpak: Use appropriate python environment",
            "Test with: python3 -c 'import pcbnew'",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            remediation_steps=remediation,
            can_retry=False,
        )


# DRC and validation errors


class DRCError(KiCadMCPError):
    """Raised when Design Rule Check fails."""

    def __init__(self, violation_count: int, violations: List[Dict[str, Any]]):
        message = f"Design Rule Check failed with {violation_count} violations"
        remediation = [
            "Review DRC violations and fix issues in KiCad",
            "Check trace widths and clearances",
            "Verify board outline is complete",
            "Run DRC in KiCad for detailed violation information",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.HIGH,
            remediation_steps=remediation,
            context={
                "violation_count": violation_count,
                "violations": violations[:10],  # First 10
            },
            can_retry=False,
        )


# Network/connection errors


class ConnectionError(KiCadMCPError):
    """Raised when connection to KiCad fails."""

    def __init__(self, details: str):
        message = f"Failed to connect to KiCad: {details}"
        remediation = [
            "Ensure KiCad is running",
            "Verify KiCad IPC API is enabled (KiCad 9.0+)",
            "Check firewall settings if using remote connection",
            "Restart KiCad and try again",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            remediation_steps=remediation,
            context={"details": details},
            can_retry=True,
        )


class TimeoutError(KiCadMCPError):
    """Raised when operation times out."""

    def __init__(self, operation: str, timeout_seconds: float):
        message = f"Operation '{operation}' timed out after {timeout_seconds}s"
        remediation = [
            "Try with a simpler operation first",
            "Check if KiCad is responsive",
            "Increase timeout setting if operation is legitimately slow",
            "Verify board file is not corrupted",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.HIGH,
            remediation_steps=remediation,
            context={"operation": operation, "timeout_seconds": timeout_seconds},
            can_retry=True,
        )


# State management errors


class StateManagementError(KiCadMCPError):
    """Raised when state management operation fails."""

    def __init__(self, operation: str, details: str):
        message = f"State management error during '{operation}': {details}"
        remediation = [
            "Try clearing state and reloading board",
            "Check if board file has been modified externally",
            "Restart MCP server to reset state",
        ]
        super().__init__(
            message=message,
            severity=ErrorSeverity.MEDIUM,
            remediation_steps=remediation,
            context={"operation": operation, "details": details},
            can_retry=True,
        )
