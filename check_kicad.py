#!/usr/bin/env python3
"""
Check KiCad Python environment and locate pcbnew module
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 10:
        print("✓ Python version is compatible (3.10+)")
        return True
    else:
        print("✗ Python version too old (need 3.10+)")
        return False


def check_kicad_installed():
    """Check if KiCad is installed"""
    print("\nChecking KiCad installation...")

    try:
        result = subprocess.run(
            ["which", "kicad"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            kicad_path = result.stdout.strip()
            print(f"✓ KiCad found at: {kicad_path}")
            return True
        else:
            print("✗ KiCad not found in PATH")
            return False
    except Exception as e:
        print(f"✗ Error checking KiCad: {e}")
        return False


def check_flatpak_kicad():
    """Check if KiCad is installed via Flatpak"""
    print("\nChecking KiCad Flatpak installation...")

    try:
        result = subprocess.run(
            ["flatpak", "list"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and "org.kicad.KiCad" in result.stdout:
            # Get version
            version_result = subprocess.run(
                [
                    "flatpak",
                    "run",
                    "--command=python3",
                    "org.kicad.KiCad",
                    "-c",
                    "import pcbnew; print(pcbnew.GetBuildVersion())",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if version_result.returncode == 0:
                version = version_result.stdout.strip()
                print(f"✓ KiCad Flatpak found: {version}")
                return True, version
            else:
                print("✓ KiCad Flatpak found (version unknown)")
                return True, "unknown"
        else:
            print("✗ KiCad Flatpak not installed")
            return False, None
    except FileNotFoundError:
        print("✗ Flatpak not available on this system")
        return False, None
    except Exception as e:
        print(f"✗ Error checking Flatpak: {e}")
        return False, None


def check_flatpak_dependencies():
    """Check if MCP dependencies are installed in Flatpak"""
    print("\nChecking Flatpak dependencies...")

    deps = ["mcp", "anthropic", "dotenv"]
    all_ok = True

    for dep in deps:
        try:
            result = subprocess.run(
                [
                    "flatpak",
                    "run",
                    "--command=python3",
                    "org.kicad.KiCad",
                    "-c",
                    f"import {dep}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            mod_name = "python-dotenv" if dep == "dotenv" else dep

            if result.returncode == 0:
                print(f"✓ {mod_name} installed in Flatpak")
            else:
                print(f"✗ {mod_name} not installed in Flatpak")
                all_ok = False
        except Exception as e:
            print(f"✗ Error checking {dep}: {e}")
            all_ok = False

    if not all_ok:
        print("\nInstall missing dependencies in Flatpak:")
        print("  ./kicad_flatpak_setup.sh")

    return all_ok


def check_pcbnew_module():
    """Check if pcbnew module is available"""
    print("\nChecking pcbnew module...")

    try:
        import pcbnew

        print(f"✓ pcbnew module available")
        print(f"  Module path: {pcbnew.__file__}")

        # Try to get version
        try:
            version = pcbnew.GetBuildVersion()
            print(f"  KiCad version: {version}")
        except:
            pass

        return True

    except ImportError as e:
        print("✗ pcbnew module not available")
        print(f"  Error: {e}")
        return False


def find_kicad_python():
    """Try to find KiCad's Python interpreter"""
    print("\nSearching for KiCad Python interpreter...")

    common_paths = [
        "/usr/lib/kicad/bin/python3",
        "/usr/lib/kicad/bin/python",
        "/usr/local/kicad/bin/python3",
        "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3",
        "C:\\Program Files\\KiCad\\7.0\\bin\\python.exe",
        "C:\\Program Files\\KiCad\\8.0\\bin\\python.exe",
    ]

    found = []
    for path in common_paths:
        if Path(path).exists():
            print(f"  Found: {path}")
            found.append(path)

    if not found:
        print("  No KiCad Python found in common locations")
        print("\n  Try searching manually:")
        print("    find /usr -name '*kicad*python*' 2>/dev/null")
        print("    find /usr/lib -name 'pcbnew.py' 2>/dev/null")

    return found


