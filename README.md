Computer Time
=============

A macOS app to measure time you spend in front of computer screen.

![screenshot](docs/screenshot.png)

Features:

- shows current computer time in menu bar (pie-clock icon)
- notifies you when it's time to take a break (after 1 hour and again after 2 hours)
- resets when you take a break (at least 3 minutes with screensaver or computer sleep)

Dependencies:

- python3
- rumps
- reportlab (to generate PDF icons)

Prepare data (icons):

    make data

Create App:

    python3 setup.py py2app


Development
-----------

Run in alias mode:

    python3 setup.py py2app -A
    ./dist/computer-time.app/Contents/MacOS/computer-time
