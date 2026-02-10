#!/usr/bin/env python3
"""
AppImage Build Script for PrismDesktop.

This script automates the creation of an AppImage for Linux.
It requires:
1.  Python 3 and PyInstaller (installed via pip)
2.  `appimagetool` installed and in your PATH.
    (Download from https://github.com/AppImage/appimagetool/releases)

Steps performed:
1.  Builds the linux binary using `build_linux.py`.
2.  Creates an AppDir structure.
3.  Copies binary, icon, and creates a .desktop file.
4.  Runs `appimagetool` to generate the AppImage.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def find_tool(name):
    """Find a tool in PATH or current directory."""
    # 1. Check PATH
    path_tool = shutil.which(name)
    if path_tool:
        return path_tool
        
    # 2. Check current directory (especially for appimagetool)
    if name == "appimagetool":
        base_dir = Path(__file__).parent.absolute()
        # Common names for the downloaded binary
        candidates = [
            "appimagetool",
            "appimagetool-x86_64.AppImage",
            "appimagetool.AppImage"
        ]
        
        for cand in candidates:
            local_path = base_dir / cand
            if local_path.exists():
                print(f"Found local tool: {local_path}")
                # Ensure it's executable
                try:
                    current_mode = os.stat(local_path).st_mode
                    os.chmod(local_path, current_mode | 0o111) # Add +x
                except Exception as e:
                    print(f"Warning: Could not make {cand} executable: {e}")
                return str(local_path)
                
    return None

def main():
    # 0. Prerequisites
    print("Checking prerequisites...")
    if sys.platform != "linux":
        print("Error: This script must be run on Linux.")
        sys.exit(1)
        
    if not find_tool("python3"):
        print("Error: python3 not found.")
        sys.exit(1)
        
    appimagetool = find_tool("appimagetool")
    if not appimagetool:
        print("Error: 'appimagetool' not found.")
        print("Please download 'appimagetool-x86_64.AppImage' from: https://github.com/AppImage/appimagetool/releases")
        print("Place it in this directory or add it to your PATH.")
        sys.exit(1)
    
    base_dir = Path(__file__).parent.absolute()
    dist_dir = base_dir / "dist"
    app_dir = base_dir / "AppDir"
    
    # 1. Build Binary
    print("\n[1/4] Building Binary...")
    build_script = base_dir / "build_linux.py"
    try:
        subprocess.run([sys.executable, str(build_script)], check=True)
    except subprocess.CalledProcessError:
        print("Error: Build failed.")
        sys.exit(1)
        
    binary_path = dist_dir / "PrismDesktop"
    if not binary_path.exists():
        print("Error: Binary not found at dist/PrismDesktop")
        sys.exit(1)

    # 2. Prepare AppDir
    print("\n[2/4] Creating AppDir Structure...")
    if app_dir.exists():
        shutil.rmtree(app_dir)
    
    # Create directories
    # Standard: usr/bin for binary, usr/share/icons for icon
    (app_dir / "usr" / "bin").mkdir(parents=True)
    (app_dir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps").mkdir(parents=True)
    
    # 3. Copy Files & Create Configs
    print("\n[3/4] Copying Assets...")
    
    # Copy Binary
    shutil.copy2(binary_path, app_dir / "usr" / "bin" / "PrismDesktop")
    
    # Copy Icon
    icon_src = base_dir / "icon.png"
    icon_dest = app_dir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "prism-desktop.png"
    # Also copy to root for AppImage parsing
    icon_root = app_dir / "prism-desktop.png"
    
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dest)
        shutil.copy2(icon_src, icon_root)
    else:
        print("Warning: icon.png not found. Using placeholder.")
    
    # Create AppRun (symlink)
    # AppRun is the entry point. We can symlink to the binary relative path.
    # relative link: usr/bin/PrismDesktop
    (app_dir / "AppRun").symlink_to("usr/bin/PrismDesktop")
    
    # Create .desktop file
    desktop_content = """[Desktop Entry]
Type=Application
Name=PrismDesktop
Comment=Home Assistant Tray Application
Exec=PrismDesktop
Icon=prism-desktop
Categories=Utility;
Terminal=false
"""
    with open(app_dir / "PrismDesktop.desktop", "w") as f:
        f.write(desktop_content)
        
    # 4. Package
    print("\n[4/4] Packaging AppImage...")
    # appimagetool requires ARCH to be set if not auto-detected, usually fine on x86_64
    env = os.environ.copy()
    if "ARCH" not in env:
        # Default to x86_64 for standard PC, users can override
        pass 
        
    try:
        # Use the found tool path
        subprocess.run([appimagetool, str(app_dir)], cwd=base_dir, check=True)
        print("\n✅ AppImage created successfully!")
    except subprocess.CalledProcessError:
        print("\n❌ AppImage packaging failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