def check_dependencies():
    """Check if required packages are installed"""
    print("\nChecking Python dependencies...")

    deps = ["mcp", "anthropic", "dotenv"]
    all_ok = True

    for dep in deps:
        try:
            if dep == "dotenv":
                __import__("dotenv")
                mod_name = "python-dotenv"
            else:
                __import__(dep)
                mod_name = dep

            print(f"✓ {mod_name} installed")
        except ImportError:
            print(f"✗ {mod_name} not installed")
            all_ok = False

    if not all_ok:
        print("\nInstall missing dependencies:")
        print("  pip install -r requirements.txt")

    return all_ok


def main():
    """Main check routine"""
    print("=" * 60)
    print("KiCad MCP Environment Check")
    print("=" * 60)

    results = {
        "Python version": check_python_version(),
        "KiCad installed": check_kicad_installed(),
        "pcbnew module": check_pcbnew_module(),
        "Dependencies": check_dependencies(),
    }

    # Check for Flatpak installation
    flatpak_found, flatpak_version = check_flatpak_kicad()
    results["KiCad Flatpak"] = flatpak_found

    # Check Flatpak dependencies if Flatpak is installed
    if flatpak_found:
        flatpak_deps_ok = check_flatpak_dependencies()
        results["Flatpak dependencies"] = flatpak_deps_ok
    else:
        flatpak_deps_ok = False

    # Find KiCad Python (for non-Flatpak installations)
    kicad_pythons = find_kicad_python()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for check, status in results.items():
        icon = "✓" if status else "✗"
        print(f"{icon} {check}")

    print("\n" + "=" * 60)

    # Provide appropriate next steps based on what's available
    if flatpak_found and flatpak_deps_ok:
        print("\n✓ Ready to use with KiCad Flatpak!")
        print("\nRecommended workflow (Flatpak):")
        print("  1. Open a PCB in KiCad PCBNew")
        print("  2. Terminal 1: ./run_with_flatpak.sh")
        print("  3. Terminal 2: source venv/bin/activate")
        print("     mcp-kicad-client ./run_with_flatpak.sh")

    elif flatpak_found and not flatpak_deps_ok:
        print("\n⚠ KiCad Flatpak found but dependencies not installed")
        print("\nSetup Flatpak dependencies:")
        print("  ./kicad_flatpak_setup.sh")
        print("\nThen run:")
        print("  ./run_with_flatpak.sh")

    elif results["pcbnew module"]:
        print("\n✓ Ready to use with KiCad (native installation)!")
        print("\nNext steps:")
        print("  1. Open a PCB in KiCad PCBNew")
        print("  2. Run: mcp-kicad")
        print("  3. Run: mcp-kicad-client mcp-kicad")

    else:
        print("\n⚠ pcbnew not available - will run in MOCK MODE")
        print("\nTo enable KiCad integration:")

        if flatpak_found:
            print("\nOption 1: Use Flatpak (RECOMMENDED)")
            print("  ./kicad_flatpak_setup.sh")
            print("  ./run_with_flatpak.sh")

        if kicad_pythons:
            print(f"\nOption 2: Use KiCad's Python:")
            for kp in kicad_pythons:
                print(f"   {kp} -m pip install -e '.[dev]'")
                print(f"   {kp} -m mcp_kicad.server.extended")

        if not flatpak_found:
            print("\nOption 3: Install KiCad via Flatpak:")
            print("  flatpak install flathub org.kicad.KiCad")
            print("  ./kicad_flatpak_setup.sh")

        print("\nOption 4: Link pcbnew to your virtual environment:")
        print("  find /usr/lib -name 'pcbnew.py' 2>/dev/null")
        print("  ln -s /path/to/pcbnew.py venv/lib/python3.*/site-packages/")

        print("\nOption 5: Test in mock mode:")
        print("  pytest")


if __name__ == "__main__":
    main()
