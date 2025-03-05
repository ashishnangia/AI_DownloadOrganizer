"""
Setup script for AI_DownloadOrganizer.
"""

from setuptools import setup

APP = ['main.py']
DATA_FILES = ['settings.json']
OPTIONS = {
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
    'plist': {
        'CFBundleName': 'AI_DownloadOrganizer',
        'CFBundleDisplayName': 'AI Download Organizer',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': 'com.yourdomain.aidownloadorganizer',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'LSUIElement': True,  # Makes the app appear only in the status bar, not the Dock
    },
    'arch': 'universal2',
    'semi_standalone': False,
    'site_packages': True,
    'resources': ['README.md'],  # Add any additional resources here
}

setup(
    name='AI_DownloadOrganizer',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)