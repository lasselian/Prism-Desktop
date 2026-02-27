import subprocess
import sys
import shutil
from pathlib import Path

def build():
    """Build the Prism Desktop executable."""
    print("Building Prism Desktop...")

    # Define paths
    base_dir = Path(__file__).parent
    dist_dir = base_dir / "dist"
    build_dir = base_dir / "build"
    icon_path = base_dir / "icon.png"
    font_path = base_dir / "materialdesignicons-webfont.ttf"
    
    # Clean previous builds
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
        
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "PrismDesktop",
        "--add-data", f"{font_path};.",  # Windows separator is ;
        "--exclude", "PySide6",  # Avoid Qt binding conflict
    ]
    
    # Add icon if exists
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
        
    # Add cached mapping if exists
    mapping_path = base_dir / "mdi_mapping.json"
    if mapping_path.exists():
        cmd.extend(["--add-data", f"{mapping_path};."])
        
    # Main script
    cmd.append("main.py")
    
    print(f"Running: {' '.join(str(x) for x in cmd)}")
    
    subprocess.check_call(cmd, cwd=base_dir)
    
    print("\nBuild complete!")
    print(f"Executable is at: {dist_dir / 'PrismDesktop.exe'}")
    print("Note: Configuration is stored in %APPDATA%/PrismDesktop/config.json")

if __name__ == "__main__":
    build()
