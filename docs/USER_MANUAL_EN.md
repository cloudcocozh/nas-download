# Nas Download 1.3.0: complete user manual

[中文](USER_MANUAL_ZH.md) | **English**

**For people using a NAS download tool for the first time.** Follow the first five chapters to go from preparing your devices to completing your first download. Site search, check-in, and automated torrent downloading/seeding are optional; you do not need to configure everything at once.

Version: 1.3.0 beta · Document date: 2026-10-08. Button names were checked against this version of the Android app. NAS system menus vary by brand and version. **The app interface is currently Chinese.** This guide explains controls in English and retains their actual Chinese labels so you can find them; it does not indicate an English app interface.

## 1. What is this for?

Nas Download runs downloads on your own NAS. Use your phone or the web interface to add torrents, check progress, pause, and resume. Files are stored on the NAS hard drive. Your phone is a remote control: its screen does not have to stay on, and your computer does not have to keep running.

**How it works: phone / web interface → your own NAS → NAS hard drive.** The default installation uses one product container with the qBittorrent download engine included. You do not need to configure a separate qB address and password.

| What you want to do | What this version supports |
|---|---|
| Regular downloads | Add magnet links, torrent download URLs, and `.torrent` files |
| Manage downloads | View progress, live speeds, states, file lists, and Trackers; pause, resume, and delete |
| Use multiple devices | Android and the web interface connect to the same NAS service and share tasks; one-time pairing codes and device access revocation are supported |
| Search your own sites | Configure M-Team or Torznab sites, then search, view details, and manually add downloads |
| Daily tasks | Configure the HDFans check-in template, custom HTTP check-in, or an M-Team account API check |
| Unattended downloads | Automatically select resources according to configuration; remove low-performing tasks and add new ones when all protection and verification requirements are met |
| Connect an existing downloader | Advanced mode supports existing qBittorrent 4/5 and Transmission 4 instances |

This is not a resource-site account, a cloud-storage subscription, or a video player. It does not provide private-tracker (PT) invitations, API Keys, or Cookies. A regular video webpage URL is not a torrent download URL. It does not automatically add files to NAS media-center collections or take over your earlier NAS-tools tasks. Built-in download mode uses its own engine and configuration.

### Version scope

- NAS: Linux, x86_64/amd64, with Docker and Docker Compose installed. This version's offline image does not support ARM NAS devices.
- Phone: Android 8.0 or later is the minimum installation requirement, not a claim that every model has been tested. There is no native iPhone app in this release; use a browser to access the service.
- Verified: actual downloads, removal and replacement, failure recovery, migration from the old version, and rollback on an isolated NAS, plus Android emulator tests.
- Not covered: the complete first-installation flow from a real phone to a NAS, continuous operation over multiple days, and every brand or model. Initial sharing is as a beta release. See the [acceptance report](ACCEPTANCE_1_3_EN.md) for detailed limits.

## 2. What to prepare before you start

### 2.1 Prepare the NAS first

1. **Turn it on and connect it to your home network.** Keep your phone and NAS on the same network for your first attempt so remote-network issues do not complicate installation.
2. **Check the processor architecture.** Look in the NAS system information. If you cannot find it, ask an administrator to run `uname -m`. This version requires `x86_64` or `amd64`; architectures such as `aarch64` and `armv7l` are not supported.
3. **Install Docker / container management and Compose.** Brands use different names for these features; a menu path for one brand should not be assumed to apply to every device.
4. **Enable SSH.** This is the connection the phone temporarily uses to sign in to the NAS and install the software. Record the account, port, and password.
5. **Check that this account can operate Docker.** Being able to sign in to the NAS website does not necessarily mean SSH works or the account has container permissions. Ask an administrator to check instead of repeatedly trying different passwords in the app.
6. **Choose storage for installation and downloads.** The installation directory stores configuration and task state; the download directory stores actual files. Leave room for the image, configuration, logs, upgrade backups, and downloaded files.

An administrator can check readiness with these read-only commands. They do not enable tasks or change configuration:

```sh
uname -m
docker compose version
docker info
```

If any of these three checks reports “command not found,” “permission denied,” or cannot connect to Docker, fix the NAS environment first. The app does not automatically install Docker, enable SSH, or elevate permissions.

### 2.2 Keep these four types of information separate

| Information | Purpose | Where it comes from |
|---|---|---|
| NAS SSH account and password | Install the software on the NAS | NAS administration settings; used for this connection only, and the app does not save the SSH password |
| Nas Download administrator account and password | Use the app or web interface day to day | You create these after the first installation |
| Setup code | Create the first administrator only | Generated by the installer; the app normally fills it in automatically |
| Phone pairing code | Add another device to an existing service | Generated by a signed-in device; valid for 5 minutes and usable once |

