#!/usr/bin/env python3

import os.path
import datetime as dt
import logging
from collections import OrderedDict
import configparser

import rumps
from AppKit import NSObject, NSWorkspace
from Foundation import NSDistributedNotificationCenter


CONFIG_FILE = "computer-time.ini"
LOG_FILE = "computer-time.log"

INTERVAL_MENU = OrderedDict([
            ("Pomodoro", 25),
            ("40 minutes", 40),
            ("1 hour", 60),
            ("2 hours", 120),
            ("Custom...", None),
        ])


class ComputerTimeApp(rumps.App):

    def __init__(self, *args, **kwargs):
        menu_spec = [
            "Time",
            "Reset",
            None,
            "Silent mode",
            self._build_interval_submenu(),
            None,
            "Quit",
        ]
        super(ComputerTimeApp, self).__init__(*args, menu=menu_spec, quit_button=None, **kwargs)
        logging.info("start (program init)")
        self.t_start = dt.datetime.now()
        self.t_idle = None
        self.interval = 120  # maximum time before break
        self.min_break = 3   # minimal length of break to auto-reset timer
        self.notified = False  # notification was fired (there should be only one per interval)
        # Load config file
        self.config = configparser.ConfigParser()
        self.load_config()
        self.mark_interval()
        self._register_notification()

    @rumps.timer(60)
    def refresh(self, _=None):
        # Draw pie clock
        t_now = dt.datetime.now()
        interval = self.interval * 60  # interval converted to seconds
        delta = (t_now - self.t_start).total_seconds()
        delta_str = "%d:%02d" % (delta // 3600, (delta // 60) % 60)
        angle = int(360 / 15 * (delta / interval)) * 15
        angle = max(angle, 0)
        angle = min(angle, 360)
        # Refresh icon and menu item
        self.icon = "data/icon%03d.pdf" % angle
        self.menu['Time'].title = "Time: %s" % delta_str
        # Silent mode or idle - no notifications
        if self.menu['Silent mode'].state or self.t_idle:
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
        self.save_config()

    def set_interval(self, minutes):
        self.interval = minutes
        self.save_config()
        self.refresh()

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

    def save_config(self):
        self.config.set('Setup', 'interval', str(self.interval))
        self.config.set('Setup', 'silent_mode', str(self.menu['Silent mode'].state))
        with self.open(CONFIG_FILE, "w") as f:
            self.config.write(f)

    def load_config(self):
        try:
            with self.open(CONFIG_FILE, "r") as f:
                self.config.read_file(f)
            self.interval = self.config.getint('Setup', 'interval', fallback=self.interval)
            self.menu['Silent mode'].state = self.config.getboolean('Setup', 'silent_mode', fallback=False)
        except FileNotFoundError:
            # Prepare default config
            self.config.add_section("Setup")

    def mark_interval(self):
        """Mark interval in menu according to current setting"""
        for name, interval in INTERVAL_MENU.items():
            if interval == self.interval:
                self.menu["Set interval"][name].state = True
                break
        else:
            custom = self.menu["Set interval"]["Custom..."]
            custom.state = True
            custom.title = "Custom: %s minutes" % self.interval

    def _build_interval_submenu(self):
        menu = rumps.MenuItem("Set interval")
        for title, value in INTERVAL_MENU.items():
            def cb(sender):
                minutes = sender.value
                if not minutes:
                    dlg = rumps.Window("Enter interval length in minutes:",
                                       "Custom interval",
                                       str(self.interval), dimensions=(320, 120), cancel=True)
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
