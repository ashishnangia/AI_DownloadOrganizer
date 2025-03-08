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
    NSAlert, NSRoundedBezelStyle, NSMakeRect, NSApp, NSObject, NSTimer, 
    NSTextField, NSScrollView, NSTableView, NSFocusRingTypeNone, NSTextFieldCell,
    NSButtonCell, NSFont, NSStatusBar, NSMenuItem, NSMenu, NSMutableAttributedString,
    NSFontAttributeName, NSMutableDictionary, NSAttributedString, 
    NSTableViewColumnAutoresizingStyle, NSTextAlignmentCenter
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

# File type mappings
FILE_TYPES = {
    "PDF": [".pdf"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code": [".py", ".js", ".java", ".c", ".cpp", ".rb", ".go", ".html", ".css", ".php", ".swift"],
    "Spreadsheets": [".csv", ".xls", ".xlsx", ".tsv", ".ods"],
    "Disk Images": [".dmg", ".iso"],
    "Documents": [".doc", ".docx", ".odt", ".rtf", ".txt", ".md"],
    "Videos": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Presentations": [".ppt", ".pptx", ".key", ".odp"],
    "Executables": [".exe", ".app", ".sh", ".bat", ".msi"]
}

# Default settings for feature toggles
DEFAULT_SETTINGS = {
    "rename_files": True,
    "organize_folders": True,
    "file_types": {name: True for name in FILE_TYPES.keys()}  # Enable all file types by default
}

# Dictionary to track files being downloaded
downloading_files = {}
# Lock for thread-safe access to downloading_files
downloading_files_lock = threading.Lock()

# Minimum file age in seconds to consider a file "stable" (not actively being downloaded)
MIN_FILE_AGE = 3  # Seconds to wait to ensure download is complete

# Extension to category mapping
def get_category_for_extension(ext):
    for category, extensions in FILE_TYPES.items():
        if ext.lower() in extensions:
            return category
    return "Other"  # Default category for unknown file types

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

def is_file_complete(file_path):
    """
    Determine if a file is stable and complete (not actively downloading).
    Returns True if the file hasn't changed size in MIN_FILE_AGE seconds.
    """
    if not os.path.exists(file_path):
        return False
    
    # Check if file is stable for MIN_FILE_AGE seconds
    try:
        initial_size = os.path.getsize(file_path)
        time.sleep(MIN_FILE_AGE)
        current_size = os.path.getsize(file_path) if os.path.exists(file_path) else -1
        
        # If file size has changed, it's still being downloaded
        if initial_size != current_size:
            print(f"File {file_path} is still being written to. Initial size: {initial_size}, current size: {current_size}")
            return False
        
        return True
    except Exception as e:
        print(f"Error checking file stability: {e}")
        return False

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
    
    # Ensure we don't overwrite an existing file
    counter = 1
    while os.path.exists(new_file_path):
        if current_settings.get("organize_folders", True):
            new_file_path = os.path.join(target_folder, f"{new_base_name}_{counter}{ext}")
        else:
            new_file_path = os.path.join(DOWNLOADS_FOLDER, f"{new_base_name}_{counter}{ext}")
        counter += 1
    
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
        rename_and_sort_file(file_path, "PDF", keywords)
    else:
        print("No text extracted from PDF.")

def process_image(file_path):
    print(f"Processing image file: {file_path}")
    rename_and_sort_file(file_path, "Images", [])

def process_archive(file_path):
    print(f"Processing archive file: {file_path}")
    rename_and_sort_file(file_path, "Archives", [])

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

def process_disk_image(file_path):
    print(f"Processing disk image file: {file_path}")
    rename_and_sort_file(file_path, "Disk Images", [])

def process_document(file_path):
    print(f"Processing document file: {file_path}")
    rename_and_sort_file(file_path, "Documents", [])

def process_video(file_path):
    print(f"Processing video file: {file_path}")
    rename_and_sort_file(file_path, "Videos", [])

def process_audio(file_path):
    print(f"Processing audio file: {file_path}")
    rename_and_sort_file(file_path, "Audio", [])

def process_presentation(file_path):
    print(f"Processing presentation file: {file_path}")
    rename_and_sort_file(file_path, "Presentations", [])

def process_executable(file_path):
    print(f"Processing executable file: {file_path}")
    rename_and_sort_file(file_path, "Executables", [])

def process_other(file_path):
    print(f"Processing other file type: {file_path}")
    rename_and_sort_file(file_path, "Other", [])

def process_new_file(file_path):
    """
    Determines the file type based on its extension and routes to the appropriate processor.
    Only processes file types that are enabled in the settings and ensures file is completely downloaded.
    """
    # First check if the file exists
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist, skipping processing.")
        return
    
    # Wait to ensure the file is completely downloaded
    if not is_file_complete(file_path):
        print(f"File {file_path} is not stable yet, skipping for now.")
        # Queue the file for later processing
        with downloading_files_lock:
            downloading_files[file_path] = time.time()
        return
    
    # If we get here, the file is complete and ready for processing
    print(f"File {file_path} is stable and ready for processing.")
    
    # Remove from downloading files list if it was there
    with downloading_files_lock:
        if file_path in downloading_files:
            del downloading_files[file_path]
    
    ext = os.path.splitext(file_path)[1].lower()
    
    # Get the category for this file extension
    category = get_category_for_extension(ext)
    
    # Check if this file type is enabled in settings
    settings = load_settings()
    file_type_settings = settings.get("file_types", {})
    
    if category != "Other" and not file_type_settings.get(category, True):
        print(f"File type '{category}' is disabled in settings. Skipping file: {file_path}")
        return
    
    # Process the file based on its category
    if category == "PDF":
        process_pdf(file_path)
    elif category == "Images":
        process_image(file_path)
    elif category == "Archives":
        process_archive(file_path)
    elif category == "Code":
        process_code(file_path)
    elif category == "Spreadsheets":
        process_spreadsheet(file_path)
    elif category == "Disk Images":
        process_disk_image(file_path)
    elif category == "Documents":
        process_document(file_path)
    elif category == "Videos":
        process_video(file_path)
    elif category == "Audio":
        process_audio(file_path)
    elif category == "Presentations":
        process_presentation(file_path)
    elif category == "Executables":
        process_executable(file_path)
    else:
        process_other(file_path)

def check_pending_downloads():
    """Check for any files that were previously skipped and might now be ready for processing"""
    with downloading_files_lock:
        current_time = time.time()
        files_to_process = []
        files_to_remove = []
        
        for file_path, timestamp in downloading_files.items():
            # Check if the file has been waiting for a while (60 seconds)
            if current_time - timestamp > 60:
                # Check if the file still exists
                if os.path.exists(file_path):
                    if is_file_complete(file_path):
                        files_to_process.append(file_path)
                    else:
                        # Update the timestamp to give it more time
                        downloading_files[file_path] = current_time
                else:
                    # File no longer exists, remove from tracking
                    files_to_remove.append(file_path)
        
        # Remove tracked files that no longer exist
        for file_path in files_to_remove:
            del downloading_files[file_path]
    
    # Process files that are now ready
    for file_path in files_to_process:
        process_new_file(file_path)

# ---------------- File Monitoring ----------------

class DownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            process_new_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            file_path = event.src_path
            # Check if this is a file we're tracking
            with downloading_files_lock:
                if file_path in downloading_files:
                    print(f"Update detected on tracked file: {file_path}")
                    # Will be processed later by the periodic check

# ---------------- Preferences Window Controller ----------------

class PreferencesWindowController(objc.lookUpClass("NSWindowController")):
    def init(self):
        self = objc.super(PreferencesWindowController, self).init()
        if self is None:
            return None

        # Create a window with a native macOS style
        rect = NSMakeRect(200, 300, 550, 550)  # Increased height for API key field
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(rect, style, NSBackingStoreBuffered, False)
        window.setTitle_("AI Download Organizer Preferences")
        window.setReleasedWhenClosed_(False)  # Prevent window from being deallocated
        self.setWindow_(window)

        # Load current settings
        self.current_settings = load_settings()
        
        # Create a vertical offset for positioning elements
        y_offset = 490  # Increased to make room for API key section
        
        # Create section title for API Key
        apiKeyTitle = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y_offset, 480, 24))
        apiKeyTitle.setStringValue_("OpenAI API Key")
        apiKeyTitle.setEditable_(False)
        apiKeyTitle.setBezeled_(False)
        apiKeyTitle.setDrawsBackground_(False)
        apiKeyTitle.setFont_(NSFont.boldSystemFontOfSize_(16))
        self.window().contentView().addSubview_(apiKeyTitle)
        
        y_offset -= 30
        
        # API Key description
        apiKeyDesc = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y_offset, 480, 36))
        apiKeyDesc.setStringValue_("A default key is provided, but you can use your own OpenAI API key for unlimited usage.")
        apiKeyDesc.setEditable_(False)
        apiKeyDesc.setBezeled_(False)
        apiKeyDesc.setDrawsBackground_(False)
        self.window().contentView().addSubview_(apiKeyDesc)
        
        y_offset -= 60
        
        # API Key input field
        self.apiKeyField = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y_offset, 510, 60))
        self.apiKeyField.setStringValue_(self.current_settings.get("api_key", ""))
        # Enable copy/paste functionality
        self.apiKeyField.setEditable_(True)
        self.apiKeyField.setSelectable_(True)
        self.apiKeyField.setAllowsEditingTextAttributes_(True)
        self.apiKeyField.setFocusRingType_(NSFocusRingTypeNone)
        self.window().contentView().addSubview_(self.apiKeyField)
        
        y_offset -= 50  # Add more space after API key field
        
        # Create section title for General Settings
        generalTitle = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y_offset, 480, 24))
        generalTitle.setStringValue_("General Settings")
        generalTitle.setEditable_(False)
        generalTitle.setBezeled_(False)
        generalTitle.setDrawsBackground_(False)
        generalTitle.setFont_(NSFont.boldSystemFontOfSize_(16))
        self.window().contentView().addSubview_(generalTitle)
        
        y_offset -= 40
        
        # Create "Rename Files" checkbox
        self.renameCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(20, y_offset, 480, 24))
        self.renameCheckbox.setButtonType_(NSSwitchButton)
        self.renameCheckbox.setTitle_("Rename Files with AI Keywords")
        self.renameCheckbox.setState_(1 if self.current_settings.get("rename_files", True) else 0)
        self.window().contentView().addSubview_(self.renameCheckbox)
        
        y_offset -= 30
        
        # Create "Organize in Folders" checkbox
        self.organizeCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(20, y_offset, 480, 24))
        self.organizeCheckbox.setButtonType_(NSSwitchButton)
        self.organizeCheckbox.setTitle_("Organize Files in Folders")
        self.organizeCheckbox.setState_(1 if self.current_settings.get("organize_folders", True) else 0)
        self.window().contentView().addSubview_(self.organizeCheckbox)
        
        y_offset -= 50
        
        # Create section title for File Types
        fileTypesTitle = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y_offset, 480, 24))
        fileTypesTitle.setStringValue_("File Types to Process")
        fileTypesTitle.setEditable_(False)
        fileTypesTitle.setBezeled_(False)
        fileTypesTitle.setDrawsBackground_(False)
        fileTypesTitle.setFont_(NSFont.boldSystemFontOfSize_(16))
        self.window().contentView().addSubview_(fileTypesTitle)
        
        y_offset -= 30
        
        # Create file type checkboxes
        self.fileTypeCheckboxes = {}
        file_types_per_row = 2
        checkbox_width = 240
        checkbox_height = 24
        checkbox_margin = 10
        
        file_type_settings = self.current_settings.get("file_types", {})
        sorted_file_types = sorted(FILE_TYPES.keys())
        
        for i, file_type in enumerate(sorted_file_types):
            row = i // file_types_per_row
            col = i % file_types_per_row
            
            x_pos = 20 + col * checkbox_width
            y_pos = y_offset - (row * (checkbox_height + checkbox_margin))
            
            checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(x_pos, y_pos, checkbox_width, checkbox_height))
            checkbox.setButtonType_(NSSwitchButton)
            checkbox.setTitle_(file_type)
            checkbox.setState_(1 if file_type_settings.get(file_type, True) else 0)
            
            self.window().contentView().addSubview_(checkbox)
            self.fileTypeCheckboxes[file_type] = checkbox
        
        # Calculate position for save button based on number of file type rows
        num_rows = (len(sorted_file_types) + file_types_per_row - 1) // file_types_per_row
        save_button_y = y_offset - (num_rows * (checkbox_height + checkbox_margin)) - 40
        
        # Create a Save button
        self.saveButton = NSButton.alloc().initWithFrame_(NSMakeRect(225, save_button_y, 100, 32))
        self.saveButton.setTitle_("Save")
        self.saveButton.setBezelStyle_(NSRoundedBezelStyle)
        self.saveButton.setTarget_(self)
        self.saveButton.setAction_(objc.selector(self.saveSettings_, signature=b'v@:@'))
        self.window().contentView().addSubview_(self.saveButton)

        return self

    def showWindow_(self, sender):
        # Reload settings when window is shown
        self.current_settings = load_settings()
        self.updateUI()
        self.window().makeKeyAndOrderFront_(sender)
    
    def updateUI(self):
        # Update general settings checkboxes
        self.renameCheckbox.setState_(1 if self.current_settings.get("rename_files", True) else 0)
        self.organizeCheckbox.setState_(1 if self.current_settings.get("organize_folders", True) else 0)
        
        # Update file type checkboxes
        file_type_settings = self.current_settings.get("file_types", {})
        for file_type, checkbox in self.fileTypeCheckboxes.items():
            checkbox.setState_(1 if file_type_settings.get(file_type, True) else 0)

    def saveSettings_(self, sender):
        api_key = self.apiKeyField.stringValue()

        # Get values from general settings checkboxes
        new_settings = {
             "api_key": api_key,
            "rename_files": True if self.renameCheckbox.state() == 1 else False,
            "organize_folders": True if self.organizeCheckbox.state() == 1 else False,
            "file_types": {}
        }
        
        # Get values from file type checkboxes
        for file_type, checkbox in self.fileTypeCheckboxes.items():
            new_settings["file_types"][file_type] = True if checkbox.state() == 1 else False
        
        # Save the new settings
        save_settings(new_settings)
        self.current_settings = new_settings
        
        # Update OpenAI client with new API key
        global client
        client = openai.OpenAI(api_key=api_key)

        # Show confirmation alert
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Settings Saved")
        alert.runModal()

