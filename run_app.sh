#!/bin/bash
# Launcher for AI_DownloadOrganizer
APP_DIR="$(cd "$(dirname "$0")"; pwd)/dist/AI_DownloadOrganizer.app"
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

echo "Starting AI_DownloadOrganizer..."
"$PYTHON" "$SCRIPT"
