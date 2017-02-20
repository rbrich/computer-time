#!/usr/bin/env python3

import os.path
import datetime as dt
import logging
from collections import OrderedDict
import configparser

import rumps
from AppKit import NSObject, NSWorkspace, NSRunningApplication
from Foundation import NSDistributedNotificationCenter


CONFIG_FILE = "computer-time.ini"
LOG_FILE = "computer-time.log"
LAUNCHD_NAME = "cz.lgv.computer-time.plist"
LAUNCHD_PATH = os.path.expanduser("~/Library/LaunchAgents/" + LAUNCHD_NAME)
LAUNCHD_TEMPLATE = "data/launchd-template.xml"

INTERVAL_MENU = OrderedDict([
            ("Pomodoro", 25),
            ("40 minutes", 40),
            ("1 hour", 60),
            ("2 hours", 120),
            ("Custom...", None),
        ])


def get_executable_path():
    # Try to get the path from Cocoa
    r_app = NSRunningApplication.currentApplication()
    if r_app.bundleIdentifier().endswith(".ComputerTime"):
        path = r_app.executableURL().path()
    else:
        # Fallback to python script path
        path = os.path.abspath(__file__)
        logging.info("script file: %s", __file__)
    return path


class Config:

    def __init__(self, filename):
        self._filename = filename
        self._parser = configparser.ConfigParser()
        # Defaults
        self.interval = 120  # maximum time before break
        self.silent_mode = False

    def load(self):
        c = self._parser
        try:
            with open(self._filename, "r") as f:
                c.read_file(f)
        except FileNotFoundError:
            # Prepare default config
            c.add_section("Setup")
            return
        self.interval = c.getint('Setup', 'interval', fallback=self.interval)
        self.silent_mode = c.getboolean('Setup', 'silent_mode', fallback=self.silent_mode)

    def save(self):
        c = self._parser
        c.set('Setup', 'interval', str(self.interval))
        c.set('Setup', 'silent_mode', str(self.silent_mode))
        with open(self._filename, "w") as f:
            c.write(f)