# ---------------- Main Window Controller ----------------

class MainWindowController(objc.lookUpClass("NSWindowController")):
    def init(self):
        self = objc.super(MainWindowController, self).init()
        if self is None:
            return None

        # Create a window with a native macOS style
        rect = NSMakeRect(200, 300, 400, 200)
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable
        self.setWindow_(NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(rect, style, NSBackingStoreBuffered, False))
        self.window().setTitle_("AI Download Organizer")

        # Add status label
        statusLabel = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 140, 360, 24))
        statusLabel.setStringValue_("AI Download Organizer is running...")
        statusLabel.setEditable_(False)
        statusLabel.setBezeled_(False)
        statusLabel.setDrawsBackground_(False)
        statusLabel.setFont_(NSFont.boldSystemFontOfSize_(14))
        statusLabel.setAlignment_(NSTextAlignmentCenter)
        self.window().contentView().addSubview_(statusLabel)
        
        # Add description
        descLabel = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 100, 360, 40))
        descLabel.setStringValue_("Files in your Downloads folder will be automatically organized according to your preferences.")
        descLabel.setEditable_(False)
        descLabel.setBezeled_(False)
        descLabel.setDrawsBackground_(False)
        descLabel.setAlignment_(NSTextAlignmentCenter)
        self.window().contentView().addSubview_(descLabel)
        
        # Preferences button
        self.prefsButton = NSButton.alloc().initWithFrame_(NSMakeRect(125, 50, 150, 32))
        self.prefsButton.setTitle_("Preferences...")
        self.prefsButton.setBezelStyle_(NSRoundedBezelStyle)
        self.prefsButton.setTarget_(self)
        self.prefsButton.setAction_(objc.selector(self.openPreferences_, signature=b'v@:@'))
        self.window().contentView().addSubview_(self.prefsButton)

        return self
    
    def openPreferences_(self, sender):
        NSApp.delegate().openPreferences_(sender)