**Do not mix them up.** If sign-in fails, first check whether you are signing in to the NAS itself or to Nas Download.

### 2.3 Which package files should you use?

| File | Who uses it |
|---|---|
| `Nas-Download-Standalone-1.3.0.apk` | Android users: install on the phone; includes the offline image needed for NAS installation |
| `Nas-Download-Standalone-1.3.0-install.tar.gz` | Administrators installing manually on the NAS; do not install again after successful automatic installation from the phone |
| `Nas-Download-1.3.0-source.zip` | Developers inspecting or modifying source; ordinary users do not need it |
| `SHA256SUMS.txt` | Check that the original packages received are intact; not an installation file |

If you received a sharing bundle with manuals, extract it first and open **START_HERE.html** or **“先看这里.html”** (Start here) in its root directory. Do not install directly from an archive preview or use that preview to follow links between files. The older combined sharing bundle still includes Chinese guides; the latest standalone `Nas-Download-1.3.0-manuals.zip` provides bilingual guides. The original source release ZIP remains unchanged; the latest English documentation is also available on the repository’s main branch.

## 3. Install on the NAS from an Android phone

### 3.1 Install the phone app

Save the APK on your phone and open it with the file manager. Android may ask you to allow that file manager to install apps; follow your phone's instructions. Then open **Nas Download**.

The welcome page has two options:

- **自动安装** (Automatic installation): use this when the NAS does not yet have this product's service.
- **连接已有 NAS** (Connect to an existing NAS): use this when the service is already installed or you are signing in from a new phone.

The package name is `com.nasdownload.app`, which differs from the earlier three-in-one app. Installing this APK does not replace the three-in-one app with this product.

### 3.2 Fill in the automatic-installation form

The examples below use the fictional NAS `192.168.50.20`. Replace it with your own information; the example is not an existing server you can connect to.

| Actual field label | What to enter | Common mistake |
|---|---|---|
| SSH 主机（IP / 主机名） — SSH host (IP / hostname) | `192.168.50.20` | Entering `http://192.168.50.20:7120`; that is a service URL, not an SSH host |
| SSH 端口 — SSH port | Usually `22`; use the NAS's actual setting | Entering web-service port `7120` |
| SSH 用户名 — SSH username | A NAS account with SSH and Docker permissions | Entering the software administrator account, which has not yet been created |
| SSH 密码（只在内存使用） — SSH password (used only in memory) | That NAS account's password | Entering an API Key, pairing code, or setup code |
| 安装目录（绝对路径） — Installation directory (absolute path) | A new dedicated directory, such as `/volume1/docker/nas-download` if `/volume1` actually exists | Entering a Windows drive letter, shared-folder display name, another app's directory, or drive root |
| 服务监听地址 — Service bind address | Usually keep `0.0.0.0` | Treating it as the browser sign-in address |
| 服务端口（1024–65534） — Service port | Usually `7120`; reserve the next port, `7121`, too | Checking only `7120` and forgetting that `7121` must also be available |
| 下载模式 — Download mode | **内置下载（推荐）** (Built-in download, recommended) | Selecting advanced mode without an existing downloader |
| 下载保存目录（可留空） — Download directory (optional) | Blank: `downloads` under the installation directory; otherwise a real directory on your download drive | Using program-state directories such as `data` or `engine-config` |

An “absolute path” is the full path starting with `/`. A name such as “Downloads” or “Shared folder” shown by the NAS website may not be the full path. Check properties in the NAS file manager, or ask an administrator. No component of the installation path may be a symbolic link.

**For your first installation, a separate new download directory is recommended.** Files are easier to find and distinguish from your existing download system. An existing directory must also be writable by the SSH account and pass the installer's path checks.

### 3.3 Verify the SSH fingerprint

After you tap **验证并安装** (Verify and install), the first connection shows **确认 NAS 的 SSH 指纹** (Confirm the NAS SSH fingerprint). This acts like an identity number for the NAS on the connection. Compare it with the host public-key fingerprint shown by a trusted NAS terminal or supplied by your administrator. Tap **已核对，信任** (Verified; trust) only after it matches.

An administrator can list host public-key fingerprints locally on the NAS or through an already trusted terminal:

```sh
for key in /etc/ssh/ssh_host_*_key.pub; do
  [ -f "$key" ] && ssh-keygen -lf "$key" -E sha256
done
```

Compare the fingerprint after `SHA256:`. Different host-key algorithms have different fingerprints; match the one corresponding to the dialog. If unsure, cancel and ask an administrator. A later fingerprint change causes the connection to be refused. Disabling verification is not a solution.

### 3.4 Wait for installation to finish

