# NASDownload 1.3.0

[中文](RELEASE_1_3.md) | English

Android versionCode: 6. The download engine is built in by default: the management service and qBittorrent 5.2.4 run in the same product container. Advanced mode continues to support existing downloaders. Phone installation defaults to the built-in mode. Port validation matches the Linux installer (1024–65534). Upload progress shows the actual percentage, with longer timeouts for large installation packages.

The complete offline package includes a prebuilt image; the lightweight source package can be built on the NAS. Initial installation requires a Linux NAS, SSH, Docker Compose, and permission to manage containers. This version was first verified on x86_64; ARM has not been tested. The application continues to use the original release signing identity, and upgrades preserve user credentials.

Verification of tasks, paths, engine recovery, upgrade rollback, and real downloads is reported in the [current acceptance record](ACCEPTANCE_1_3_EN.md). This release note does not present plans or simulated tests as passes on actual devices. Version 1.3.0 is published as a beta in this repository's [Releases](https://github.com/cloudcocozh/nas-download/releases).

In an isolated x86_64 Linux NAS environment, this version passed verification of real single-container downloads, pause/resume, deletion and replacement, engine fault recovery, restart, and forced rollback. Normal two-container migration was also verified: the old engine stopped, and the original session, task hash, path, and file SHA256 were preserved. See the [final acceptance report](ACCEPTANCE_1_3_EN.md) for the evidence. The complete package includes the prebuilt image. This is a public beta: long-term operation has not been observed, and compatibility with every NAS, ARM device, or phone is not claimed. The phone's SSH protocol and signing identity continuity during upgrade were checked separately using an isolated emulator.