# ---------------- App Delegate ----------------

class AppDelegate(NSObject):
    mainWindowController = objc.ivar()
    preferencesController = objc.ivar()
    observer = objc.ivar()
    statusItem = objc.ivar()  # Add this line to store the status item
    
    def applicationDidFinishLaunching_(self, notification):
         # Load settings and get API key
        settings = load_settings()
        api_key = settings.get("api_key", "")
    
    # Update OpenAI client with the API key
        global client
        if api_key:
         client = openai.OpenAI(api_key=api_key)
        
        # Create the status bar item
        statusBar = NSStatusBar.systemStatusBar()
        self.statusItem = statusBar.statusItemWithLength_(22)  # Fixed width
        self.statusItem.setTitle_("AI")  # Simple text that should be visible
        
        # Create a menu for the status bar
        menu = NSMenu.alloc().init()
        
        # Add menu items
        openPrefsItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Preferences...", "openPreferences:", "")
        openPrefsItem.setTarget_(self)  # Explicitly set the target
        menu.addItem_(openPrefsItem)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        quitItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "terminate:", "q")
        menu.addItem_(quitItem)
        
        # Set the menu
        self.statusItem.setMenu_(menu)
        
        # Initialize the main window controller
        self.mainWindowController = MainWindowController.alloc().init()
        # Don't show the window automatically for a status bar app
        # self.mainWindowController.showWindow_(None)
        
        # Initialize preferences controller
        self.preferencesController = PreferencesWindowController.alloc().init()
        
        # Start file monitoring in a separate thread
        self.startFileMonitoring()
        
        # Start timer to check pending downloads
        self.startPendingDownloadsCheck()
        
        print("AI Download Organizer started successfully!")
    
    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return False
    
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
    
    def startPendingDownloadsCheck(self):
        # Create a timer to check for pending downloads every 30 seconds
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            30.0, self, "checkPendingDownloads:", None, True)
    
    def checkPendingDownloads_(self, timer):
        # Check for any files that were waiting to finish downloading
        check_pending_downloads()

def main():
    # Create and run the application
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()

if __name__ == '__main__':
    main()