The full package is about 96 MB. Progress covers connection, upload, extraction, installation, and verification. The offline image reduces dependency downloads during the initial NAS build; it does not mean future downloads or site queries work offline.

Keep the app in the foreground and maintain the network connection during installation. Do not tap repeatedly or choose another directory and reinstall because progress briefly pauses. Slow Wi-Fi and a slow NAS increase waiting time; stopping the old service during an upgrade may also take time.

Successful installation normally opens **创建管理员** (Create administrator). If the service is installed but the phone cannot connect, try the manual connection in Chapter 4 before installing again.

## 4. First sign-in, or connecting from a new phone

### 4.1 Create the first administrator

1. Check the service address, for example `http://192.168.50.20:7120`. It uses the NAS IP and selected service port.
2. Choose an administrator username you can remember and a password of at least **10 characters**.
3. Check that **安装生成的初始化码** (Setup code generated during installation) is filled in, then tap **创建并进入** (Create and enter).
4. Seeing **下载任务** (Download tasks) and the built-in downloader in the selector means the basic connection is working.

If the app does not redirect automatically, tap **连接已有 NAS** (Connect to an existing NAS) on the welcome page, enter the service address, then tap **首次安装：创建管理员** (First installation: create administrator). An administrator can find `ND_SETUP_TOKEN` in `.env` in the corresponding installation directory. Share only that setup code privately with the actual installer; do not publish the whole file. The setup code works only before an administrator is created. If one already exists, sign in instead of initializing again.

### 4.2 Sign in with an existing account

Choose **连接已有 NAS** (Connect to an existing NAS), enter the service address and Nas Download administrator username/password, leave the pairing code blank, and tap **连接** (Connect). Do not enter the NAS SSH password, unless you happened to use the same password for both accounts.

This version has no beginner-friendly one-tap “forgot password” flow. Preserve data and contact the service administrator if you forget it. Do not delete the `data` folder to create an account again.

### 4.3 Add another phone

1. On a signed-in phone, tap **更多 → 手机配对码** (More → Phone pairing code), or generate a code in the signed-in web interface.
2. Install the app on the new phone and tap **连接已有 NAS** (Connect to an existing NAS).
3. Enter the same service address, enter the code in **配对码（可代替账号密码）** (Pairing code, can replace username/password), and connect.
4. Codes are **valid for 5 minutes and usable only once**. Generate a new one after expiry rather than repeatedly trying the old code.

Use **更多 → 已登录设备** (More → Signed-in devices) to revoke device access. Pairing grants management access, not read-only guest access. Give it only to people you trust.

### 4.4 Use a computer or iPhone browser

Open the same address in a browser, for example `http://192.168.50.20:7120`, and sign in with the same administrator account. The web interface and Android app manage the same NAS service, tasks, and automation settings.

Do not enter `0.0.0.0` or `localhost`. On a phone, `localhost` means the phone, not the NAS. Do not append paths such as `/api/v1` to the app's service address.

## 5. Complete your first download

### 5.1 Use a magnet link or torrent file

1. On **下载任务** (Download tasks), tap **＋ 添加** (Add).
2. Select the built-in downloader. If several are connected, check that you selected the correct one.
3. Paste a complete link into **磁力链接 / 种子 URL** (Magnet link / torrent URL), or tap **选择 .torrent 文件** (Choose a .torrent file). Use one method, not both. Torrent files selected on the phone have a **2 MB** limit.
4. **Leave 保存目录 (Save directory) blank initially** to use the downloader's default directory.
5. To start immediately, leave **添加后暂停** (Pause after adding) unchecked. Tap **添加** (Add).
6. Read the operation receipt, return to the list, and tap **刷新** (Refresh). Tap the task once it appears to inspect progress, files, and Trackers.

For your first test, choose a resource you are entitled to download that still has active seeders. These fields accept magnet or torrent inputs; pasting an arbitrary movie webpage does not start a download.

### 5.2 How do you know it has finished?

Successful submission means the task was accepted, not that the file is complete. Check progress and completion state in the list and actual NAS files. A magnet task must first obtain torrent metadata; this can take time with a poor network or no peers.

| State shown in the UI | Meaning / what to do |
|---|---|
| 下载中 — Downloading | Files are being received; check whether progress increases |
| 做种中 — Seeding | Files are complete and shared with other downloaders; this does not mean downloading is unfinished |
| 已完成 — Completed | Downloading has finished; look in the NAS save directory |
| 已暂停 — Paused | No transfer; open details and tap 继续 (Resume) to run it |
| 排队中 — Queued | No running slot assigned yet; do not add it again |
| 校验中 — Checking | Checking existing files, including after restart recovery; wait for completion |
| 错误 — Error | Open details for the cause, such as directory permissions, disk, or Tracker problems |

