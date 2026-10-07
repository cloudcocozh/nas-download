# Nas Download

**把下载交给自己的 NAS，手机和网页只负责操作。** 默认一个容器，内置 qBittorrent；不需要单独安装、登录和配置 qB。

当前公开版本：**1.3.0 测试版**。Linux x86_64 NAS；Android 8.0 或以上。ARM 暂不支持。

## 直接下载使用

**[打开下载页：v1.3.0-beta.1](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1)**

| 想怎么使用 | 下载什么 |
|---|---|
| 第一次使用 | **完整分享包**，解压后打开“先看这里.html” |
| 安卓手机自动安装到 NAS | **Nas-Download-Standalone-1.3.0.apk** |
| 管理员在 NAS 终端安装 | **Nas-Download-Standalone-1.3.0-install.tar.gz** |
| 先看使用方法 | [快速上手](docs/QUICK_START_ZH.md) / [完整说明书](docs/USER_MANUAL_ZH.md) |

绿色 **Code → Download ZIP** 是工程源码，不是手机安装包。普通用户请使用下载页。

## 能做什么

- 添加磁力、种子地址或 `.torrent` 文件，查看真实进度、速度、文件与 Tracker。
- 暂停、继续、删除任务；删除文件需要单独选择。
- Android 与网页管理同一套任务，支持手机配对和撤销设备登录。
- 可选配置自己的 M-Team / Torznab 站点，搜索、看详情并主动下载。
- 可选签到、账户检查和无人值守下载；在 NAS 后台运行，默认停用。
- 高级模式接入已有 qBittorrent 4/5 或 Transmission 4。

文件保存在 NAS 硬盘，手机关闭后 NAS 可继续下载。软件不提供 PT 账号、邀请、API Key、Cookie 或资源。

## 新手安装

1. NAS 准备好 **SSH、Docker 和 Docker Compose**；SSH 账号须有 Docker 权限。首次让手机与 NAS 在同一家庭网络。
2. 安装 APK → “自动安装” → 填自己的 NAS 地址、SSH 账号和专用安装目录 → 保留“内置下载（推荐）”。
3. 核对 NAS SSH 指纹并等待安装，创建软件管理员，再点“＋ 添加”完成第一个下载。

**每一格怎么填、文件在哪里：[逐步快速上手](docs/QUICK_START_ZH.md)。**

默认网页端口 7120，内置下载另用 7121 TCP/UDP。两个端口都不能冲突。App 不会替你开启 SSH、安装 Docker 或提权。NAS SSH 账号与软件管理员账号是两种用途。

管理员可从 Release 获取完整安装包，上传到 NAS 的临时空目录，在 NAS 终端执行：

```sh
tar -xzf Nas-Download-Standalone-1.3.0-install.tar.gz
sh install.sh --dir /volume1/docker/nas-download --port 7120 --mode bundled
```

路径只是示例，须替换成你自己的可写专用目录。解压目录和安装目录要分开。手机自动安装与手动安装选一种，不必重复。详情见说明书第 12 章。

## 自动化与保护

签到、刷流默认不开启，可先只读预演。自动化只管理自己添加并登记的任务；保种义务未知、永久保护、观察不足或身份/文件核验失败时保留。自动删除和删除文件均须明确开启。

M-Team 账户检查不是网页登录签到或保号。可验证 VIP 只决定非免费新种准入，不代表豁免保种或整个下载期间免费。本产品不导入其他软件的刷流规则。见 [自动化参考](docs/AUTOMATION.md)。

## 验证范围

隔离 x86_64 NAS 真实下载、暂停/恢复、自动删补、引擎恢复、旧版迁移、失败回滚通过；Linux 验收测试 145 项通过。Android 模拟器原生操作、完整包 SSH/SFTP 和同签名覆盖升级通过。

尚未完成真实手机到 NAS 的完整首次安装、多日运行或所有机型兼容验证。当前是测试版，不承诺满速或公网入站可达。[验收记录](docs/ACCEPTANCE_1_3.md)。

## 文档与源码

- [快速上手](docs/QUICK_START_ZH.md) / [完整说明书](docs/USER_MANUAL_ZH.md)
- [开发与构建](docs/BUILDING.md)
- [自动化参考](docs/AUTOMATION.md) / [站点接入](docs/SITES.md)
- [隐私说明](PRIVACY.md) / [第三方组件](THIRD_PARTY.md)

离线 HTML 说明书在 Release 的说明书压缩包里，可搜索章节、打印或保存 PDF。

本项目原创管理服务、网页、Android 客户端和文档采用 [MIT License](LICENSE)。qBittorrent、Qt、Python 等第三方组件保留各自许可，不因项目采用 MIT 而改为 MIT。第三方许可与对应源码材料见同一版本 Release。

不包含私人 NAS 配置、站点账号、下载数据或正式签名密钥。通过 [Issues](https://github.com/cloudcocozh/nas-download/issues) 反馈时请提供版本、步骤和脱敏错误，不要上传密码、Cookie、API Key 或带 passkey 的地址。
