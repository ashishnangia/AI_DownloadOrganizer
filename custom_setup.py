#!/usr/bin/env python3
"""
Custom build script for AI_DownloadOrganizer that works around py2app codesigning issues.
This script will:
1. Use py2app to do the initial build (which will fail at signing)
2. Create a launcher script that can run the app without needing proper code signing
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
import platform

# Configuration
MAIN_SCRIPT = 'main.py'  # Replace with your actual main script name
APP_NAME = 'AI_DownloadOrganizer'
BUNDLE_ID = 'com.yourdomain.aidownloadorganizer'

def clean_build_dir():
    """Remove existing build artifacts"""
    print("Cleaning build directories...")
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed {dir_name}/")

def create_setup_py():
    """Create a temporary setup.py file"""
    print("Creating setup.py file...")
    setup_content = f'''
from setuptools import setup

APP = ['{MAIN_SCRIPT}']

OPTIONS = {{
    'argv_emulation': False,
    'includes': ['openai', 'watchdog', 'PyPDF2', 'dotenv', 
                'jaraco.text', 'jaraco.functools', 'jaraco.context',
                'more_itertools', 'importlib_metadata', 'zipp'],
    'packages': ['pkg_resources'],
    'excludes': ['typing_extensions', 'packaging'],
    'plist': {{
        'CFBundleName': '{APP_NAME}',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': '{BUNDLE_ID}',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
    }},
    'arch': 'universal2',
    'semi_standalone': False,
    'site_packages': True,
}}

setup(
    app=APP,
    options={{'py2app': OPTIONS}},
    setup_requires=['py2app'],
)
'''
    with open('temp_setup.py', 'w') as f:
        f.write(setup_content)
    return 'temp_setup.py'

def run_py2app(setup_file):
    """Run py2app with the setup file"""
    print("Running py2app (may fail at signing phase, which is expected)...")
    try:
        result = subprocess.run([sys.executable, setup_file, 'py2app'], 
                               capture_output=True, text=True)
        print(result.stdout)
        if 'Cannot sign bundle' in result.stderr:
            print("Expected signing error occurred, continuing with workaround...")
            return True
        elif result.returncode != 0:
            print("Unexpected error:", result.stderr)
            return False
        return True
    except Exception as e:
        print(f"Error running py2app: {e}")
        return False

def create_launcher():
    """Create a launcher script that can run the app"""
    print("Creating launcher script...")
    launcher_content = f'''#!/bin/bash
# Launcher for {APP_NAME}
APP_DIR="$(cd "$(dirname "$0")"; pwd)/dist/{APP_NAME}.app"
PYTHON="$APP_DIR/Contents/Resources/Python.app/Contents/MacOS/Python"
SCRIPT="$APP_DIR/Contents/Resources/__boot__.py"

if [ ! -f "$PYTHON" ]; then
    echo "Error: Python interpreter not found at $PYTHON"
    exit 1
fi

if [ ! -f "$SCRIPT" ]; then
    echo "Error: Boot script not found at $SCRIPT"
    exit 1
fi

echo "Starting {APP_NAME}..."
"$PYTHON" "$SCRIPT"
'''
    with open('run_app.sh', 'w') as f:
        f.write(launcher_content)
    os.chmod('run_app.sh', 0o755)
    print("Created launcher script: run_app.sh")

def main():
    """Main build process"""
    print(f"Building {APP_NAME}...")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    clean_build_dir()
    setup_file = create_setup_py()
    success = run_py2app(setup_file)
    
    if success:
        create_launcher()
        print("\nBuild completed with workarounds. To run the app, use:")
        print("  ./run_app.sh")
    else:
        print("\nBuild failed.")
        sys.exit(1)
    
    # Clean up temp files
    if os.path.exists(setup_file):
        os.remove(setup_file)

if __name__ == "__main__":
    main()