### 5.3 Where are the files actually stored?

Suppose the installation directory is `/volume1/docker/nas-download`:

| Installation choice | Where to find files on the NAS |
|---|---|
| Download directory blank | `/volume1/docker/nas-download/downloads` |
| Download directory `/volume2/Downloads` | `/volume2/Downloads` |
| Tasks added by automated torrent downloading/seeding | Subdirectories `nd-brush/task-ID/info-hash` under that download root |

**Seeing `/downloads` in task details is normal.** It is the path inside the downloader container; the installer connects it to your selected NAS download directory. Ordinary users can leave it blank when adding tasks. Do not copy the NAS host path `/volume2/Downloads` directly into an individual built-in task's save directory.

For built-in downloader subdirectories, use a path below the default root, such as `/downloads/movies`, after checking your requirements. The automated task's save path must match the downloader default directory; leaving it blank is recommended.

## 6. Daily management: view, pause, resume, and delete

- **全部 / 下载 / 完成 / 暂停** (All / Downloading / Completed / Paused) filters the list; it does not change tasks.
- The downloader selector at the top switches between one downloader and all of them. The search box searches task names.
- Tap a task to open details, inspect its files, save directory, and Trackers, then pause or resume it.
- A **Tracker** helps downloaders find each other. Errors can identify site-authentication or network problems. Hide private passkeys in its address before sharing screenshots.

### Distinguish these operations before deleting

| Operation | Result |
|---|---|
| Delete a task with **同时删除下载文件（不可恢复）** (Also delete downloaded files, irreversible) **unchecked** | Removes the task from the downloader but keeps files; keeping files does not mean they are still being seeded |
| Delete a task with that option **checked** | Requests deletion of both task and files by the downloader; this app has no file-recycle-bin restore button |
| 更多 → 下载器管理 → 移除接入 (More → Downloader management → Remove connection) | Removes only this product's connection configuration; does not delete the downloader or its tasks |

Manual deletion is a direct instruction from you. **Do not treat automated seeding/retention protection as a safeguard for manual deletion.** Check PT seeding obligations before acting.

### If submission times out, do not tap again

A result such as **响应未知 / 待确认 / uncertain** (Response unknown / awaiting confirmation / uncertain) may mean the request arrived but its response did not reach the phone. Go to **更多 → 操作记录与待确认回执** (More → Operation history and pending receipts), query the original ID, and check the actual list. Do not submit a new request to repeat an add or delete.

`已登记` (Recorded), `queued`, and `running` mean waiting or in progress. Continue checking the result; they do not prove a download is complete or files have been deleted.

## 7. Optional: search your own PT / Torznab sites

Regular downloads in Chapter 5 work without site search. The software does not include other people's site accounts or keys.

### 7.1 Add a site

Go to **更多 → 站点配置 → ＋ 添加站点** (More → Site configuration → Add site). Enter the name, type, API URL, and your own API Key, then save.

| Type | What to enter |
|---|---|
| M-Team | Obtain your own access token from your site account and enter it separately as the API Key. The app currently suggests `https://api.m-team.cc/api`, and the code also accepts `https://api.m-team.io/api`. These are supported configuration values in this version, not a guarantee of future site addresses |
| Torznab / Jackett / Prowlarr | Copy the site's complete Torznab API path from your configured indexer. Enter the API Key separately; the URL must not include `?apikey=...`, a username, or a password |

Saving stores inputs; it does not prove the site is reachable. An actual search checks credentials and connectivity. HDFans search uses a configured Torznab source, not a native HDFans search API provided directly by this product.

### 7.2 Search and download

1. Return to **下载任务** (Download tasks) and tap **站点搜索** (Site search).
2. Enter keywords and tap **搜索** (Search). Use **停止当前搜索** (Stop current search) to cancel the query.
3. Tap a result's **详情 / 下载** (Details / Download), check the resource, then tap **选择下载器并下载** (Choose downloader and download).
4. Select the downloader, usually leave the save directory blank, and tap **下载** (Download). Return to the list to check the receipt and actual task.

Manual downloads do not use the automated FREE filter. Check whether download traffic will be counted first. Signing in to a site in your browser does not automatically make its API Key available here; these are separate authentication methods.

## 8. Optional: check-in and account checks

Open **更多 → 签到与刷流** (More → Check-in and automated torrent downloading/seeding). Tasks are stored in the NAS service and, when enabled, run on schedule even when the phone is off. New tasks are disabled by default and do not import old-system tasks.

### 8.1 Understand the three functions first

