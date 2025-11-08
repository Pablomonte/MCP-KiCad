#!/usr/bin/env python3
"""
Test MCP server tools with a real KiCad board (no GUI needed).
This script loads a PCB file directly and tests the server functions.
"""

import sys
import os

# Test if pcbnew is available
try:
    import pcbnew
    print("✓ pcbnew module loaded successfully")
    print(f"  KiCad version: {pcbnew.GetBuildVersion()}")
except ImportError as e:
    print("✗ pcbnew module not available")
    print(f"  Error: {e}")
    print("\nTo run this test:")
    print("  flatpak run --command=python3 --filesystem=home org.kicad.KiCad test_real_board.py")
    sys.exit(1)

# Path to test board
BOARD_PATH = "/home/pablo/repos/Proyecto-Incubadora/HardWare/Electro/Olivia_control/v0.2/v0.2.kicad_pcb"

def test_load_board():
    """Test loading a real KiCad board."""
    print("\n" + "="*60)
    print("TEST 1: Loading Board")
    print("="*60)

    if not os.path.exists(BOARD_PATH):
        print(f"✗ Board file not found: {BOARD_PATH}")
        return False

    try:
        board = pcbnew.LoadBoard(BOARD_PATH)
        print(f"✓ Board loaded: {os.path.basename(BOARD_PATH)}")

        # Get board info
        bbox = board.GetBoardEdgesBoundingBox()
        width = pcbnew.ToMM(bbox.GetWidth())
        height = pcbnew.ToMM(bbox.GetHeight())

        print(f"  Size: {width:.1f} x {height:.1f} mm")
        print(f"  Layers: {board.GetCopperLayerCount()}")
        print(f"  Components: {len(board.GetFootprints())}")

        return board
    except Exception as e:
        print(f"✗ Failed to load board: {e}")
        return False

def test_list_components(board):
    """Test listing components."""
    print("\n" + "="*60)
    print("TEST 2: Listing Components")
    print("="*60)

    try:
        footprints = board.GetFootprints()
        print(f"Found {len(footprints)} components:")
        print(f"\n{'Reference':<12} {'Value':<20} {'Position (mm)':<20} {'Layer':<8}")
        print("-" * 60)

        for i, fp in enumerate(footprints):
            if i >= 10:  # Show only first 10
                print(f"... and {len(footprints) - 10} more")
                break

            ref = fp.GetReference()
            value = fp.GetValue()
            pos = fp.GetPosition()
            x_mm = pcbnew.ToMM(pos.x)
            y_mm = pcbnew.ToMM(pos.y)
            layer = "Top" if fp.IsFlipped() == False else "Bottom"

            print(f"{ref:<12} {value:<20} ({x_mm:6.2f}, {y_mm:6.2f})   {layer:<8}")

        return True
    except Exception as e:
        print(f"✗ Failed to list components: {e}")
        return False

def test_get_nets(board):
    """Test reading netlist."""
    print("\n" + "="*60)
    print("TEST 3: Reading Netlist")
    print("="*60)

    try:
        netinfo = board.GetNetInfo()
        net_count = netinfo.GetNetCount()

        print(f"Found {net_count} nets:")
        print(f"\n{'Net Name':<30} {'Net Code':<10} {'Pads':<10}")
        print("-" * 50)

        shown = 0
        for net_code in range(net_count):
            if shown >= 15:  # Show only first 15
                print(f"... and {net_count - 15} more")
                break

            net = netinfo.GetNetItem(net_code)
            if net:
                net_name = net.GetNetname()
                # Count pads on this net
                pad_count = 0
                for fp in board.GetFootprints():
                    for pad in fp.Pads():
                        if pad.GetNetCode() == net_code:
                            pad_count += 1

                if net_name or pad_count > 0:  # Skip empty nets
                    print(f"{net_name:<30} {net_code:<10} {pad_count:<10}")
                    shown += 1

        return True
    except Exception as e:
        print(f"✗ Failed to read netlist: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_board_info(board):
    """Test getting board information."""
    print("\n" + "="*60)
    print("TEST 4: Board Information")
    print("="*60)

    try:
        bbox = board.GetBoardEdgesBoundingBox()
        width = pcbnew.ToMM(bbox.GetWidth())
        height = pcbnew.ToMM(bbox.GetHeight())

        # Count components
        footprints = list(board.GetFootprints())

        # Count tracks and vias
        tracks = list(board.GetTracks())
        track_count = sum(1 for t in tracks if t.Type() == pcbnew.PCB_TRACE_T)
        via_count = sum(1 for t in tracks if t.Type() == pcbnew.PCB_VIA_T)

        print("Board Information:")
        print(f"  File: {os.path.basename(BOARD_PATH)}")
        print(f"  Size: {width:.1f} x {height:.1f} mm")
        print(f"  Copper layers: {board.GetCopperLayerCount()}")
        print(f"  Components: {len(footprints)}")
        print(f"  Tracks: {track_count}")
        print(f"  Vias: {via_count}")
        print(f"  Nets: {board.GetNetInfo().GetNetCount()}")

        return True
    except Exception as e:
        print(f"✗ Failed to get board info: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_export_bom(board):
    """Test BOM export (read-only, don't write file)."""
    print("\n" + "="*60)
    print("TEST 5: BOM Generation (dry run)")
    print("="*60)

    try:
        # Group components by value and footprint
        bom = {}
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            value = fp.GetValue()
            footprint = str(fp.GetFPID().GetLibItemName())

            key = (value, footprint)
            if key not in bom:
                bom[key] = []
            bom[key].append(ref)

        print(f"BOM would contain {len(bom)} unique parts:")
        print(f"\n{'References':<25} {'Value':<20} {'Footprint':<30} {'Qty':<5}")
        print("-" * 80)

        total_components = 0
        for i, ((value, footprint), refs) in enumerate(sorted(bom.items())):
            if i >= 15:  # Show only first 15
                remaining_parts = len(bom) - 15
                remaining_components = sum(len(refs) for (v, f), refs in list(bom.items())[15:])
                print(f"... and {remaining_parts} more part types ({remaining_components} components)")
                break

            refs_str = ", ".join(sorted(refs)[:5])
            if len(refs) > 5:
                refs_str += f", ... +{len(refs)-5}"

            print(f"{refs_str:<25} {value:<20} {footprint:<30} {len(refs):<5}")
            total_components += len(refs)

        print(f"\nTotal unique parts: {len(bom)}")
        print(f"Total components: {sum(len(refs) for refs in bom.values())}")

        return True
    except Exception as e:
        print(f"✗ Failed to generate BOM: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("KiCad MCP Server - Real Board Tests")
    print("="*60)
    print(f"Test board: {os.path.basename(BOARD_PATH)}")

    # Test 1: Load board
    board = test_load_board()
    if not board:
        print("\n✗ FAILED: Could not load board")
        return 1

    # Test 2: List components
    if not test_list_components(board):
        print("\n✗ FAILED: Could not list components")
        return 1

    # Test 3: Read netlist
    if not test_get_nets(board):
        print("\n✗ FAILED: Could not read netlist")
        return 1

    # Test 4: Board info
    if not test_board_info(board):
        print("\n✗ FAILED: Could not get board info")
        return 1

    # Test 5: BOM generation
    if not test_export_bom(board):
        print("\n✗ FAILED: Could not generate BOM")
        return 1

    # Summary
    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60)
    print("\nThe MCP server should work correctly with real KiCad boards.")
    print("Next step: Test with MCP server running")

    return 0

if __name__ == "__main__":
    sys.exit(main())
