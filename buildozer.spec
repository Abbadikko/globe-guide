[app]
title = Globe Guide
package.name = globeguide
package.domain = com.abba.globeguide
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,json
version = 1.0
requirements = python3,kivy==2.3.0,requests,certifi,urllib3,charset-normalizer,idna
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.ndk_api = 21
android.allow_backup = True
android.arch = arm64-v8a
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
