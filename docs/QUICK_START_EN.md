# Nas Download 1.3.0: start here for your first use

[中文](QUICK_START_ZH.md) | **English**

**This download assistant runs on your own NAS.** Your phone sends commands; the NAS downloads and saves files. Downloads continue after the phone is off as long as the NAS keeps running. The qB download engine is included, so first installation does not require installing a separate qB.

This is the **1.3.0 beta** for **x86_64 Linux NAS** devices with Docker Compose and SSH. The Android package requires **Android 8.0 or later**. ARM NAS devices are not supported. There is no native iPhone package; use the web interface in a browser that can access your NAS. **The app currently has a Chinese interface.** English explanations below include the actual Chinese labels; this documentation does not imply app localization.

## Before starting, prepare these five things

| What you need | Where to find it / how to check |
|---|---|
| Your own NAS | Powered on, with enough disk space |
| NAS LAN IP | NAS network settings or router device list; `192.168.50.20` is an example only |
| NAS SSH account, password, and port | Enable SSH in NAS settings; default usually `22`, but use your own setting |
| Docker and Docker Compose | Install on NAS first; the SSH account must have Docker permissions |
| Android phone and APK | For first use, phone and NAS on the same home network; open `Nas-Download-Standalone-1.3.0.apk` to install |

**Unsure about NAS architecture or Docker permissions?** Ask the NAS administrator first. The app does not enable SSH, install Docker, or grant itself permissions. Installing only the phone app does not make the NAS start downloading.

## Step 1: open the app and tap 自动安装 (Automatic installation)

If Android asks to allow installation from this source, allow the installation for the file manager or browser you are using. Open **Nas Download** afterward. You will see **连接已有 NAS** (Connect to an existing NAS) and **自动安装** (Automatic installation). For first use on this NAS, choose **自动安装**.

Already installed the service? Choose **连接已有 NAS** without creating another instance. Do not uninstall the old app to upgrade a release package with the same signing certificate.

## Step 2: fill in the form and tap 验证并安装 (Verify and install)

| App field | What a beginner should enter |
|---|---|
| SSH 主机（IP / 主机名） — SSH host (IP / hostname) | Your NAS IP, e.g. `192.168.50.20`; no `http://` and no `:7120` here |
| SSH 端口 — SSH port | The SSH port configured on NAS, usually `22` |
| SSH 用户名 / SSH 密码 — SSH username / password | NAS SSH credentials, **not the software administrator account created later** |
| 安装目录（绝对路径） — Installation directory (absolute path) | A new dedicated directory; use `/volume1/docker/nas-download` only if `/volume1` really exists on this NAS |
| 服务监听地址 — Service bind address | Usually keep `0.0.0.0`; allows LAN access, but is not the address to enter in a browser |
| 服务端口 — Service port | Usually keep `7120`; built-in download also uses next port `7121`. Neither may be occupied by another service |
| 下载模式 — Download mode | Keep **内置下载（推荐）** (Built-in download, recommended) |
| 下载保存目录（可留空） — Download directory (optional) | Leave blank initially: files go under `downloads` in the installation directory. For another drive, enter a real full directory path on it |

Do not use an existing media library, another app's directory, or the entire drive root as the installation directory. Different NAS brands may not use `/volume1`; check the real path in the NAS file manager rather than copying a nonexistent directory.

First connection shows **确认 NAS 的 SSH 指纹** (Confirm the NAS SSH fingerprint). Verify that you are connecting to your NAS by comparing the SSH host public-key fingerprint supplied by the administrator. If it matches, tap **已核对，信任** (Verified; trust). If you cannot verify it, cancel first. See the complete manual's SSH fingerprint guidance and troubleshooting in Chapters 3 and 14.

Installation uploads a full package of about 96 MB and imports the image. Keep the app in the foreground and the network connected; wait for progress updates instead of tapping installation repeatedly. Time depends on Wi-Fi and NAS performance.

**Seeing 创建管理员 (Create administrator) means first-time setup has begun.** If installation fails, keep the full error text and follow troubleshooting; do not continually install multiple instances in new directories.

## Step 3: create the software account and add your first download

1. **服务地址** (Service address) is usually filled automatically. The example `http://192.168.50.20:7120` must be replaced with your actual NAS IP and port.
2. Choose an **administrator username** and a password of at least **10 characters**. The setup code generated during installation is normally filled in automatically.
3. Tap **创建并进入** (Create and enter) to open **下载任务** (Download tasks). An empty list is normal.
4. Tap **＋ 添加** (Add) and select the built-in downloader. Paste a `magnet:` link or tap **选择 .torrent 文件** (Choose a .torrent file). Start with just one resource you are entitled to download that still has seeders.
5. Leave **保存目录** (Save directory) blank and **添加后暂停** (Pause after adding) unchecked. Tap **添加** (Add), inspect the receipt, and refresh the list.
6. Increasing progress means downloading has started. At 100%, find files in the NAS download directory. They are on the NAS, not the phone.

**Regular downloads work without a PT account.** You can add magnets and torrents without configuring sites, check-in, or automated torrent downloading/seeding first.

## Day-to-day use

- Open the app to view tasks, or visit the same service address in a computer browser.
- Tap a task for details, including pause and resume controls.
- When deleting, leave **同时删除下载文件（不可恢复）** (Also delete downloaded files, irreversible) unchecked to remove only the task; checking it requests file deletion by the downloader.
- Turning off the phone does not stop NAS downloads. NAS shutdown, loss of network, or stopping the container affects them.
- If **响应未知** (Response unknown) appears, query **更多 → 操作记录与待确认回执** (More → Operation history and pending receipts) before repeating any add or delete.

## If something goes wrong, check this first

| Situation | First action |
|---|---|
| Cannot connect to SSH | Check NAS IP, SSH enabled, port, username/password; put phone back on the same network first |
| No Docker permission / missing Compose | Ask the NAS administrator to install and authorize; the app does not elevate permissions |
| Port occupied | Identify the conflicting service; a new installation can use an available adjacent pair such as `7130` and `7131` |
| Webpage inaccessible | Enter your NAS IP and service port, not `0.0.0.0`, `localhost`, or SSH port `22` |
| App works but speed is zero | Check paused state and available seeders, then Tracker details |
| Cannot find files | Look on the NAS; default is **installation-directory/downloads**, not the phone gallery or phone Downloads folder |

For full feature explanations, examples, check-in and automated torrent downloading/seeding, upgrades, backups, and troubleshooting, read the [complete user manual](USER_MANUAL_EN.md). See the [acceptance report](ACCEPTANCE_1_3_EN.md) for actual testing scope.