class ComputerTimeApp(rumps.App):

    def __init__(self, *args, **kwargs):
        menu_spec = [
            "Time",
            "Reset",
            None,
            "Silent mode",
            self._build_interval_submenu(),
            None,
            "Run at login",
            "Quit",
        ]
        super(ComputerTimeApp, self).__init__(*args, menu=menu_spec, quit_button=None, **kwargs)
        # Setup auxiliary variables
        self.t_start = dt.datetime.now()
        self.t_idle = None
        self.min_break = 3   # minimal length of break to auto-reset timer
        self.notified = False  # notification was fired (there should be only one per interval)
        # Load config file
        self.config = Config(os.path.join(self._application_support, CONFIG_FILE))
        self.config.load()
        self.menu["Silent mode"].state = self.config.silent_mode
        self.menu["Run at login"].state = os.path.exists(LAUNCHD_PATH)
        self.mark_interval()
        # Register for screensaver / sleep notifications
        self._register_notification()
        logging.info("start (program init)")

    @rumps.timer(60)
    def refresh(self, _=None):
        # Draw pie clock
        t_now = dt.datetime.now()
        interval = self.config.interval * 60  # interval converted to seconds
        delta = (t_now - self.t_start).total_seconds()
        delta_str = "%d:%02d" % (delta // 3600, (delta // 60) % 60)
        angle = int(360 / 15 * (delta / interval)) * 15
        angle = max(angle, 0)
        angle = min(angle, 360)
        # Refresh icon and menu item
        self.icon = "data/icon%03d.pdf" % angle
        self.menu['Time'].title = "Time: %s" % delta_str
        # Silent mode or idle - no notifications
        if self.config.silent_mode or self.t_idle:
            return
        # Notification
        if not self.notified and delta >= interval:
            rumps.notification("Time to take a break!", None, "Your computer time is %s" % delta_str)
            self.notified = True

    @rumps.clicked("Reset")
    def reset(self, sender=None):
        if sender is not None:
            logging.info("reset (from menu)")
        self.t_start = dt.datetime.now()
        self.t_idle = None
        self.refresh()

    @rumps.clicked("Silent mode")
    def silent_mode(self, sender):
        sender.state = not sender.state
        self.config.silent_mode = sender.state
        self.config.save()

    def set_interval(self, minutes):
        self.config.interval = minutes
        self.config.save()
        self.refresh()

    @rumps.clicked('Run at login')
    def run_at_login(self, sender):
        enabled = not sender.state
        if enabled:
            # Enable by creating launchd .plist file from template
            with open(LAUNCHD_TEMPLATE, 'r') as f:
                template = f.read()
            with open(LAUNCHD_PATH, 'w') as f:
                f.write(template.format(get_executable_path()))
        else:
            # Disable by removing the .plist file from launchd
            os.unlink(LAUNCHD_PATH)
        sender.state = enabled

    @rumps.clicked('Quit')
    def quit(self, _):
        logging.info("stop (program end)")
        rumps.quit_application()

    def set_idle(self, status):
        if status and not self.t_idle:
            self.t_idle = dt.datetime.now()
        if not status and self.t_idle:
            # Check idle time
            delta = (dt.datetime.now() - self.t_idle).total_seconds()
            if delta >= self.min_break * 60:
                logging.info("reset (idle for %ds)" % delta)
                self.reset()
            self.t_idle = None

    def mark_interval(self):
        """Mark interval in menu according to current setting"""
        for name, interval in INTERVAL_MENU.items():
            if interval == self.config.interval:
                self.menu["Set interval"][name].state = True
                break
        else:
            custom = self.menu["Set interval"]["Custom..."]
            custom.state = True
            custom.title = "Custom: %s minutes" % self.config.interval

    def _build_interval_submenu(self):
        menu = rumps.MenuItem("Set interval")
        for title, value in INTERVAL_MENU.items():
            def cb(sender):
                minutes = sender.value
                if not minutes:
                    dlg = rumps.Window("Enter interval length in minutes:",
                                       "Custom interval",
                                       str(self.config.interval),
                                       dimensions=(320, 120), cancel=True)
                    while True:
                        res = dlg.run()
                        if res.clicked == 0:
                            return
                        try:
                            minutes = int(res.text)
                            break
                        except ValueError:
                            rumps.alert("Error", "Invalid input!")
                            dlg.default_text = res.text
                            continue
                    sender.title = "Custom: %s minutes" % minutes
                else:
                    menu["Custom..."].title = "Custom..."
                # Closure magic...
                for item in menu.values():
                    item.state = False
                sender.state = True
                self.set_interval(minutes)
            mi = rumps.MenuItem(title, callback=cb)
            mi.value = value
            menu[title] = mi

        return menu

    def _register_notification(self):
        set_idle = self.set_idle

        class Notify(NSObject):

            def screensaverDidStart_(self, _):
                logging.info("idle (screensaver started)")
                set_idle(True)

            def screensaverDidStop_(self, _):
                logging.info("active (screensaver stopped)")
                set_idle(False)

            def workspaceWillSleep_(self, _):
                logging.info("idle (sleep)")
                set_idle(True)

            def workspaceDidWake_(self, _):
                logging.info("active (wake)")
                set_idle(False)

        self._notify = Notify.new()

        # screensaver notifications
        nc = NSDistributedNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self._notify, 'screensaverDidStart:',
                                             'com.apple.screensaver.didstart', None)
        nc.addObserver_selector_name_object_(self._notify, 'screensaverDidStop:',
                                             'com.apple.screensaver.didstop', None)

        # sleep notifications
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(self._notify, 'workspaceWillSleep:',
                                             'NSWorkspaceWillSleepNotification', None)
        nc.addObserver_selector_name_object_(self._notify, 'workspaceDidWake:',
                                             'NSWorkspaceDidWakeNotification', None)


def main():
    app_name = "Computer Time"
    log_path = os.path.join(rumps.application_support(app_name), LOG_FILE)
    logging.basicConfig(filename=log_path, level=logging.DEBUG,
                        format="%(asctime)s  %(levelname)s %(message)s")
    ComputerTimeApp(app_name, icon="data/icon000.pdf", template=True).run()


if __name__ == "__main__":
    main()
