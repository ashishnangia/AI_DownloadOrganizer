import os
import json
from Cocoa import (
    NSApplication, NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable, NSBackingStoreBuffered, NSButton, NSSwitchButton,
    NSAlert, NSRoundedBezelStyle, NSMakeRect
)
from PyObjCTools import AppHelper
import objc

# Define the path for our settings file
SETTINGS_FILE = "settings.json"

# Default settings for feature toggles
DEFAULT_SETTINGS = {
    "rename_files": True,
    "organize_folders": True
}

def load_settings():
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
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print("Error saving settings:", e)

class PreferencesWindowController(objc.lookUpClass("NSWindowController")):
    def init(self):
        self = objc.super(PreferencesWindowController, self).init()
        if self is None:
            return None

        # Create a window with a native macOS style
        rect = NSMakeRect(200, 500, 400, 200)
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable
        self.setWindow_(NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(rect, style, NSBackingStoreBuffered, False))
        self.window().setTitle_("Preferences")

        # Load current settings
        current_settings = load_settings()

        # Create "Only Rename Files" checkbox
        self.renameCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(20, 120, 360, 24))
        self.renameCheckbox.setButtonType_(NSSwitchButton)
        self.renameCheckbox.setTitle_("Only Rename Files")
        self.renameCheckbox.setState_(1 if current_settings.get("rename_files", True) else 0)
        self.window().contentView().addSubview_(self.renameCheckbox)

        # Create "Only Organize in Folders" checkbox
        self.organizeCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(20, 80, 360, 24))
        self.organizeCheckbox.setButtonType_(NSSwitchButton)
        self.organizeCheckbox.setTitle_("Only Organize in Folders")
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

def main():
    app = NSApplication.sharedApplication()
    controller = PreferencesWindowController.alloc().init()
    controller.showWindow_(None)
    AppHelper.runEventLoop()

if __name__ == '__main__':
    main()