| Function | What it actually does |
|---|---|
| HDFans check-in | Uses your supplied Cookie to access the check-in endpoint; expiry, captchas, and similar issues are logged as errors |
| Custom site check-in | Sends a configured HTTP request and judges success using explicit response text |
| M-Team account check | Checks the account API and VIP expiry; **it is not a website sign-in/check-in or an account-retention action** |

A Cookie is part of a website login session, not the password. Being signed in through a browser does not mean the app has your Cookie. Never put API Keys, Cookies, setup codes, or pairing codes in a sharing bundle or public screenshot.

### 8.2 Recommended sequence for beginners

1. Choose the task type, enter a task name, and supply your own site-authentication information.
2. Leave **启用 NAS 后台定时任务** (Enable scheduled NAS background task) unchecked and save first.
3. Tap **只读预演（默认）** (Read-only dry run, default) and inspect configuration-check results. A custom HTTP check-in dry run does not actually request the site, so it cannot prove authentication works or check-in succeeds.
4. Check that another application is not already running the same check-in task, then edit and enable it.
5. To test the real result, tap **实际运行** (Actual run) and confirm. Check **运行日志 / 刷新状态** (Run logs / Refresh status), and verify on the site if needed.

By default, tasks run randomly during the daily **08:00–10:00 Beijing time** window; you can change it. At most one actual check-in attempt is allowed per day. An uncertain result is not retried automatically. Missing today's automatic window schedules the next day, not a late-night catch-up request. Manual actual runs also obey the once-per-day limit.

Custom check-in needs the correct request method, URL, parameters, and success marker. If you do not understand them, ask the site administrator for an integration method instead of arbitrarily using “success” as the criterion. Sites requiring captchas, dynamic tokens, or complex web sign-in cannot be automated with this single-request template alone.

**停止并停用** (Stop and disable) prevents future automatic write operations. A request already sent may still complete; check logs. Updating the Cookie does not reset that day's already-used check-in attempt.

## 9. Optional: unattended downloads and automatic cleanup

This is an advanced feature for people familiar with downloads and site rules. **Complete one manual download before enabling an automatic task.** Automation is configurable; it does not guarantee maximum speed or a particular upload total.

### 9.1 The safest enabling sequence

1. Check that site search works and the selected downloader is correct.
2. Create an automated torrent downloading/seeding task in **签到与刷流**; initially leave the save directory blank.
3. Keep **仅 FREE** (FREE only), leave automatic cleanup and file deletion disabled, and choose **未知：保持保护，不自动清理** (Unknown: keep protected, no automatic cleanup) if you cannot confirm seeding obligations.
4. Review concurrency, capacity, and reserved space. Save and run **只读预演** (Read-only dry run) to inspect candidates and retention reasons.
5. Enable only after everything is correct. You can also use **实际运行** (Actual run), then confirm actual additions in the task list.
6. After operation is stable, configure cleanup only if you understand site seeding requirements and accept deletion. Protection when information is unknown is expected behavior.

### 9.2 Common fields in this version

| Field | Default | What it means |
|---|---|---|
| 检查间隔 — Check interval | 10 minutes | How often this task runs; configurable from 2–1440 minutes |
| 全部未完成任务并发上限 — Limit on all incomplete tasks | 8 | Admission limit for automatic additions to the selected downloader; manual, paused, and queued incomplete tasks count too. It does not forcibly constrain every qB running behavior to 8 tasks |
| 保留磁盘空间 — Reserved disk space | 100 GiB | Space kept for the system and other uses; outstanding bytes of incomplete tasks are also reserved before additions |
| 本任务容量上限 — Capacity limit for this task | 500 GiB | Limits torrent capacity managed by this automated task, not total NAS capacity |
| 最低做种人数 / 最低下载人数 — Minimum seeders / downloading peers | 2 / 3 | Candidates need sufficient evidence of participant counts; not a speed guarantee |
| 清理前观察小时 — Observation before cleanup | 6 hours | Observe new tasks first; unfinished downloads are not rotated out as low-performing torrents |
| 低上传阈值 — Low-upload threshold | 32 KiB/s | Requires roughly one hour of complete samples; retained if current upload speed or the hourly average meets the threshold |
| 低需求人数阈值 — Low-demand participant threshold | 0 | Extra condition disabled by default; enabling it also requires continuous supporting samples |
| 仅 FREE / 促销白名单 — FREE only / promotion allowlist | Enabled / FREE | Add only resources matching verified promotion conditions; FREE means a download-traffic exemption |
| 自动清理 — Automatic cleanup | Disabled | Only when enabled can owned tasks meeting every condition be removed |
| 同时删除已验证文件 — Also delete verified files | Disabled | Requires automatic cleanup enabled and successful file/directory verification too |
| 新任务保种条件 — Seeding requirements for new tasks | Unknown | Protected by default; after confirming rules, declare no obligation or require both seeding hours and share ratio to be met |

