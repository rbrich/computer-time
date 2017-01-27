from setuptools import setup

OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
    },
    'packages': ['rumps'],
}

setup(
    app=['computer-time.py'],
    data_files=['data'],
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
