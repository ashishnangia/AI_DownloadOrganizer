#!/usr/bin/env python3
"""
Custom build script for AI_DownloadOrganizer that works around py2app codesigning issues.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
import platform

# Configuration
APP_NAME = 'AI_DownloadOrganizer'
BUNDLE_ID = 'com.yourdomain.aidownloadorganizer'
MAIN_SCRIPT = 'main.py'
VERSION = '1.0.0'

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
DATA_FILES = ['settings.json']
OPTIONS = {{
    'argv_emulation': False,
    'includes': [
        'openai', 'watchdog', 'PyPDF2', 'dotenv',
        'jaraco.text', 'jaraco.functools', 'jaraco.context',
        'more_itertools', 'importlib_metadata', 'zipp',
        'objc', 'PyObjCTools',
    ],
    'packages': [
        'pkg_resources',
        'watchdog', 
        'openai',
    ],
    'excludes': ['typing_extensions', 'packaging'],
    'plist': {{
        'CFBundleName': '{APP_NAME}',
        'CFBundleDisplayName': 'AI Download Organizer',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '{VERSION}',
        'CFBundleIdentifier': '{BUNDLE_ID}',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'LSUIElement': True,  # Makes the app appear only in the status bar, not the Dock
    }},
    'arch': 'universal2',
    'semi_standalone': False,
    'site_packages': True,
}}

setup(
    name='{APP_NAME}',
    app=APP,
    data_files=DATA_FILES,
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

def create_install_script():
    """Create an install script to move the app to Applications folder"""
    print("Creating install script...")
    install_content = f'''#!/bin/bash
# Installer for {APP_NAME}
APP_PATH="$(cd "$(dirname "$0")"; pwd)/dist/{APP_NAME}.app"
APPLICATIONS="/Applications"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: Application not found at $APP_PATH"
    echo "Please run the build script first."
    exit 1
fi

echo "Installing {APP_NAME} to Applications folder..."
cp -R "$APP_PATH" "$APPLICATIONS/"

echo "Installation complete!"
echo "You can now launch the app from your Applications folder or from Spotlight."
'''
    with open('install_app.sh', 'w') as f:
        f.write(install_content)
    os.chmod('install_app.sh', 0o755)
    print("Created installer script: install_app.sh")

def create_readme():
    """Create a README file with instructions"""
    print("Creating README file...")
    readme_content = f'''# AI Download Organizer

AI Download Organizer automatically organizes your downloaded files using AI-powered categorization.

## Features
- Monitors your Downloads folder for new files
- Uses AI to extract relevant keywords from files
- Organizes files into appropriate folders
- Renames files based on extracted keywords
- Simple macOS status bar interface

## Installation

1. Run the installer script:
   ```
   ./install_app.sh
   ```

2. Alternatively, you can run the app directly:
   ```
   ./run_app.sh
   ```

## Usage

After launching the app, look for the folder icon (📂) in your macOS menu bar.
Click it to access the preferences or quit the application.

## Requirements
- macOS 10.13 or later
- OpenAI API key (set in your environment variables)

## Setup

For the app to function properly, you need to set your OpenAI API key as an environment variable:

1. Create a file named `.env` in the same directory as the application with the following content:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

2. Restart the application.

'''
    with open('README.md', 'w') as f:
        f.write(readme_content)
    print("Created README.md")

def main():
    """Main build process"""
    print(f"Building {APP_NAME}...")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    clean_build_dir()
    setup_file = create_setup_py()
    create_readme()
    success = run_py2app(setup_file)
    
    if success:
        create_launcher()
        create_install_script()
        print("\nBuild completed with workarounds.")
        print("To run the app directly, use:")
        print("  ./run_app.sh")
        print("\nTo install to Applications folder, use:")
        print("  ./install_app.sh")
    else:
        print("\nBuild failed.")
        sys.exit(1)
    
    # Clean up temp files
    if os.path.exists(setup_file):
        os.remove(setup_file)

if __name__ == "__main__":
    main()