Capacity is used only for safe space calculations, not as a per-torrent size cutoff or ranking bonus. By default, the number of downloading peers is prioritized, then the demand-to-supply ratio. These are this standalone product's defaults. It does not automatically import another app's automated torrent rules, task pools, or dynamic concurrency settings.

### 9.3 VIP and non-FREE resources

New non-FREE M-Team resources are allowed only when you turn off “FREE only,” include the promotion in the allowlist, and the program confirms VIP status and a future expiry during that run. Expired or unverifiable VIP status falls back to FREE. Torznab does not use M-Team VIP privileges.

This is only a **condition for adding new tasks**. It does not guarantee a resource stays FREE throughout downloading or that VIP exempts you from seeding. “I am VIP” is not a reason to delete all tasks.

### 9.4 Which tasks are excluded from ordinary automatic cleanup?

The program manages only tasks it added and durably registered itself. Ownership, tag, hash, or path mismatches; unknown seeding obligations; manual permanent protection; insufficient observation; downloads in progress; and paused, queued, checking, or error states all block ordinary low-performance cleanup.

Before deleting files, it also verifies the dedicated directory, original file list, shared paths, links, and other conditions. Uncertainty means retention. Each cycle removes at most one item, then confirms the result and rereads free space before deciding whether to add a replacement. **This version does not promise a replacement after every deletion.** A successful receipt does not prove space has been freed.

A new task's seeding declaration is saved when it enters the managed pool. Later configuration changes do not remove unknown-obligation protection from old tasks. Register resources you want to retain permanently under **归属与永久保护** (Ownership and permanent protection). Removing explicit protection does not bypass other restrictions.

### 9.5 What happens to downloads when an automatic task stops?

**停止并停用** (Stop and disable) stops that automation's future actions; it does not tell the downloader to pause or delete every torrent already added. To pause a particular download, use task details. If a result is uncertain, check logs and the original run ID instead of creating a duplicate task.

## 10. Access from outside your home

Get it working at home first, then configure remote access. A home LAN IP usually cannot be reached directly from an outside Wi-Fi network.

If you already use Tailscale, join the NAS and phone to the same trusted network and enter the NAS's **numeric Tailscale IP** service address. HTTP accepts only local or numeric Tailscale IPs allowed by the code, not arbitrary HTTP domains. For a public domain, use HTTPS with a valid certificate.

The app does not automatically install Tailscale, configure your router, obtain a public IP, or open inbound ports. Do not forward the unencrypted `7120` sign-in endpoint directly to the internet. Opening the web interface does not prove BT inbound connectivity; speed still depends on peers, network, disks, and bandwidth.

## 11. Advanced: connect an installed downloader

When the initial mode is **高级：接入已有下载器** (Advanced: connect an existing downloader), the product does not start its own download engine. After installation, go to **更多 → 下载器管理 → ＋ 添加下载器** (More → Downloader management → Add downloader). Enter the type, name, address, username, password, and default save directory. Tap **测试连接** (Test connection) before saving.

The address is accessed by the **NAS service**. `localhost` in one container is not another container. Use an address reachable from the service's network. Do not use your existing downloader for first-time automatic file-deletion experiments.

Automatic cleanup of external-downloader data requires an administrator to configure the corresponding download directory as a read-only verification mount. Without it, leave file deletion disabled. Mount instructions are in the developer guide [docs/AUTOMATION_EN.md](AUTOMATION_EN.md); they do not concern ordinary built-in installation.

Installation mode is not a switch that migrates tasks in place. Do not arbitrarily change an installation directory from built-in to existing mode, or the reverse. Plan a migration; do not delete configuration to bypass a warning.

## 12. Advanced: manual NAS installation without a phone

Ordinary Android users who completed Chapter 3 do not need this chapter. It is an alternative for administrators who can use a NAS terminal. Do not run Linux installation commands directly in a local Windows terminal.

1. Upload `Nas-Download-Standalone-1.3.0-install.tar.gz` to a **temporary empty directory** on the NAS.
2. Enter that directory in a NAS terminal and extract the package. The temporary extraction directory must be separate from the final installation directory; otherwise the installer treats the target as containing other files.
3. Verify that the paths below belong to this NAS before running them. This example applies only to NAS devices with `/volume1`; otherwise replace the entire installation path with your actual storage path.

```sh
tar -xzf Nas-Download-Standalone-1.3.0-install.tar.gz
sh install.sh --dir /volume1/docker/nas-download --port 7120 --mode bundled
```

To store downloads separately, if `/volume2/Downloads` really exists and is writable by your current NAS account, replace the second command with:

