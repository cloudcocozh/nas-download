# 从源码测试和构建

**简体中文** | [English](BUILDING_EN.md)

普通用户直接使用 [Release 安装包](https://github.com/cloudcocozh/nas-download/releases/tag/v1.3.0-beta.1)。本页面向开发者。

## 结构

`server/` 是 Python 服务，`web/` 是网页，`deploy/` 与 `install.sh` 管理安装、引擎和升级，`android/` 是原生 Java 客户端，`tests/` 是后端与 Linux 安装器测试。

## 后端与网页测试

需要 Python 3.11、Node.js；完整安装器测试在 Linux 运行，Windows 会明确跳过部分 Linux 测试。

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r server/requirements.txt
python -m unittest discover -s tests -v
node web/tests/smoke.cjs
node web/tests/sites-smoke.cjs
node web/tests/automations-smoke.cjs
```

测试使用独立临时数据和适配器，不连接真实 PT 凭据或现有下载器做删除试验。

## Linux 镜像

```sh
docker build -t nas-download:1.3.0 .
```

Dockerfile 的引擎复制阶段固定到特定上游镜像摘要，支持 x86_64。Python 基础镜像与系统包未全部固定摘要，源码重建不承诺与发布镜像逐字节相同。用安装器部署到新测试目录，不覆盖现有运行状态。

## 准备 Android 内置资源

仓库根目录执行：

```sh
python deploy/package.py
```

生成 `android/app/src/main/assets/installer.tar.gz`，以及相邻 `outputs` 目录的源码和安装包。无镜像的源码型资源首次安装会在 NAS 构建，需要网络。

若有 `docker save` 导出的 gzip 镜像，可以构建完整离线资源：

```sh
python deploy/package.py --image /实际路径/nas-download-image.tar.gz
```

APK 的 `assets/installer.bundle` 必须与资源 gzip 逐字节一致。不要打入真实 NAS 的 `.env`、`data`、密钥或下载数据。

## Android 构建

使用 JDK 17、Android SDK 35、Build Tools 35.0.0、Gradle 8.10.2，项目插件 AGP 8.7.3。本仓库没有 Gradle Wrapper，请安装 Gradle 或在 Android Studio 配置版本。按自己的环境设置 `JAVA_HOME`、`ANDROID_HOME`。

```sh
gradle -p android assembleDebug lintDebug
```

Debug 包名 `com.nasdownload.app.debug`，可与正式版并存。设备测试需构建 `assembleDebugAndroidTest` 并使用独立模拟器，不清理个人设备的数据。

正式签名从环境变量 `NAS_DOWNLOAD_SIGNING_FILE` 读取配置文件路径，或使用 Android app 项目目录下的本地 `signing.properties`：

```properties
storeFile=/absolute/path/to/your-release-keystore.jks
storePassword=REPLACE_WITH_YOUR_SECRET
keyAlias=YOUR_ALIAS
keyPassword=REPLACE_WITH_YOUR_SECRET
```

```sh
gradle -p android assembleRelease lintRelease
```

签名配置和密钥禁止提交 Git。你自己的签名不能直接覆盖官方同包名安装版；开发优先用 Debug 包。缺少签名配置不代表生成了已签名可发布包。

公开源码与 1.3.0 已验收运行代码一致；仅移除了开发机专用签名路径，并增加公开文档、许可和测试流程。二进制放在 Releases，不放 Git 历史。

## 更新双语离线说明书

中英文 Markdown 分开维护，顶部提供语言切换。修改后重新生成 HTML；说明书使用独立依赖，不增加 NAS 运行依赖。

```sh
python -m pip install -r deploy/docs-requirements.txt
python deploy/render_guides.py --archive ../outputs/Nas-Download-1.3.0-manuals.zip
```
