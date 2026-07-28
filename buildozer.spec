[app]

title = Activity Log
package.name = activitylog
package.domain = com.joyfulhestee

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

# Icon / presplash can be added later:
# icon.filename = %(source.dir)s/icon.png

android.permissions = INTERNET

android.api = 34
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
