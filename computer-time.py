#!/usr/bin/env python3

import datetime as dt
import logging
from collections import OrderedDict
import configparser

import rumps
from AppKit import NSObject, NSWorkspace
from Foundation import NSDistributedNotificationCenter


CONFIG_FILE = "computer_time.ini"

INTERVAL_MENU = OrderedDict([
            ("40 minutes", 40 * 60),
            ("1 hour", 1 * 3600),
            ("2 hours", 2 * 3600),
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
        self.notif_interval = 1 * 3600
        self.alert_interval = 2 * 3600  # 2 hours
        self.break_interval = 3 * 60  # 3 minutes = minimal length of break to auto-reset timer
        self.alert_state = 0  # 1 - notification reached, 2 - alert reached
        # Load config file
        self.config = configparser.ConfigParser()
        self.load_config()
        self.mark_interval()
        self._register_notification()

    @rumps.timer(60)
    def refresh(self, _=None):
        # Draw pie clock
        t_now = dt.datetime.now()
        delta = (t_now - self.t_start).total_seconds()
        delta_str = "%d:%02d" % (delta // 3600, (delta // 60) % 60)
        angle = int(360 / 15 * (delta / self.alert_interval)) * 15
        angle = max(angle, 0)
        angle = min(angle, 360)
        # Refresh icon and menu item
        self.icon = "data/icon%03d.pdf" % angle
        self.menu['Time'].title = "Time: %s" % delta_str
        # Silent mode or idle - no notifications
        if self.menu['Silent mode'].state or self.t_idle:
            return
        # Notification
        if self.alert_state < 1 and delta >= self.notif_interval:
            rumps.notification("Computer time", None, "%s elapsed" % delta_str)
            self.alert_state = 1
        # Alert
        if self.alert_state < 2 and delta >= self.alert_interval:
            # Actually also notification, alert window fails to jump to front
            rumps.notification("Take a break!", None, "Your computer time is %s" % delta_str)
            self.alert_state = 2

    @rumps.clicked("Reset")
    def reset(self, sender=None):
        if sender is not None:
            logging.info("reset (from menu)")
        self.t_start = dt.datetime.now()
        self.t_idle = None
        self.refresh()

    @rumps.clicked("Silent mode")
    def silent_mode(self, sender):
        # TODO: remember state (App Support config)
        sender.state = not sender.state

    def set_interval(self, secs):
        self.alert_interval = secs
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
            if delta >= self.break_interval:
                logging.info("reset (idle for %ds)" % delta)
                self.reset()
            self.t_idle = None

    def save_config(self):
        self.config.set('Setup', 'interval', str(self.alert_interval))
        with self.open(CONFIG_FILE, "w") as f:
            self.config.write(f)

    def load_config(self):
        try:
            with self.open(CONFIG_FILE, "r") as f:
                self.config.read_file(f)
            self.alert_interval = self.config.getint('Setup', 'interval', fallback=self.alert_interval)
        except FileNotFoundError:
            # Prepare default config
            self.config.add_section("Setup")

    def mark_interval(self):
        """Mark interval in menu according to current setting"""
        for name, interval in INTERVAL_MENU.items():
            if interval == self.alert_interval:
                self.menu["Set interval"][name].state = True
                break
        else:
            custom = self.menu["Set interval"]["Custom..."]
            custom.state = True
            custom.title = "Custom: %s seconds" % self.alert_interval

    def _build_interval_submenu(self):
        menu = rumps.MenuItem("Set interval")
        for title, value in INTERVAL_MENU.items():
            def cb(sender):
                secs = sender.value
                if not secs:
                    dlg = rumps.Window("Enter interval length in seconds (hint: 3600 = 1 hour):",
                                       "Custom alert interval",
                                       "5400", dimensions=(320, 120), cancel=True)
                    while True:
                        res = dlg.run()
                        if res.clicked == 0:
                            return
                        try:
                            secs = int(res.text)
                            break
                        except ValueError:
                            rumps.alert("Error", "Invalid input!")
                            dlg.default_text = res.text
                            continue
                    sender.title = "Custom: %s seconds" % secs
                else:
                    menu["Custom..."].title = "Custom..."
                # Closure magic...
                for item in menu.values():
                    item.state = False
                sender.state = True
                self.set_interval(secs)
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


if __name__ == "__main__":
    logging.basicConfig(filename='computer-time.log', level=logging.DEBUG,
                        format="%(asctime)s  %(levelname)s %(message)s")
    #rumps.debug_mode(True)
    ComputerTimeApp("Computer Time", icon="data/icon000.pdf", template=True).run()
