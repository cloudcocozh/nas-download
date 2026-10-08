# 第三方组件与对应源码

**简体中文** | [English](THIRD_PARTY.en.md)

本项目原创管理服务、网页、Android 客户端采用 MIT。第三方组件各自许可独立保留；根目录 LICENSE 不重新许可这些第三方组件。

## 固定的下载引擎

1.3.0 离线镜像中的 qBittorrent 为 5.2.4，复制自固定 LinuxServer 镜像摘要。实际引擎 buildInfo 核对：Qt 6.11.2、libtorrent 2.0.15.0、Boost 1.92.0、OpenSSL 4.0.2、zlib 1.3.2。具体镜像、二进制摘要与构建提交见 [RELEASE_COMPONENTS.json](docs/RELEASE_COMPONENTS.json)。没有修改 qB 引擎代码。

qBittorrent 源码 GPLv2-or-later，二进制 GPLv3-or-later，并带上游 OpenSSL 例外。原文：[COPYING](licenses/qbittorrent/COPYING)、[GPLv2](licenses/qbittorrent/COPYING.GPLv2)、[GPLv3](licenses/qbittorrent/COPYING.GPLv3)。Qt 与其他依赖的许可见 [licenses](licenses)。

## 与二进制同处提供的源码材料

[本版本 Release](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1) 提供 `Nas-Download-1.3.0-third-party-sources.tar.gz`，与安装包同页、无需付费下载。内含 qBittorrent、Qt base/tools、libtorrent、Boost、OpenSSL、zlib 及相关依赖源码归档，静态构建脚本、补丁、LinuxServer 固定构建提交，以及版本与 SHA256 清单。

来源与校验值见 [THIRD_PARTY_SOURCES.json](docs/THIRD_PARTY_SOURCES.json)。使用与实际引擎版本一致的历史依赖源归档，而不是已经更新的 latest；保存上游归档原始字节。构建步骤及平台配置位于随附 `qbittorrent-nox-static-build-scripts.tar.gz` 的 README、工作流及构建脚本中。该材料用于取得和修改对应组件，不声称已证明整个镜像位级可重复构建。

## Android 与 Python

已解析 Android releaseRuntimeClasspath：OkHttp 4.12.0、Okio 3.6.0、mwiede JSch 0.2.26、Kotlin 1.9.10、JetBrains annotations 13.0。其许可及必要通知保留在 [licenses](licenses)。JSch 包内的多项第三方许可也一并保存。

Python cryptography 固定为 50.0.0；Python 镜像内相关 wheel 的许可保留于 `licenses/python-image`。CPython 与 Debian 基础系统的版权文件继续随镜像保留；Debian 实际包版本见 [DEBIAN_PACKAGES.json](docs/DEBIAN_PACKAGES.json)，对应源码可以在 [Debian Sources](https://sources.debian.org/) 按源码包名和版本取得。musl、tini 的许可另行保存。

## 重新分享时

保留本项目 MIT 许可、第三方许可与通知，以及对应源码材料的取得说明。完整分享包附有这些材料的说明；只转发裸 APK 时也应一并提供本 Release 页面，不把第三方组件说成 MIT。
