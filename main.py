"""
Activity Log - Android (Kivy)
------------------------------
Tracks how many times you log in and how many minutes you were active
each session. Protected by a password (created on first run) with a
recovery keyword in case you forget it. Session history can be viewed
and deleted from the dashboard.

On Android, it also records which app was in the foreground while you
were logged in (package name + app label). This requires you to grant
"Usage Access" to this app in Android Settings the first time you run
it - Android does not allow that permission to be requested with a
normal popup, so the app will show a button that opens the right
settings screen for you.

Note: Android does not expose window titles the way Windows does, so
unlike the desktop version, this can only tell you WHICH APP was
active (e.g. "Chrome", "WPS Office"), not which specific file/document
inside it.
"""

import sqlite3
import hashlib
import secrets
import time
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.utils import platform

DB_FILE = "activity_log.db"
ITERATIONS = 100_000
POLL_INTERVAL = 5  # seconds
IS_ANDROID = platform == "android"


# ---------------------- Android foreground-app detection ----------------------

def has_usage_access():
    if not IS_ANDROID:
        return False
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        AppOpsManager = autoclass('android.app.AppOpsManager')
        Process = autoclass('android.os.Process')

        activity = PythonActivity.mActivity
        appops = activity.getSystemService(Context.APP_OPS_SERVICE)
        mode = appops.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            activity.getPackageName()
        )
        return mode == AppOpsManager.MODE_ALLOWED
    except Exception:
        return False


def open_usage_access_settings():
    if not IS_ANDROID:
        return
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        activity = PythonActivity.mActivity
        activity.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
    except Exception:
        pass


def get_foreground_app():
    """Return (package_name, app_label) for the app currently in the
    foreground, or (None, None) if unavailable/not permitted."""
    if not IS_ANDROID:
        return (None, None)
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        System = autoclass('java.lang.System')
        UsageEvents = autoclass('android.app.usage.UsageEvents')

        activity = PythonActivity.mActivity
        usm = activity.getSystemService(Context.USAGE_STATS_SERVICE)
        end_time = System.currentTimeMillis()
        start_time = end_time - (POLL_INTERVAL * 3 * 1000)

        events = usm.queryEvents(start_time, end_time)
        event = autoclass('android.app.usage.UsageEvents$Event')()
        last_pkg = None
        while events.hasNextEvent():
            events.getNextEvent(event)
            if event.getEventType() == 1:  # MOVE_TO_FOREGROUND
                last_pkg = event.getPackageName()

        if not last_pkg:
            return (None, None)

        pm = activity.getPackageManager()
        try:
            app_info = pm.getApplicationInfo(last_pkg, 0)
            label = str(pm.getApplicationLabel(app_info))
        except Exception:
            label = last_pkg
        return (last_pkg, label)
    except Exception:
        return (None, None)


