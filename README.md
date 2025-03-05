# AI Download Organizer

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