```sh
sh install.sh --dir /volume1/docker/nas-download --port 7120 --mode bundled --downloads /volume2/Downloads
```

Choose one installation command, not both in succession. The full package includes the image; no separate development image archive is required.

Successful installation outputs three important fields:

| Output | How to use it |
|---|---|
| `NAS_DOWNLOAD_READY` | Web-service entry point; replace `0.0.0.0` with the actual NAS IP if shown |
| `NAS_DOWNLOAD_SETUP_CODE` | Setup code for the first administrator; keep private |
| `NAS_DOWNLOAD_PROJECT` | Container project name for this installation; keep to identify it during maintenance |

Open the correct service URL in a browser and create the administrator as in Chapter 4. A terminal exiting or webpage opening does not mean files have downloaded; still complete the real-download check in Chapter 5.

### Installation parameters

| Parameter | Default / purpose |
|---|---|
| `--dir` | Required: a new empty directory, or this product's original marked installation directory |
| `--port` | `7120`; range 1024–65534, with the next TCP/UDP port also used in built-in mode |
| `--bind` | `0.0.0.0`; must be a valid IPv4 bind address |
| `--mode` | `bundled` for built-in; `existing` for an existing downloader |
| `--downloads` | New built-in installation: `installation-directory/downloads`; omitting it during upgrade retains the recorded download path |

## 13. Upgrade, back up, stop, and remove

### 13.1 Upgrade the phone app

A new APK with the same release signing certificate can replace the installed app; uninstalling first is unnecessary. Retention of the signed-in session through upgrade has been verified. If Android reports a signing conflict, check whether you installed a debug/preview package. Do not uninstall first and only then discover that pending operation records were not preserved.

**Updating the phone APK does not automatically update the NAS service.** Rerun the new installation flow against the original NAS installation directory. Before upgrading, record the directory, mode, port, and download path. A new directory creates another independent instance rather than upgrading the old one.

### 13.2 Upgrade the NAS service

1. Record the current service address and installation directory, and resolve uncertain operation results.
2. Back up, or ask an administrator to arrange a consistent backup while stopped. Do not copy just one database file while it is being written.
3. Use automatic installation from the new app or the new manual installation package, specifying **the same installation directory, same mode, and original port/download path**.
4. After preparing the image, the installer briefly stops its owned instance, saves matching configuration and state, then switches and verifies. Failure triggers an attempt to restore the matching old version.
5. After completion, sign in/refresh and check task counts, paths, and important files. Do not immediately remove rollback backups.

### 13.3 What to back up

| Contents | Why to keep them |
|---|---|
| Entire `data` directory | Accounts, encryption keys, configuration, operation receipts, and task records; losing keys affects decryption of existing credentials |
| `engine-config` | Built-in engine settings, torrents, and recovery state |
| `.env`, installation marker, Compose files | Original paths, mode, project, and connection settings; contain secrets and must not be shared publicly |
| Actual download directory | Real files; may be on another drive rather than inside the installation directory |
| `installer-backups` | Matching rollback records generated by the installer; use space, but do not delete before verification |

Share only release packages and manuals with others. **Do not archive your entire installed directory**; it contains your accounts, keys, and task state.

### 13.4 Stop using it temporarily, or uninstall

To stop temporarily, find the project identified in the installation output in the NAS container manager and stop only that product project. Its web interface, downloads, and automation stop with it. Do not accidentally stop the old system's qB or other containers.

To remove the program, first disable automation, confirm receipts, and back up. Then remove the explicitly identified product container while **keeping configuration and download directories**. The software has no automatic file-migration or reliably reversible one-click file-deletion feature. Decide separately whether to remove files. Do not use commands that clear all Docker resources.

## 14. Troubleshooting