# ---------------------- Database helpers ----------------------

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            keyword_hash TEXT NOT NULL,
            keyword_salt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login_time TEXT NOT NULL,
            logout_time TEXT,
            duration_minutes REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER NOT NULL,
            app_label TEXT NOT NULL,
            package_name TEXT NOT NULL,
            minutes REAL NOT NULL,
            FOREIGN KEY (log_id) REFERENCES logs(id)
        )
    """)
    conn.commit()
    return conn


def hash_value(value, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', value.encode('utf-8'), salt, ITERATIONS)
    return digest.hex(), salt.hex()


def verify_value(value, stored_hash, stored_salt_hex):
    salt = bytes.fromhex(stored_salt_hex)
    digest = hashlib.pbkdf2_hmac('sha256', value.encode('utf-8'), salt, ITERATIONS)
    return digest.hex() == stored_hash


def settings_exist(conn):
    return conn.execute("SELECT 1 FROM settings WHERE id = 1").fetchone() is not None


def save_settings(conn, password, keyword):
    p_hash, p_salt = hash_value(password)
    k_hash, k_salt = hash_value(keyword)
    conn.execute("DELETE FROM settings")
    conn.execute(
        "INSERT INTO settings (id, password_hash, password_salt, keyword_hash, keyword_salt) "
        "VALUES (1, ?, ?, ?, ?)",
        (p_hash, p_salt, k_hash, k_salt)
    )
    conn.commit()


def get_settings(conn):
    return conn.execute(
        "SELECT password_hash, password_salt, keyword_hash, keyword_salt FROM settings WHERE id = 1"
    ).fetchone()


def update_password(conn, new_password):
    p_hash, p_salt = hash_value(new_password)
    conn.execute("UPDATE settings SET password_hash = ?, password_salt = ? WHERE id = 1", (p_hash, p_salt))
    conn.commit()


def start_session(conn):
    login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("INSERT INTO logs (login_time) VALUES (?)", (login_time,))
    conn.commit()
    return cur.lastrowid


def end_session(conn, log_id, duration_minutes):
    logout_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE logs SET logout_time = ?, duration_minutes = ? WHERE id = ?",
        (logout_time, round(duration_minutes, 2), log_id)
    )
    conn.commit()


def fetch_logs(conn):
    return conn.execute(
        "SELECT id, login_time, logout_time, duration_minutes FROM logs ORDER BY id DESC"
    ).fetchall()


def delete_logs(conn, ids):
    conn.executemany("DELETE FROM logs WHERE id = ?", [(i,) for i in ids])
    conn.executemany("DELETE FROM activity_details WHERE log_id = ?", [(i,) for i in ids])
    conn.commit()


def save_activity_details(conn, log_id, usage_seconds):
    rows = [
        (log_id, label, pkg, round(secs / 60, 2))
        for (pkg, label), secs in usage_seconds.items() if secs > 0
    ]
    if rows:
        conn.executemany(
            "INSERT INTO activity_details (log_id, app_label, package_name, minutes) VALUES (?, ?, ?, ?)",
            rows
        )
        conn.commit()


def fetch_activity_details(conn, log_id):
    return conn.execute(
        "SELECT app_label, package_name, minutes FROM activity_details "
        "WHERE log_id = ? ORDER BY minutes DESC",
        (log_id,)
    ).fetchall()


def totals(conn):
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0) FROM logs WHERE logout_time IS NOT NULL"
    ).fetchone()
    return row[0], round(row[1], 2)


# ---------------------- UI helpers ----------------------

def field(hint, password=False, multiline=False):
    return TextInput(hint_text=hint, password=password, multiline=multiline,
                      size_hint_y=None, height=48, font_size=16)


def styled_button(text, callback, bg=(0.2, 0.4, 0.75, 1)):
    btn = Button(text=text, size_hint_y=None, height=52, background_color=bg)
    btn.bind(on_release=callback)
    return btn


def info_popup(title, message):
    Popup(title=title, content=Label(text=message), size_hint=(0.85, 0.4)).open()


# ---------------------- Screens ----------------------

class CreatePasswordScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=24, spacing=12)
        layout.add_widget(Label(text="Create Your Password", font_size=22, size_hint_y=None, height=50))

        self.pw1 = field("New password", password=True)
        self.pw2 = field("Confirm password", password=True)
        self.kw = field("Recovery keyword (used if you forget your password)")

        layout.add_widget(self.pw1)
        layout.add_widget(self.pw2)
        layout.add_widget(self.kw)
        layout.add_widget(styled_button("Create Password", self.submit, bg=(0.18, 0.49, 0.2, 1)))
        layout.add_widget(BoxLayout())
        self.add_widget(layout)

    def submit(self, *_):
        app = App.get_running_app()
        p1, p2, keyword = self.pw1.text.strip(), self.pw2.text.strip(), self.kw.text.strip()
        if not p1 or not p2 or not keyword:
            info_popup("Missing Info", "Please fill in all fields.")
            return
        if p1 != p2:
            info_popup("Mismatch", "Passwords do not match.")
            return
        if len(p1) < 4:
            info_popup("Weak Password", "Password must be at least 4 characters.")
            return
        save_settings(app.conn, p1, keyword)
        self.pw1.text = self.pw2.text = self.kw.text = ""
        info_popup("Success", "Password created. Please log in.")
        self.manager.current = "login"


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=24, spacing=12)
        layout.add_widget(Label(text="Activity Log Login", font_size=22, size_hint_y=None, height=50))
        self.pw = field("Password", password=True)
        layout.add_widget(self.pw)
        layout.add_widget(styled_button("Log In", self.do_login))
        layout.add_widget(styled_button("Forgot Password?", self.go_forgot, bg=(0.4, 0.4, 0.4, 1)))
        layout.add_widget(BoxLayout())
        self.add_widget(layout)

    def do_login(self, *_):
        app = App.get_running_app()
        settings = get_settings(app.conn)
        if settings is None:
            self.manager.current = "create"
            return
        p_hash, p_salt, _, _ = settings
        if verify_value(self.pw.text.strip(), p_hash, p_salt):
            self.pw.text = ""
            app.begin_session()
        else:
            info_popup("Login Failed", "Incorrect password.")
            self.pw.text = ""

    def go_forgot(self, *_):
        self.manager.current = "forgot"


class ForgotPasswordScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=24, spacing=12)
        layout.add_widget(Label(text="Forgot Password", font_size=22, size_hint_y=None, height=50))
        layout.add_widget(Label(text="Enter your recovery keyword", size_hint_y=None, height=30))
        self.kw = field("Recovery keyword")
        layout.add_widget(self.kw)
        layout.add_widget(styled_button("Verify Keyword", self.verify, bg=(0.85, 0.42, 0, 1)))
        layout.add_widget(styled_button("Back to Login", self.back, bg=(0.4, 0.4, 0.4, 1)))
        layout.add_widget(BoxLayout())
        self.add_widget(layout)

    def verify(self, *_):
        app = App.get_running_app()
        settings = get_settings(app.conn)
        _, _, k_hash, k_salt = settings
        if verify_value(self.kw.text.strip(), k_hash, k_salt):
            self.kw.text = ""
            self.manager.current = "reset"
        else:
            info_popup("Incorrect", "Recovery keyword does not match.")

    def back(self, *_):
        self.kw.text = ""
        self.manager.current = "login"


class ResetPasswordScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=24, spacing=12)
        layout.add_widget(Label(text="Set New Password", font_size=22, size_hint_y=None, height=50))
        self.pw1 = field("New password", password=True)
        self.pw2 = field("Confirm password", password=True)
        layout.add_widget(self.pw1)
        layout.add_widget(self.pw2)
        layout.add_widget(styled_button("Update Password", self.submit, bg=(0.18, 0.49, 0.2, 1)))
        layout.add_widget(BoxLayout())
        self.add_widget(layout)

    def submit(self, *_):
        app = App.get_running_app()
        p1, p2 = self.pw1.text.strip(), self.pw2.text.strip()
        if not p1 or p1 != p2:
            info_popup("Error", "Passwords must match and not be empty.")
            return
        if len(p1) < 4:
            info_popup("Weak Password", "Password must be at least 4 characters.")
            return
        update_password(app.conn, p1)
        self.pw1.text = self.pw2.text = ""
        info_popup("Success", "Password updated. Please log in.")
        self.manager.current = "login"


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.row_checks = {}  # log_id -> checkbox
        self.layout = BoxLayout(orientation="vertical", padding=12, spacing=8)
        self.add_widget(self.layout)

    def on_pre_enter(self, *_):
        self.build()

    def build(self):
        app = App.get_running_app()
        self.layout.clear_widgets()
        self.row_checks = {}

        count, minutes = totals(app.conn)
        self.layout.add_widget(Label(text=f"Total Logins: {count}   |   Active Minutes: {minutes}",
                                      size_hint_y=None, height=30, font_size=13))

        self.timer_label = Label(text="Session time: 00:00:00", font_size=18,
                                  size_hint_y=None, height=36)
        self.layout.add_widget(self.timer_label)

        self.current_app_label = Label(text="Currently active app: —", font_size=12,
                                        size_hint_y=None, height=28)
        self.layout.add_widget(self.current_app_label)

        if IS_ANDROID and not has_usage_access():
            self.layout.add_widget(styled_button(
                "Grant Usage Access (for app tracking)",
                lambda *_: open_usage_access_settings(), bg=(0.85, 0.42, 0, 1)
            ))

        self.layout.add_widget(styled_button("Log Out", lambda *_: app.logout(), bg=(0.78, 0.16, 0.16, 1)))

        self.layout.add_widget(Label(text="Activity History (tap a row to select)",
                                      size_hint_y=None, height=30, font_size=14))

        scroll = ScrollView(size_hint=(1, 1))
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=4)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        self.layout.add_widget(scroll)

        self.refresh_logs()

        btn_row = BoxLayout(size_hint_y=None, height=52, spacing=8)
        btn_row.add_widget(styled_button("View Details", self.view_details, bg=(0.2, 0.4, 0.75, 1)))
        btn_row.add_widget(styled_button("Delete Selected", self.delete_selected, bg=(0.4, 0.4, 0.4, 1)))
        self.layout.add_widget(btn_row)

    def refresh_logs(self):
        app = App.get_running_app()
        self.grid.clear_widgets()
        self.row_checks = {}
        for log_id, login_time, logout_time, duration in fetch_logs(app.conn):
            logout_display = logout_time if logout_time else "Active"
            duration_display = duration if duration is not None else "-"
            row = BoxLayout(size_hint_y=None, height=44, spacing=6)
            chk = CheckBox(size_hint_x=None, width=36)
            self.row_checks[log_id] = chk
            row.add_widget(chk)
            row.add_widget(Label(
                text=f"#{log_id}  {login_time} -> {logout_display}  ({duration_display} min)",
                font_size=11, halign="left", valign="middle", text_size=(None, 44)
            ))
            self.grid.add_widget(row)

    def selected_ids(self):
        return [log_id for log_id, chk in self.row_checks.items() if chk.active]

    def delete_selected(self, *_):
        app = App.get_running_app()
        ids = self.selected_ids()
        if not ids:
            info_popup("No Selection", "Check one or more sessions to delete.")
            return
        if app.current_log_id in ids:
            ids.remove(app.current_log_id)
            info_popup("Note", "Your current active session cannot be deleted.")
        if not ids:
            return
        delete_logs(app.conn, ids)
        self.refresh_logs()

    def view_details(self, *_):
        app = App.get_running_app()
        ids = self.selected_ids()
        if len(ids) != 1:
            info_popup("Select One", "Check exactly one session to view its app breakdown.")
            return
        log_id = ids[0]

        if log_id == app.current_log_id:
            rows = sorted(
                [(label, pkg, round(secs / 60, 2)) for (pkg, label), secs in app.usage_seconds.items()],
                key=lambda r: r[2], reverse=True
            )
            note = "(session still active - updates live)"
        else:
            rows = fetch_activity_details(app.conn, log_id)
            note = None

        content = BoxLayout(orientation="vertical", padding=10, spacing=6)
        if note:
            content.add_widget(Label(text=note, size_hint_y=None, height=24, font_size=11))
        if not rows:
            msg = "No app activity recorded yet." if IS_ANDROID and has_usage_access() else \
                  "No app activity recorded.\nMake sure Usage Access is granted."
            content.add_widget(Label(text=msg))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, size_hint_y=None, spacing=4)
            grid.bind(minimum_height=grid.setter("height"))
            for label, pkg, minutes in rows:
                grid.add_widget(Label(text=f"{label} ({pkg}) - {minutes} min",
                                       size_hint_y=None, height=32, font_size=12))
            scroll.add_widget(grid)
            content.add_widget(scroll)

        popup = Popup(title=f"Details - Session #{log_id}", content=content, size_hint=(0.9, 0.7))
        popup.open()


# ---------------------- App ----------------------

class ActivityLogApp(App):
    def build(self):
        self.conn = get_conn()
        self.current_log_id = None
        self.login_start = None
        self.usage_seconds = {}  # (package, label) -> seconds
        self.timer_event = None
        self.poll_event = None

        self.sm = ScreenManager()
        self.sm.add_widget(CreatePasswordScreen(name="create"))
        self.sm.add_widget(LoginScreen(name="login"))
        self.sm.add_widget(ForgotPasswordScreen(name="forgot"))
        self.sm.add_widget(ResetPasswordScreen(name="reset"))
        self.sm.add_widget(DashboardScreen(name="dashboard"))

        self.sm.current = "login" if settings_exist(self.conn) else "create"
        return self.sm

    def begin_session(self):
        self.current_log_id = start_session(self.conn)
        self.login_start = time.time()
        self.usage_seconds = {}
        self.sm.current = "dashboard"
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)
        self.poll_event = Clock.schedule_interval(self.poll_app, POLL_INTERVAL)
        self.poll_app(0)

    def update_timer(self, dt):
        dash = self.sm.get_screen("dashboard")
        if not self.login_start:
            return
        elapsed = int(time.time() - self.login_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        dash.timer_label.text = f"Session time: {h:02d}:{m:02d}:{s:02d}"

    def poll_app(self, dt):
        pkg, label = get_foreground_app()
        if pkg is None:
            return
        key = (pkg, label)
        self.usage_seconds[key] = self.usage_seconds.get(key, 0) + POLL_INTERVAL
        dash = self.sm.get_screen("dashboard")
        dash.current_app_label.text = f"Currently active app: {label}"

    def logout(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        if self.poll_event:
            self.poll_event.cancel()
            self.poll_event = None
        if self.current_log_id and self.login_start:
            duration_minutes = (time.time() - self.login_start) / 60
            end_session(self.conn, self.current_log_id, duration_minutes)
            save_activity_details(self.conn, self.current_log_id, self.usage_seconds)
        self.current_log_id = None
        self.login_start = None
        self.usage_seconds = {}
        self.sm.current = "login"

    def on_stop(self):
        if self.current_log_id and self.login_start:
            duration_minutes = (time.time() - self.login_start) / 60
            end_session(self.conn, self.current_log_id, duration_minutes)
            save_activity_details(self.conn, self.current_log_id, self.usage_seconds)


if __name__ == "__main__":
    ActivityLogApp().run()
