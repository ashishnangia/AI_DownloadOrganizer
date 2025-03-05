import json
import time
import os
import shutil
import threading
from dotenv import load_dotenv  # To load environment variables from .env file
import openai
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyPDF2 import PdfReader

# Import the Cocoa UI components
import objc
from Cocoa import (
    NSApplication, NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable, NSBackingStoreBuffered, NSButton, NSSwitchButton,
    NSAlert, NSRoundedBezelStyle, NSMakeRect, NSStatusBar, NSMenu, NSMenuItem, 
    NSVariableStatusItemLength, NSImage, NSApp, NSObject, NSTimer
)
from PyObjCTools import AppHelper

# Load environment variables from .env
load_dotenv()

# Instantiate the OpenAI client with your API key
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
if not client.api_key:
    print("OPENAI_API_KEY not set in environment.")

# Define the Downloads folder path
DOWNLOADS_FOLDER = os.path.expanduser("~/Downloads")
SETTINGS_FILE = "settings.json"

# Default settings for feature toggles
DEFAULT_SETTINGS = {
    "rename_files": True,
    "organize_folders": True
}

def load_settings():
    """Load settings from a JSON file; if not found, write default settings."""
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print("Error loading settings:", e)
        return DEFAULT_SETTINGS

def save_settings(settings):
    """Save the provided settings dictionary to the JSON file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print("Error saving settings:", e)

# ---------------- Helper Functions ----------------

def extract_text_from_pdf(file_path, retries=3, delay=1):
    """
    Extracts text from the first page of a PDF file using PyPDF2.
    If the file appears empty, wait a bit and retry.
    """
    text = ""
    for attempt in range(retries):
        try:
            if not os.path.exists(file_path):
                print(f"File {file_path} does not exist.")
                return ""
            if os.path.getsize(file_path) == 0:
                print(f"File size is zero, waiting for file to finish writing: {file_path}")
                time.sleep(delay)
                continue

            reader = PdfReader(file_path)
            if len(reader.pages) > 0:
                # Only extract text from the first page
                page = reader.pages[0]
                text = page.extract_text() or ""
            if text:
                return text
            else:
                print(f"No text extracted from first page on attempt {attempt+1}. Retrying...")
                time.sleep(delay)
        except FileNotFoundError:
            print(f"File {file_path} not found on attempt {attempt+1}. Aborting extraction.")
            return ""
        except Exception as e:
            print(f"Attempt {attempt+1}: Error reading PDF {file_path}: {e}")
            time.sleep(delay)
    return text

def extract_text_from_code(file_path, max_lines=100):
    """
    Reads the first max_lines of a code file (or any text file) to capture its primary content.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = []
            for _ in range(max_lines):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
            return "".join(lines)
    except Exception as e:
        print(f"Error reading code file {file_path}: {e}")
        return ""

