# Activity Log (Android)

A password-protected login/activity tracker built with Kivy. Tracks how many
times you log in, how long you stay active, and (on Android, with your
permission) which app was in the foreground while you were logged in.

## What's in this folder

- `main.py` — the app itself
- `buildozer.spec` — tells Buildozer how to package it into an APK
- `.github/workflows/build-apk.yml` — GitHub Actions workflow that builds
  the APK automatically every time you push
- `README.md` — this file

## Step 1: Push this to GitHub

1. Create a new **public or private** repository on GitHub (e.g. `activity-log-app`).
2. From this folder, run:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
   (Replace `<your-username>/<your-repo>` with your actual repo path.)

## Step 2: Let GitHub Actions build the APK

As soon as you push to `main`, GitHub automatically starts the build:

1. Go to your repository on GitHub.
2. Click the **Actions** tab.
3. You'll see a "Build APK" workflow run in progress. Click into it.
4. **First build takes 15–25 minutes** — it's downloading and setting up the
   full Android SDK/NDK toolchain from scratch. Later builds are faster
   because GitHub caches most of it.
5. When it finishes with a green check, scroll down to **Artifacts** and
   download `activity-log-apk` (a .zip containing your `.apk` file).

If the build fails (red X), click into the failed step to read the error —
Buildozer errors are almost always a missing dependency or an Android
license not being auto-accepted, and the log will say which.

## Step 3: Install it on your phone

1. Unzip the downloaded artifact to get the `.apk` file.
2. Transfer it to your phone (e.g. via USB, Google Drive, or email it to yourself).
3. On your phone, tap the `.apk` file to install it. Android will likely warn
   you it's from an "unknown source" — you'll need to allow installs from
   that source (Settings will prompt you directly, or go to
   **Settings > Apps > Special app access > Install unknown apps**).

## Step 4: Enable app tracking (optional)

The app can log which application was in the foreground while you were
logged in, but Android treats this as sensitive and won't let any app
request it with a normal permission popup. Instead:

1. Open the Activity Log app and log in.
2. If app tracking isn't yet enabled, you'll see a **"Grant Usage Access"**
   button on the dashboard — tap it. This opens Android's Settings screen.
3. Find "Activity Log" in the list and turn the toggle **on**.
4. Go back to the app — tracking will now work.

Note: Android only exposes *which app* was active (e.g. "Chrome",
"WPS Office"), not the specific file or document open inside it — that
level of detail isn't available across apps on Android the way it is on
Windows.

## Making changes later

Any time you edit `main.py` (or anything else) and push to `main`, GitHub
Actions rebuilds the APK automatically — just repeat Step 2 to grab the new
version.

## Rebuilding on the same version of Android

The app targets Android API 34 with a minimum of API 21 (Android 5.0+),
covering effectively all phones in use today. If you need to change targeted
versions, edit `android.api` / `android.minapi` in `buildozer.spec`.
