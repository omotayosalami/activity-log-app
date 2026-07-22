# Testing on Windows Before Pushing to GitHub

Kivy runs fine as a normal desktop app on Windows, so you can sanity-check
the whole UI — login, password creation, keyword recovery, session timer,
history list, delete — without waiting on a 20-minute Android build each
time. The only thing that *won't* work on desktop is app-tracking (it needs
Android's UsageStatsManager), and the app already knows to skip that
gracefully on non-Android platforms — no crash, the tracking UI just won't
appear.

## 1. Install Python

Use Python 3.10 or 3.11 (best current Kivy compatibility on Windows).
Check what you have:

```bash
python --version
```

## 2. Create a virtual environment (recommended)

From inside the `activity_log_android` folder:

```bash
python -m venv venv
venv\Scripts\activate
```

You'll see `(venv)` appear in your Command Prompt once it's active.

## 3. Install Kivy

```bash
python -m pip install --upgrade pip
pip install "kivy[base]"
```

This pulls a precompiled wheel with SDL2 bundled in, so you shouldn't need
any separate `kivy_deps` packages or a C compiler. If you hit an error about
a missing Visual C++ runtime, install the
[Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe)
and try again.

## 4. Run it

```bash
python main.py
```

A window should open with the "Create Your Password" screen (since no
`activity_log.db` exists yet). Walk through:

- Creating a password + recovery keyword
- Logging in
- Watching the session timer count up
- Logging out, then checking the history list shows the session
- Selecting a row's checkbox and using **View Details** / **Delete Selected**
- Using **Forgot Password?** with your recovery keyword to reset the password

Since `IS_ANDROID` is `False` on Windows, the "Grant Usage Access" button and
app-tracking rows simply won't appear — that's expected, not a bug.

## 5. Resetting between tests

Each run reuses `activity_log.db` in the same folder (so your password and
history persist across runs, same as the real app would). To start totally
fresh — e.g. to re-test the first-run "Create Password" screen — just delete
that file:

```bash
del activity_log.db
```

## 6. Once it looks right

Commit and push as normal (see the main `README.md`) and let GitHub Actions
build the real APK. Nothing about local testing changes what gets built —
`main.py` runs identically on both platforms, it just self-detects
`platform == "android"` at runtime to decide whether to touch Android-only
APIs.