def extract_keywords(text):
    """
    Uses OpenAI's client interface to analyze the provided text and return exactly two 
    distinct, single-word keywords that capture the primary subject and core offering.
    Prioritize organization names, product names, or service names over generic terms.
    Return only the two keywords separated by commas, with no additional explanation.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Extract exactly two distinct, single-word keywords that capture the primary subject and core offering "
                "of the provided text. Prioritize organization names, product names, or service names over generic terms. "
                "Return only two single words separated by commas, with no additional explanation."
            )
        },
        {"role": "user", "content": text}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=60,
            temperature=0.5,
        )
        keywords_text = response.choices[0].message.content.strip()
        # Sanitize the keywords: lower-case and trim extra spaces
        keywords = [k.strip().lower() for k in keywords_text.split(",") if k.strip()]
        return keywords[:2]
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return []

def rename_and_sort_file(file_path, category, keywords):
    """
    Renames the file based on the extracted keywords and moves it into a folder under the Downloads folder.
    Files are moved directly into folders like ~/Downloads/PDFs, ~/Downloads/Images, etc.
    The behavior depends on the feature toggles loaded from settings.json:
      - If 'rename_files' is false, the original file name is preserved.
      - If 'organize_folders' is false, the file remains in the Downloads folder.
    """
    current_settings = load_settings()  # Always load the latest settings
    base, ext = os.path.splitext(os.path.basename(file_path))
    
    # Check if renaming is enabled
    if current_settings.get("rename_files", True):
        if keywords:
            new_base_name = "_".join(keywords)
        else:
            new_base_name = base
    else:
        new_base_name = base

    # Check if folder organization is enabled
    if current_settings.get("organize_folders", True):
        target_folder = os.path.join(DOWNLOADS_FOLDER, category)
        os.makedirs(target_folder, exist_ok=True)
        new_file_path = os.path.join(target_folder, f"{new_base_name}{ext}")
    else:
        new_file_path = os.path.join(DOWNLOADS_FOLDER, f"{new_base_name}{ext}")
    
    try:
        shutil.move(file_path, new_file_path)
        print(f"Moved file to {new_file_path}")
    except Exception as e:
        print(f"Error moving file: {e}")

# ---------------- File Processors ----------------

def process_pdf(file_path):
    print(f"Processing PDF file: {file_path}")
    text = extract_text_from_pdf(file_path)
    if text:
        keywords = extract_keywords(text)
        print(f"Extracted keywords for PDF: {keywords}")
        rename_and_sort_file(file_path, "PDFs", keywords)
    else:
        print("No text extracted from PDF.")

def process_image(file_path):
    print(f"Processing image file: {file_path}")
    rename_and_sort_file(file_path, "Images", [])

def process_zip(file_path):
    print(f"Processing ZIP file: {file_path}")
    rename_and_sort_file(file_path, "ZIPs", [])

def process_code(file_path):
    print(f"Processing code file: {file_path}")
    text = extract_text_from_code(file_path)
    if text:
        keywords = extract_keywords(text)
        print(f"Extracted keywords for code file: {keywords}")
        rename_and_sort_file(file_path, "Code", keywords)
    else:
        print("No text extracted from code file.")

def process_spreadsheet(file_path):
    print(f"Processing spreadsheet file: {file_path}")
    rename_and_sort_file(file_path, "Spreadsheets", [])

def process_dmg(file_path):
    print(f"Processing DMG file: {file_path}")
    rename_and_sort_file(file_path, "DMGs", [])

def process_word(file_path):
    print(f"Processing Word file: {file_path}")
    rename_and_sort_file(file_path, "Word_Files", [])

def process_video(file_path):
    print(f"Processing video file: {file_path}")
    rename_and_sort_file(file_path, "Videos", [])

def process_new_file(file_path):
    """
    Determines the file type based on its extension and routes to the appropriate processor.
    """
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist, skipping processing.")
        return
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        process_pdf(file_path)
    elif ext in ['.jpg', '.jpeg', '.png', '.gif']:
        process_image(file_path)
    elif ext == ".zip":
        process_zip(file_path)
    elif ext in ['.py', '.js', '.java', '.c', '.cpp', '.rb', '.go']:
        process_code(file_path)
    elif ext in ['.csv', '.xls', '.xlsx', '.tsv']:
        process_spreadsheet(file_path)
    elif ext == ".dmg":
        process_dmg(file_path)
    elif ext in ['.doc', '.docx', '.odt']:
        process_word(file_path)
    elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv']:
        process_video(file_path)
    else:
        print(f"No processor defined for file type '{ext}'. Skipping file: {file_path}")

# ---------------- File Monitoring ----------------

class DownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            process_new_file(event.src_path)

# ---------------- Preferences Window Controller ----------------

class PreferencesWindowController(objc.lookUpClass("NSWindowController")):
    def init(self):
        self = objc.super(PreferencesWindowController, self).init()
        if self is None:
            return None

        # Create a window with a native macOS style
        rect = NSMakeRect(200, 500, 400, 200)
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable
        self.setWindow_(NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(rect, style, NSBackingStoreBuffered, False))
        self.window().setTitle_("AI Download Organizer Preferences")

        # Load current settings
        current_settings = load_settings()

        # Create "Rename Files" checkbox
        self.renameCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(20, 120, 360, 24))
        self.renameCheckbox.setButtonType_(NSSwitchButton)
        self.renameCheckbox.setTitle_("Rename Files with AI Keywords")
        self.renameCheckbox.setState_(1 if current_settings.get("rename_files", True) else 0)
        self.window().contentView().addSubview_(self.renameCheckbox)

        # Create "Organize in Folders" checkbox
        self.organizeCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(20, 80, 360, 24))
        self.organizeCheckbox.setButtonType_(NSSwitchButton)
        self.organizeCheckbox.setTitle_("Organize Files in Folders")
        self.organizeCheckbox.setState_(1 if current_settings.get("organize_folders", True) else 0)
        self.window().contentView().addSubview_(self.organizeCheckbox)

        # Create a Save button
        self.saveButton = NSButton.alloc().initWithFrame_(NSMakeRect(150, 20, 100, 32))
        self.saveButton.setTitle_("Save")
        self.saveButton.setBezelStyle_(NSRoundedBezelStyle)
        self.saveButton.setTarget_(self)
        self.saveButton.setAction_(objc.selector(self.saveSettings_, signature=b'v@:@'))
        self.window().contentView().addSubview_(self.saveButton)

        return self

    def showWindow_(self, sender):
        self.window().makeKeyAndOrderFront_(sender)

    def saveSettings_(self, sender):
        new_settings = {
            "rename_files": True if self.renameCheckbox.state() == 1 else False,
            "organize_folders": True if self.organizeCheckbox.state() == 1 else False,
        }
        save_settings(new_settings)
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Settings Saved")
        alert.runModal()

# ---------------- App Delegate ----------------

class AppDelegate(NSObject):
    statusItem = objc.ivar()
    preferencesController = objc.ivar()
    observer = objc.ivar()
    
    def applicationDidFinishLaunching_(self, notification):
        # Create a status bar item
        statusBar = NSStatusBar.systemStatusBar()
        self.statusItem = statusBar.statusItemWithLength_(NSVariableStatusItemLength)
        self.statusItem.setTitle_("📂")  # Folder emoji as the app icon
        
        # Create a menu
        menu = NSMenu.alloc().init()
        
        # Add menu items
        openPrefsItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Preferences...", "openPreferences:", "")
        menu.addItem_(openPrefsItem)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        quitItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "terminate:", "")
        menu.addItem_(quitItem)
        
        # Set the menu
        self.statusItem.setMenu_(menu)
        
        # Initialize preferences controller
        self.preferencesController = PreferencesWindowController.alloc().init()
        
        # Start file monitoring in a separate thread
        self.startFileMonitoring()
        
        print("AI Download Organizer started successfully!")
    
    def openPreferences_(self, sender):
        self.preferencesController.showWindow_(sender)
    
    def startFileMonitoring(self):
        # Start file monitoring in a background thread
        monitoring_thread = threading.Thread(target=self.monitorDownloads)
        monitoring_thread.daemon = True
        monitoring_thread.start()
    
    def monitorDownloads(self):
        event_handler = DownloadHandler()
        self.observer = Observer()
        self.observer.schedule(event_handler, path=DOWNLOADS_FOLDER, recursive=False)
        self.observer.start()
        print(f"Monitoring {DOWNLOADS_FOLDER} for new files...")
        
        try:
            while True:
                time.sleep(1)
        except Exception as e:
            print(f"Error in file monitoring: {e}")
            self.observer.stop()
        self.observer.join()

def main():
    # Create and run the application
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()

if __name__ == '__main__':
    main()