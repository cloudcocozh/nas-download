# Third-Party Components and Corresponding Source

[中文](THIRD_PARTY.md) | English

This project's original management service, web interface, and Android client use the MIT license. Third-party components retain their own separate licenses; the root LICENSE does not relicense those components.

## Pinned download engine

The 1.3.0 offline image contains qBittorrent 5.2.4, copied from a LinuxServer image pinned by digest. The actual engine's buildInfo was checked: Qt 6.11.2, libtorrent 2.0.15.0, Boost 1.92.0, OpenSSL 4.0.2, and zlib 1.3.2. See [RELEASE_COMPONENTS.json](docs/RELEASE_COMPONENTS.json) for image and binary digests and build commits. The qB engine code has not been modified.

qBittorrent source is licensed under GPLv2-or-later, and its binary under GPLv3-or-later, with the upstream OpenSSL exception. Original texts: [COPYING](licenses/qbittorrent/COPYING), [GPLv2](licenses/qbittorrent/COPYING.GPLv2), and [GPLv3](licenses/qbittorrent/COPYING.GPLv3). Licenses for Qt and other dependencies are in [licenses](licenses).

## Source materials provided alongside the binaries

[This version's Release](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1) provides `Nas-Download-1.3.0-third-party-sources.tar.gz` on the same page as the installation packages, available to download free of charge. It contains source archives for qBittorrent, Qt base/tools, libtorrent, Boost, OpenSSL, zlib, and related dependencies; static build scripts; patches; the pinned LinuxServer build commit; and version and SHA256 manifests.

Sources and checksums are listed in [THIRD_PARTY_SOURCES.json](docs/THIRD_PARTY_SOURCES.json). Historical dependency source archives matching the actual engine versions are used, rather than an updated latest version; the original bytes of upstream archives are preserved. Build steps and platform configuration are in the README, workflows, and build scripts within the included `qbittorrent-nox-static-build-scripts.tar.gz`. These materials let you obtain and modify the corresponding components. They do not establish that the entire image can be rebuilt bit for bit.

## Android and Python

The resolved Android releaseRuntimeClasspath contains OkHttp 4.12.0, Okio 3.6.0, mwiede JSch 0.2.26, Kotlin 1.9.10, and JetBrains annotations 13.0. Their licenses and required notices are retained in [licenses](licenses). The multiple third-party licenses included in JSch are also preserved.

Python cryptography is pinned to 50.0.0. Licenses for the relevant wheels in the Python image are retained in `licenses/python-image`. Copyright files for CPython and the Debian base system remain in the image. Actual Debian package versions are listed in [DEBIAN_PACKAGES.json](docs/DEBIAN_PACKAGES.json); corresponding source can be obtained from [Debian Sources](https://sources.debian.org/) by source package name and version. Licenses for musl and tini are stored separately.

## Redistributing the project

Retain this project's MIT license, third-party licenses and notices, and the instructions for obtaining corresponding source materials. The complete distribution package includes information about these materials. If you share only the APK, also provide this Release page; do not describe third-party components as MIT-licensed.
