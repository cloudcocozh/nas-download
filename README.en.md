# Nas Download

[简体中文](README.md) | **English**

**Let your NAS handle downloads. Manage them from your phone or browser.** The default installation runs in one container with qBittorrent built in, so you do not need to install, sign in to, or configure qBittorrent separately.

Current public release: **1.3.0 beta**. Requires a Linux x86_64 NAS; the Android app requires **Android 8.0 or later**. ARM is not supported yet.

These English documents describe the existing release. **The app interface is currently in Chinese**; the guides include the actual Chinese button labels alongside English explanations.

## Download and get started

**[Open the download page: v1.3.0-beta.1](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1)**

| What you want to do | What to download |
|---|---|
| Get everything in one download | **Nas-Download-1.3.0-share.zip**. Extract it and open `先看这里.html`. This original bundle includes Chinese guides; download the updated bilingual manuals below for English. |
| Install on your NAS from an Android phone | **Nas-Download-Standalone-1.3.0.apk** |
| Install from a NAS terminal as an administrator | **Nas-Download-Standalone-1.3.0-install.tar.gz** |
| Read the instructions first | [Quick start](docs/QUICK_START_EN.md) / [Full user manual](docs/USER_MANUAL_EN.md) |
| Read offline in Chinese or English | **Nas-Download-1.3.0-manuals.zip**; extract it and open `START_HERE.html` |

The green **Code → Download ZIP** button downloads source code, not the Android installer. For ready-to-use downloads, use the release page above.

## What it does

- Add magnet links, torrent URLs, or `.torrent` files; view actual progress, transfer speeds, files, and trackers.
- Pause, resume, and remove tasks. Deleting downloaded files requires a separate selection.
- Manage the same tasks from Android and the web, pair another phone, and revoke device sessions.
- Optionally connect your own M-Team or Torznab sites to search, view details, and choose downloads.
- Optionally run daily check-ins, account checks, and unattended downloads on the NAS. Automation is disabled by default.
- Connect an existing qBittorrent 4/5 or Transmission 4 instance in advanced mode.

Files are stored on the NAS. Downloads can continue with your phone switched off. The software does not provide private-tracker accounts, invitations, API keys, cookies, or content.

## First installation

1. Prepare **SSH, Docker, and Docker Compose** on the NAS. The SSH account must have permission to use Docker. Connect your phone and NAS to the same home network for the first installation.
2. Install the APK → choose **自动安装 (Automatic installation)** → enter your NAS address, SSH account, and a dedicated installation directory → keep **内置下载（推荐） (Built-in downloader, recommended)** selected.
3. Verify the NAS SSH host fingerprint, wait for installation, create the application administrator account, and select **＋ 添加 (Add)** to start your first download.

**[The quick start explains every field and where to find your files.](docs/QUICK_START_EN.md)**

The default web service port is 7120; the built-in downloader also uses 7121 over TCP/UDP. Both ports must be available. The app does not enable SSH, install Docker, or grant itself additional permissions. Your NAS SSH account and the application's administrator account serve different purposes.

Administrators can download the full installer from the release page, upload it to an empty temporary directory on the NAS, and run these commands in the NAS terminal:

```sh
tar -xzf Nas-Download-Standalone-1.3.0-install.tar.gz
sh install.sh --dir /volume1/docker/nas-download --port 7120 --mode bundled
```

The path is an example: use a dedicated, writable directory on your own NAS. Keep the extraction directory separate from the installation directory. Choose either phone installation or manual installation; you do not need both. See chapter 12 of the user manual.

## Automation and protection

Check-ins and automated torrent downloading/seeding are disabled by default. Start with a read-only dry run. Automation only manages tasks it added and recorded. Tasks are retained if seeding obligations are unknown, permanent protection applies, the observation period is incomplete, or identity/file verification fails. Automatic removal and file deletion must each be explicitly enabled.

An M-Team account check is not a website check-in or an account-retention guarantee. Verified VIP status only controls admission of new non-FREE torrents; it does not waive seeding obligations or guarantee a download remains exempt from traffic accounting throughout its duration. This product does not import other software's automation rules. See the [automation reference](docs/AUTOMATION_EN.md).

## Validation and limitations

Actual downloads, pause/resume, automated removal and replacement, engine recovery, upgrades from the older version, and failure rollback passed on an isolated x86_64 NAS. All 145 Linux acceptance tests passed. Android emulator UI checks, full-package SSH/SFTP transfer, and upgrades signed with the same certificate passed.

A complete first installation from a physical phone to a NAS, multi-day operation, and compatibility across all devices have not been verified. This is a beta release, with no guarantee of maximum transfer speed or public inbound connectivity. See the [acceptance record](docs/ACCEPTANCE_1_3_EN.md).

## Documentation and source

- [Quick start](docs/QUICK_START_EN.md) / [Full user manual](docs/USER_MANUAL_EN.md)
- [Development and building](docs/BUILDING_EN.md)
- [Automation reference](docs/AUTOMATION_EN.md) / [Site integration](docs/SITES_EN.md)
- [Installation and release reference](docs/INSTALL_RELEASE_EN.md) / [Release notes](docs/RELEASE_1_3_EN.md)
- [Privacy](PRIVACY.en.md) / [Third-party components](THIRD_PARTY.en.md)

The manuals archive on the release page contains offline HTML guides in both languages, with chapter search and printing/PDF support.

The project's original management service, web interface, Android client, and documentation use the [MIT License](LICENSE). Third-party components such as qBittorrent, Qt, and Python retain their own licenses; adopting MIT for this project does not relicense them. Third-party licenses and corresponding source materials are available on the same release page.

No private NAS configuration, site credentials, download data, or release signing keys are included. When reporting an [issue](https://github.com/cloudcocozh/nas-download/issues), include the version, steps, and sanitized errors. Do not upload passwords, cookies, API keys, or URLs containing a passkey.
