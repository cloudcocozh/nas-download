# Testing and Building from Source

[中文](BUILDING.md) | [English](BUILDING_EN.md)

Regular users should use the [Release installation package](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1). This page is for developers.

## Structure

`server/` is the Python service; `web/` is the web interface; `deploy/` and `install.sh` manage installation, the engine and upgrades; `android/` is the native Java client; `tests/` contains backend and Linux installer tests.

## Backend and Web Tests

Python 3.11 and Node.js are required. Complete installer tests run on Linux; Windows explicitly skips some Linux tests.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r server/requirements.txt
python -m unittest discover -s tests -v
node web/tests/smoke.cjs
node web/tests/sites-smoke.cjs
node web/tests/automations-smoke.cjs
```

Tests use separate temporary data and adapters. They do not connect to real PT credentials or perform deletion experiments on existing downloaders.

## Linux Image

```sh
docker build -t nas-download:1.3.0 .
```

The engine-copy stage in Dockerfile is pinned to a specific upstream image digest and supports x86_64. The Python base image and system packages are not all pinned by digest, so source rebuilds are not guaranteed to match the release image byte for byte. Deploy with the installer into a new test directory without overwriting existing running state.

## Preparing Android Bundled Assets

Run from the repository root:

```sh
python deploy/package.py
```

This generates `android/app/src/main/assets/installer.tar.gz`, plus source and installation packages in the adjacent `outputs` directory. Source-based assets without an image build on the NAS during first installation and require network access.

If you have a gzip image exported by `docker save`, you can build complete offline assets:

```sh
python deploy/package.py --image /path/to/nas-download-image.tar.gz
```

The APK's `assets/installer.bundle` must be byte-for-byte identical to the asset gzip. Never include a real NAS's `.env`, `data`, keys or download data.

## Android Build

Use JDK 17, Android SDK 35, Build Tools 35.0.0 and Gradle 8.10.2; the project uses AGP 8.7.3. This repository has no Gradle Wrapper. Install Gradle or configure the version in Android Studio. Set `JAVA_HOME` and `ANDROID_HOME` for your environment.

```sh
gradle -p android assembleDebug lintDebug
```

The debug package name is `com.nasdownload.app.debug`, allowing it to coexist with the release version. Device tests require building `assembleDebugAndroidTest` and using a separate emulator; do not clear data on personal devices.

Release signing reads the configuration file path from `NAS_DOWNLOAD_SIGNING_FILE`, or uses local `signing.properties` in the Android app project directory:

```properties
storeFile=/absolute/path/to/your-release-keystore.jks
storePassword=REPLACE_WITH_YOUR_SECRET
keyAlias=YOUR_ALIAS
keyPassword=REPLACE_WITH_YOUR_SECRET
```

```sh
gradle -p android assembleRelease lintRelease
```

Do not commit signing configuration or keys to Git. Your own signature cannot directly replace an official installation with the same package name; prefer the debug package for development. Missing signing configuration does not mean a signed, publishable package was generated.

The public source matches the accepted 1.3.0 runtime code; only the development-machine-specific signing path was removed, and public documentation, licenses and test procedures were added. Binaries belong in Releases, not Git history.

## Updating the bilingual offline guides

Maintain the Chinese and English Markdown files together, with language links at the top. Regenerate HTML after editing. Documentation dependencies are separate from NAS runtime dependencies.

```sh
python -m pip install -r deploy/docs-requirements.txt
python deploy/render_guides.py --archive ../outputs/Nas-Download-1.3.0-manuals.zip
```
