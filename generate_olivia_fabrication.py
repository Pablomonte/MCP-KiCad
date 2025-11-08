#!/usr/bin/env python3
"""
Generate fabrication files for Olivia Control v0.2 PCB
Reads the PCB from Proyecto-Incubadora and generates files in MCP-KiCad/fabrication_output/
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import zipfile

try:
    import pcbnew
except ImportError:
    print("ERROR: pcbnew module not available")
    print("This script must be run with KiCad's Python:")
    print(
        "  flatpak run --command=python3 org.kicad.KiCad generate_olivia_fabrication.py"
    )
    sys.exit(1)


def main():
    # Paths
    pcb_path = "/home/pablo/repos/Proyecto-Incubadora/HardWare/Electro/Olivia_control/v0.2/v0.2.kicad_pcb"
    output_base = "/home/pablo/repos/MCP-KiCad/fabrication_output"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_base) / f"olivia_v0.2_{timestamp}"
    gerber_dir = output_dir / "gerber"
    drill_dir = output_dir / "drill"

    print("=" * 70)
    print("Olivia Control v0.2 - Fabrication File Generator")
    print("=" * 70)
    print()

    # Verify PCB exists
    if not os.path.exists(pcb_path):
        print(f"ERROR: PCB file not found: {pcb_path}")
        sys.exit(1)

    print(f"Input PCB: {pcb_path}")
    print(f"Output directory: {output_dir}")
    print()

    # Create output directories
    gerber_dir.mkdir(parents=True, exist_ok=True)
    drill_dir.mkdir(parents=True, exist_ok=True)

    # Load the board
    print("Loading PCB...")
    board = pcbnew.LoadBoard(pcb_path)

    if not board:
        print("ERROR: Failed to load PCB")
        sys.exit(1)

    # Get board info
    bbox = board.GetBoardEdgesBoundingBox()
    width_mm = bbox.GetWidth() / 1e6
    height_mm = bbox.GetHeight() / 1e6
    layer_count = board.GetCopperLayerCount()
    component_count = len(list(board.GetFootprints()))

    print(f"✓ PCB loaded successfully")
    print(f"  Size: {width_mm:.1f} x {height_mm:.1f} mm")
    print(f"  Layers: {layer_count}")
    print(f"  Components: {component_count}")
    print()

    # ========================================================================
    # 1. EXPORT GERBER FILES
    # ========================================================================
    print("Generating Gerber files...")

    pctl = pcbnew.PLOT_CONTROLLER(board)
    popt = pctl.GetPlotOptions()

    # Configure plot options - using only methods available in KiCad 9.x
    popt.SetOutputDirectory(str(gerber_dir))

    # Basic plot settings
    try:
        popt.SetPlotFrameRef(False)
    except:
        pass

    try:
        popt.SetPlotValue(True)
        popt.SetPlotReference(True)
    except:
        pass

    try:
        popt.SetExcludeEdgeLayer(True)
    except:
        pass

    try:
        popt.SetScale(1)
        popt.SetUseAuxOrigin(False)
        popt.SetMirror(False)
        popt.SetNegative(False)
    except:
        pass

    # Gerber specific settings
    try:
        popt.SetFormat(1)  # Gerber format
    except:
        pass

    try:
        popt.SetUseGerberProtelExtensions(False)
        popt.SetCreateGerberJobFile(True)
        popt.SetSubtractMaskFromSilk(True)
        popt.SetGerberPrecision(6)
    except:
        pass

    # Layers to export
    layers = [
        ("F.Cu", "Front Copper"),
        ("B.Cu", "Back Copper"),
        ("F.Mask", "Front Solder Mask"),
        ("B.Mask", "Back Solder Mask"),
        ("F.SilkS", "Front Silkscreen"),
        ("B.SilkS", "Back Silkscreen"),
        ("F.Paste", "Front Paste"),
        ("B.Paste", "Back Paste"),
        ("Edge.Cuts", "Board Outline"),
    ]

    gerber_files = []
    for layer_name, description in layers:
        layer_id = board.GetLayerID(layer_name)
        if layer_id < 0:
            print(f"  ⚠ Layer {layer_name} not found, skipping")
            continue

        pctl.SetLayer(layer_id)
        pctl.OpenPlotfile(layer_name, pcbnew.PLOT_FORMAT_GERBER, description)
        pctl.PlotLayer()
        pctl.ClosePlot()

        filename = pctl.GetPlotFileName()
        if os.path.exists(filename):
            gerber_files.append(os.path.basename(filename))
            print(f"  ✓ {os.path.basename(filename)}")

    print(f"✓ Generated {len(gerber_files)} Gerber files")
    print()

    # ========================================================================
    # 2. EXPORT DRILL FILES
    # ========================================================================
    print("Generating drill files...")

    drlwriter = pcbnew.EXCELLON_WRITER(board)
    drlwriter.SetOptions(
        False, False, pcbnew.VECTOR2I(0, 0), False
    )  # Don't merge PTH/NPTH
    drlwriter.SetFormat(False)  # Metric
    drlwriter.CreateDrillandMapFilesSet(str(drill_dir), True, False)

    drill_files = []
    board_name = "v0.2"

    # Check for generated drill files
    for drill_file in drill_dir.glob("*.drl"):
        drill_files.append(drill_file.name)
        print(f"  ✓ {drill_file.name}")

    print(f"✓ Generated {len(drill_files)} drill files")
    print()

    # ========================================================================
    # 3. EXPORT BOM (Bill of Materials)
    # ========================================================================
    print("Generating BOM...")

    bom_file = output_dir / "bom.csv"

    # Collect component data
    bom_data = {}
    for fp in board.GetFootprints():
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
    with open(bom_file, "w") as f:
        f.write("Reference,Value,Footprint,Quantity\n")
        for item in sorted(bom_data.values(), key=lambda x: x["value"]):
            refs = " ".join(sorted(item["references"]))
            f.write(
                f'"{refs}","{item["value"]}","{item["footprint"]}",{item["quantity"]}\n'
            )

    unique_parts = len(bom_data)
    total_components = sum(item["quantity"] for item in bom_data.values())

    print(f"✓ BOM: {unique_parts} unique parts, {total_components} total components")
    print(f"  Saved to: {bom_file.name}")
    print()

    # ========================================================================
    # 4. EXPORT POSITION FILE (Pick and Place)
    # ========================================================================
    print("Generating position file...")

    pos_file = output_dir / "position.csv"

    with open(pos_file, "w") as f:
        f.write("Designator,Val,Package,Mid X,Mid Y,Rotation,Layer\n")

        for fp in board.GetFootprints():
            pos = fp.GetPosition()
            layer = "Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom"

            f.write(
                f'"{fp.GetReference()}","{fp.GetValue()}",'
                f'"{fp.GetFPID().GetLibItemName()}",'
                f"{pos.x/1e6:.4f},{pos.y/1e6:.4f},"
                f"{fp.GetOrientationDegrees():.2f},{layer}\n"
            )

    print(f"✓ Position file: {component_count} components")
    print(f"  Saved to: {pos_file.name}")
    print()

    # ========================================================================
    # 5. CREATE ZIP PACKAGE
    # ========================================================================
    print("Creating fabrication ZIP package...")

    zip_path = Path(output_base) / f"olivia_v0.2_fabrication_{timestamp}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add gerber files
        for file in gerber_dir.glob("*"):
            arcname = f"gerber/{file.name}"
            zipf.write(file, arcname)

        # Add drill files
        for file in drill_dir.glob("*"):
            arcname = f"drill/{file.name}"
            zipf.write(file, arcname)

        # Add BOM and position
        zipf.write(bom_file, "bom.csv")
        zipf.write(pos_file, "position.csv")

    zip_size = zip_path.stat().st_size / 1024  # KB

    print(f"✓ ZIP package created: {zip_path.name}")
    print(f"  Size: {zip_size:.1f} KB")
    print()

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 70)
    print("FABRICATION FILES GENERATED SUCCESSFULLY")
    print("=" * 70)
    print()
    print(f"Board: Olivia Control v0.2")
    print(f"Size: {width_mm:.1f} x {height_mm:.1f} mm")
    print(f"Layers: {layer_count}")
    print(f"Components: {component_count} ({unique_parts} unique)")
    print()
    print("Generated files:")
    print(f"  - {len(gerber_files)} Gerber files (gerber/)")
    print(f"  - {len(drill_files)} Drill files (drill/)")
    print(f"  - BOM: {unique_parts} parts ({bom_file.name})")
    print(f"  - Position file: {component_count} components ({pos_file.name})")
    print()
    print(f"ZIP package: {zip_path}")
    print(f"Output directory: {output_dir}")
    print()
    print("Ready for fabrication! 🎉")
    print()

    # Create a summary file
    summary_file = output_dir / "FABRICATION_SUMMARY.txt"
    with open(summary_file, "w") as f:
        f.write("OLIVIA CONTROL v0.2 - FABRICATION PACKAGE\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("BOARD SPECIFICATIONS:\n")
        f.write(f"  Name: Olivia Control v0.2\n")
        f.write(f"  Size: {width_mm:.1f} x {height_mm:.1f} mm\n")
        f.write(f"  Layers: {layer_count}\n")
        f.write(f"  Components: {component_count} total, {unique_parts} unique\n\n")
        f.write("FILES INCLUDED:\n")
        f.write(f"  Gerber files: {len(gerber_files)}\n")
        for gf in sorted(gerber_files):
            f.write(f"    - {gf}\n")
        f.write(f"\n  Drill files: {len(drill_files)}\n")
        for df in sorted(drill_files):
            f.write(f"    - {df}\n")
        f.write(f"\n  BOM: bom.csv ({unique_parts} unique parts)\n")
        f.write(f"  Position file: position.csv ({component_count} components)\n\n")
        f.write("READY FOR FABRICATION\n")
        f.write("Send the ZIP file to your PCB manufacturer.\n")

    print(f"Summary saved to: {summary_file.name}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
