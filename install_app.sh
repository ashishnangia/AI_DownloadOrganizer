#!/bin/bash
# Installer for AI_DownloadOrganizer
APP_PATH="$(cd "$(dirname "$0")"; pwd)/dist/AI_DownloadOrganizer.app"
APPLICATIONS="/Applications"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: Application not found at $APP_PATH"
    echo "Please run the build script first."
    exit 1
fi

echo "Installing AI_DownloadOrganizer to Applications folder..."
cp -R "$APP_PATH" "$APPLICATIONS/"

echo "Installation complete!"
echo "You can now launch the app from your Applications folder or from Spotlight."
