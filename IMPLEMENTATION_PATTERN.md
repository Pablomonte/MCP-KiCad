# Implementation Pattern for Extended Server Methods

This document shows the complete pattern for implementing tool methods with validation, logging, and exception handling in the MCP-KiCad server.

## Pattern Overview

Each tool handler follows this 4-step pattern:

1. **Input validation** with Pydantic schemas
2. **Correlation ID** tracking
3. **Operation context** for automatic logging and timing
4. **Specific exception handling** with remediation steps

## Complete Example: place_component

### Step 1: Tool Handler (in call_tool())

```python
@self.server.call_tool()
async def call_tool(name: str, arguments: Any):
    # Set correlation ID for this request
    set_correlation_id()
    self.logger.info("tool_called", tool_name=name, arguments=arguments)

    try:
        if name == "place_component":
            # Step 1: Validate input
            try:
                validated = PlaceComponentInput(**arguments)
            except ValidationError as e:
                return validation_error_response(e)

            # Step 2: Call implementation method with validated data
            result = await self._place_component(
                validated.reference,
                validated.x_mm,
                validated.y_mm,
                validated.rotation_deg,
            )

            return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

### Step 2: Implementation Method

```python
async def _place_component(
    self,
    reference: str,
    x_mm: float,
    y_mm: float,
    rotation_deg: float = 0.0,
) -> dict:
    """
    Place a component on the board at specified coordinates.

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
    # Operation context for automatic logging and timing
    with operation_context(
        "place_component",
        logger=self.logger,
        reference=reference,
        x_mm=x_mm,
        y_mm=y_mm,
        rotation_deg=rotation_deg,
    ) as ctx:
        # Check for mock mode
        if pcbnew is None:
            self.logger.warning("pcbnew_unavailable", mode="mock")
            return {
                "status": "mock",
                "message": f"Mock: Would place {reference} at ({x_mm}, {y_mm})",
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

            ctx.log_progress("component_placed", reference=reference)

        except Exception as e:
            raise KiCadAPIError(
                operation="place_component",
                details=str(e),
                context={"reference": reference, "position": (x_mm, y_mm)},
            ) from e

        # Return success result
        return {
            "status": "success",
            "message": f"Placed {reference} at ({x_mm}, {y_mm}) with rotation {rotation_deg}°",
            "data": {
                "reference": reference,
                "x_mm": x_mm,
                "y_mm": y_mm,
                "rotation_deg": rotation_deg,
                "footprint": footprint.GetFPID().GetLibItemName(),
                "layer": footprint.GetLayerName(),
            },
        }
```

## Pattern Breakdown

### 1. Input Validation

```python
try:
    validated = ToolNameInput(**arguments)
except ValidationError as e:
    return validation_error_response(e)
```

**Why**:
- Catches invalid inputs before processing
- Provides clear error messages with field-level details
- Type coercion happens automatically
- Custom validators ensure business logic constraints

### 2. Correlation ID

```python
set_correlation_id()
self.logger.info("tool_called", tool_name=name)
```

**Why**:
- Tracks requests across all log entries
- Essential for debugging in production
- Allows filtering logs by specific requests

### 3. Operation Context

```python
with operation_context("operation_name", logger=self.logger, **params) as ctx:
    # ... implementation ...
    ctx.log_progress("step_completed", detail="value")
```

**Why**:
- Automatic start/completion logging
- Automatic timing (duration_ms in logs)
- Automatic error capture with stack traces
- Provides unique operation ID
- Log progress within operation for visibility

**What gets logged automatically**:
```json
// Start
{"event": "operation_started", "operation": "place_component", "operation_id": "a1b2c3d4", "reference": "R1", ...}

// Progress (manual via ctx.log_progress)
{"event": "board_loaded", "operation": "place_component", "operation_id": "a1b2c3d4", "board_name": "test.kicad_pcb"}

// Completion
{"event": "operation_completed", "operation": "place_component", "operation_id": "a1b2c3d4", "duration_ms": 123.45, "status": "success"}
```

### 4. Specific Exceptions

```python
# Check conditions and raise specific exceptions
if self.board is None:
    raise BoardNotOpenError()

if component_not_found:
    raise ComponentNotFoundError(reference, available_components)

try:
    # KiCad API call
except Exception as e:
    raise KiCadAPIError(operation="tool_name", details=str(e)) from e
```

**Why**:
- Provides actionable error messages
- Includes remediation steps for Claude
- Auto-suggests fixes (e.g., similar component names)
- Maintains error context with machine-readable codes
- Allows agents to handle errors intelligently

## Applying Pattern to Fabrication Methods

### Example: export_gerber

```python
async def _export_gerber(
    self,
    output_dir: str,
    layers: Optional[List[str]] = None,
    create_job_file: bool = True,
) -> dict:
    """Export Gerber files for PCB fabrication."""

    with operation_context(
        "export_gerber",
        logger=self.logger,
        output_dir=output_dir,
        layer_count=len(layers) if layers else "all",
    ) as ctx:
        # Mock mode check
        if pcbnew is None:
            self.logger.warning("pcbnew_unavailable", mode="mock")
            return {
                "status": "mock",
                "message": f"Mock: Would export Gerbers to {output_dir}",
            }

        # Board check
        if self.board is None:
            self.board = pcbnew.GetBoard()
            if self.board is None:
                raise BoardNotOpenError()

        ctx.log_progress("board_loaded")

        # Create output directory
        output_path = Path(output_dir)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            ctx.log_progress("output_directory_created", path=str(output_path))
        except OSError as e:
            raise ExportError(
                file_type="gerber",
                reason=f"Cannot create output directory: {e}",
            ) from e

        # Export logic with progress logging
        try:
            plot_controller = pcbnew.PLOT_CONTROLLER(self.board)
            plot_options = plot_controller.GetPlotOptions()

            # Configure plot options
            plot_options.SetOutputDirectory(str(output_path))
            plot_options.SetPlotFrameRef(False)
            # ... more configuration ...

            ctx.log_progress("plot_controller_configured")

            # Determine layers to export
            if layers is None:
                layers_to_plot = self._get_default_layers()
            else:
                layers_to_plot = layers

            ctx.log_progress("exporting_layers", count=len(layers_to_plot))

            # Export each layer
            exported_files = []
            for layer_name in layers_to_plot:
                layer_id = self.board.GetLayerID(layer_name)
                plot_controller.SetLayer(layer_id)
                plot_controller.OpenPlotfile(layer_name, pcbnew.PLOT_FORMAT_GERBER, layer_name)
                plot_controller.PlotLayer()
                plot_controller.ClosePlot()

                filename = plot_controller.GetPlotFileName()
                exported_files.append(filename)

                ctx.log_progress("layer_exported", layer=layer_name, file=filename)

            # Create job file if requested
            if create_job_file:
                # Job file logic...
                ctx.log_progress("job_file_created")

            return {
                "status": "success",
                "message": f"Exported {len(exported_files)} Gerber files to {output_dir}",
                "data": {
                    "output_dir": str(output_path),
                    "files": exported_files,
                    "layer_count": len(exported_files),
                    "job_file_created": create_job_file,
                },
            }

        except Exception as e:
            raise ExportError(
                file_type="gerber",
                reason=str(e),
                context={"output_dir": output_dir, "layers": layers},
            ) from e
```

## Methods Needing Pattern Application

In [extended.py](src/mcp_kicad/server/extended.py), these methods have validation but need full operation context integration:

1. ✅ `_place_component` - **COMPLETE** (shown above)
2. ❌ `_export_gerber` - Needs operation context
3. ❌ `_export_drill_files` - Needs operation context
4. ❌ `_export_fabrication_package` - Needs operation context
5. ❌ `_export_bom` - Needs operation context
6. ❌ `_export_position_file` - Needs operation context
7. ❌ `_run_drc` - Needs operation context
8. ❌ `_fill_zones` - Needs operation context
9. ❌ `_list_components` - Needs operation context
10. ❌ `_get_board_info` - Needs operation context
11. ❌ `_read_netlist` - Needs operation context
12. ❌ `_get_track_info` - Needs operation context

## Checklist for Each Method

- [ ] Add operation_context wrapper with relevant parameters
- [ ] Add mock mode check with warning log
- [ ] Add board loaded check with specific exception
- [ ] Add ctx.log_progress() at key steps:
  - After loading resources
  - Before/after major operations
  - When iterating (with counts)
  - After file creation
- [ ] Replace generic exceptions with specific types
- [ ] Include error context in exception constructors
- [ ] Return structured result dict with status, message, data
- [ ] Include duration and operation metadata

## Testing Pattern

After applying the pattern, test each method:

```python
def test_tool_with_logging(mock_pcbnew, mock_board, mock_logger, caplog):
    """Test tool execution with logging verification."""
    server = KiCadExtendedServer()
    server.board = mock_board

    result = await server._tool_name(param1, param2)

    # Verify result
    assert result["status"] == "success"

    # Verify logging
    assert "operation_started" in caplog.text
    assert "operation_completed" in caplog.text
    assert "duration_ms" in caplog.text
```

## Benefits Summary

This pattern provides:

1. **Consistency**: All tools behave the same way
2. **Observability**: Every operation is fully logged with timing
3. **Debuggability**: Correlation IDs link all logs for a request
4. **Error Recovery**: Specific exceptions with remediation steps
5. **Agent-Friendly**: Claude can interpret errors and retry intelligently
6. **Production-Ready**: Comprehensive logging for production debugging
7. **Type Safety**: Pydantic ensures data correctness
8. **Documentation**: Docstrings with Args/Returns/Raises

## Next Steps

To complete Phase 2 integration:

1. Apply operation_context pattern to remaining 11 methods
2. Add ctx.log_progress() at appropriate points in each method
3. Replace any remaining generic exception handlers
4. Test each method for proper logging output
5. Update tests to verify logging behavior
6. Run full test suite to ensure no regressions
