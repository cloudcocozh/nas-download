# NASDownload 1.3.0 Acceptance Record

[中文](ACCEPTANCE_1_3.md) | English

Date: 2026-10-07. Standalone application package: `com.nasdownload.app`; versionCode: 6.

## Completed

- The default deployment integrates qBittorrent 5.2.4 in a single container. First-time deployment requires no separate qB installation or configuration. Advanced settings still support external downloaders.
- The built-in downloader API listens only on the container's loopback address and requires authentication. The service port and peer connection port are configurable. The installation package includes an offline x86_64 Docker image to reduce image-pulling requirements during initial NAS setup.
- A separate installation directory, installation lock, path and port checks, and a maintenance gate during upgrades are implemented. The image is prepared before stopping the owned instance and backing up its matching configuration and state.
- Engine failures trigger a limited number of restarts. State is saved on exit, and new application changes are blocked during shutdown. Failed upgrades automatically restore the previous image and matching state; downloaded files are not overwritten with older copies.
- Unattended operation retains ownership checks, an observation period, checks before deletion, and replacement records. Tests did not connect to the user's private tracker accounts or change production seeding/retention policies.

## Actual verification

| Item | Result and limits |
|---|---|
| Linux automated tests | 145 passed, none skipped; includes safety boundaries, recovery, and installer tests |
| Web interface and installer | Three groups of web checks passed; installation locking, path conflicts, partial stop failures, offline import, and rollback contract checks passed |
| Real download | A private, self-generated test torrent downloaded through a local HTTP webseed; complete file bytes were checked; pause, resume, and deletion passed |
| Unattended torrent replacement | New-torrent observation protection passed. After simulating an age of 7 hours in a separate test process, real qB deletion and file removal, rereading capacity, adding a replacement, and completing its download passed. This does not demonstrate 7 hours of continuous operation |
| Fault recovery | Automatically recovered after deliberately terminating the test qB process. A complete container stop/start preserved the session, single task, and file SHA256; graceful exit code was 0 |
| Upgrade from the previous version | An actual 1.2.1 two-container copy migrated to the 1.3.0 single-container deployment. The original login, task hash, file path, and SHA256 were retained; the old engine was stopped |
| Forced rollback | Deliberately failed the upgrade health check; automatically restored the 1.2.1 two-container deployment and matching state. The original task, session, and files remained intact |
| Android | Native screens, the SSH/SFTP installation flow with the complete offline image, an in-place upgrade from 1.2.1 using the original signing identity, and persistent sessions passed. The SSH server was a local test fixture; NAS server acceptance was completed separately |

The first real download exposed a health-check defect triggered only after the engine had tasks. It was fixed and covered by a regression test. The results above come from testing again after the fix.

## Protecting existing systems and cleanup

All tests used dedicated directories and separate ports. Seven existing services, including the three-in-one application and its downloaders, M-Team, NAStool, Studio, and OpenClaw, were checked individually: their container IDs and start times were unchanged, and they remained running. The existing standalone product preview remained stopped.

The three test containers and two empty test networks created during this round were removed. Isolated test records and rollback copies were retained for reference. No user downloads or media files were deleted, and no global image cleanup was performed.

## Supported scope

The tested environment was a Linux x86_64 NAS, Docker Compose, an SSH account with the required Docker permissions, and an Android emulator. ARM NAS devices are outside the current offline image's supported scope. Multiday private tracker operation, compatibility with every NAS or phone model, and public inbound connectivity have not been verified. Reducing the container count alone does not promise higher upload speeds.

The installation package and source are ready for distribution. Public beta releases are available in this repository's [Releases](https://github.com/cloudcocozh/nas-download/releases); they have not been uploaded to an app store or public image registry. File checksums are provided in `SHA256SUMS.txt` on the [public Release page](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1).