| Situation or message | Possible cause | First action |
|---|---|---|
| APK will not install | Android older than 8.0, installation-source permission, or signing conflict | Check Android version, package integrity, and whether another signing variant is installed |
| SSH connection times out / is refused | Wrong IP/port, SSH disabled, or network isolation | Retry on the same LAN; check NAS SSH settings and port. Do not substitute web port `7120` for the SSH port |
| SSH authentication fails | Wrong NAS credentials or account not allowed to use SSH | Verify the NAS account, not the software account |
| SSH fingerprint changes | NAS reinstall, different host, changed keys, or wrong target | Verify cause and new fingerprint; do not bypass verification or blindly erase the saved record |
| Docker / Compose not installed | Missing runtime environment | Install the NAS container environment; the app will not do it for you |
| Current account lacks Docker permission | SSH account lacks container permission | Ask an administrator to authorize an appropriate account or install manually; do not expose Docker to the network |
| Target directory contains other files | Existing project or extraction directory selected | For a fresh install, choose a truly empty dedicated directory. For upgrade, check the product marker; do not empty an existing directory |
| Installation already running / installation lock | Earlier process unfinished or interrupted | Wait and ask an administrator to check the process; do not simply delete a lock |
| Directory not writable / unsafe path | Insufficient permission, nonexistent storage path, symbolic link, or state-directory overlap | Check real paths and permissions; do not grant whole-drive access to bypass checks |
| Installation port occupied | `7120` or `7121` in use, or bind address unavailable | Identify the conflict. A fresh install can use a confirmed available adjacent pair such as `7130/7131` |
| Service or engine not ready | Engine startup, permission, resource, or configuration problem | Keep errors and installation records and inspect this product's container; do not continuously create more instances |
| Webpage inaccessible after installation | Address is `0.0.0.0`, wrong port, or NAS offline | Use actual NAS IP and service port; test in a browser on the same network first |
| Public / domain HTTP address refused | App rejects arbitrary unencrypted remote addresses | Use an allowed numeric IP locally; use the correct HTTPS service URL publicly |
| Setup code invalid / already initialized | Code from another instance, or administrator already exists | Check address and matching installation directory; if initialized, sign in with the account |
| Sign-in expired | Session revoked or expired | Sign in again; no NAS service reinstallation needed |
| Empty list | New installation, filters, wrong downloader, or connection error | Select 全部下载器 (All downloaders) and 全部 (All), clear search, and inspect errors |
| Download speed 0 | Paused, queued, no active peers, or Tracker/network/disk problems | Inspect one task's details: state, space, and Tracker. Do not repeatedly add it |
| Still uploading at 100% | Normal seeding | Download complete; PT users should continue seeding as required |
| Space unchanged after task deletion | File deletion not selected, or other data still uses space | Verify deletion options, receipt, and files; do not infer freed space from torrent size |
| Site saves but search fails | API Key, URL, or connectivity problem | Inspect that site's error; browser sign-in and API authentication are separate |
| Check-in did not run | Disabled, window not reached, today's attempt already used, or authentication expired | Check next-run time and logs; an M-Team account check is not check-in |
| Automation adds no new torrents | Concurrency limit reached, insufficient reserved space, no eligible candidates, or authentication problem | Run a read-only dry run to see why; do not arbitrarily lower reserved space |
| Automation never cleans up | Cleanup disabled, unknown seeding obligations, insufficient observation, permanent protection, etc. | Inspect retention reasons; do not remove protection you do not understand just to rotate torrents |
| Submission times out; result unknown | Request may have executed but response was lost | Query the original receipt and actual task; do not blindly send it again |

### What to include in a problem report

Provide app version, NAS model/architecture, phone OS version, built-in or existing-downloader mode, failing step, exact error, time, and operation ID. Screenshots with sensitive information hidden can be attached.

Do not provide passwords, Cookies, API Keys, setup codes, pairing codes, complete `.env`, `secret.key`, databases, or Tracker URLs with passkeys. These are not ordinary diagnostic materials.

## 15. Frequently asked questions

### Do I need a PT account?

No. Ordinary magnet and torrent downloads do not require PT site configuration. Site search and check-in require your own corresponding accounts and credentials.

### Will downloads continue when the phone is off?

Yes, as long as the NAS, network, and product container keep running. Downloaded files do not pass through phone storage.

### Why do I still need a NAS username and password? Is this not automatic installation?

Your phone needs an installation connection authorized by you; it cannot bypass device permissions. Default installation includes the engine, internal connection, and image, but SSH, Docker, and storage permissions remain NAS settings.

### Does one container mean qB is no longer used?

It still uses the established qBittorrent engine, managed as part of the product. Ordinary users do not need to install it separately, sign in to it, or configure its internal password.

### Will installation guarantee high speed?

No. Speed depends on resource demand, peers, home upload/download bandwidth, disks, and connectivity. An accessible webpage or mapped port does not prove public Peer inbound connectivity has been verified.

### Can I compress my installation directory and give it to a friend?

No. Share the clean APK / manual installation package and this guide. Your friend enters their own NAS and site information. Your installed directory contains your sign-ins, keys, and tasks.

### Can I install on an SSD and download to a mechanical hard drive?

Yes. Choose separate installation and download directories. Verify real paths during installation. Do not simply move directories in a file manager afterward; existing mounts and download tasks do not update automatically.

### What is the minimum I need to do now?

Prepare NAS SSH and Docker → open 自动安装 (Automatic installation) in the APK → choose built-in download → create an administrator → add one torrent. Then consider optional features in Chapters 7–9.

Return to [First use: quick start](QUICK_START_EN.md).
