# NX2ios — 使用 GitHub Actions 构建 iOS IPA

[English](README.md) | **简体中文**

本项目通过 GitHub Actions 云端 macOS Runner，调用 [NxNative](https://github.com/seedds/nxnative) 构建未签名 iOS IPA。本仓库提供构建工作流和 CI 辅助补丁，不包含游戏文件、密钥或 NxNative 上游源码。

> **注意：** 这是社区维护的构建工作流。构建成功不代表游戏一定能在所有 iPhone 型号或 iOS 版本上正常运行。

## 功能概览

工作流可在 GitHub 的 **Actions** 页面手动启动，并提供两种构建路径：

| 设备选项 | 上游源码 | 说明 |
| --- | --- | --- |
| iPhone 15 or older (BC fallback) | [mianmuhammadse/nxnative](https://github.com/mianmuhammadse/nxnative)，固定提交版本 | BC 纹理兼容路径 |
| iPhone 15 Pro/Pro Max or newer (standard) | [seedds/nxnative](https://github.com/seedds/nxnative)，main 分支 | 标准纹理路径 |

以上选项只代表构建配置，不是设备或游戏兼容性保证。

本仓库额外实现：
- 通过 GitHub Actions Secrets 下载基础游戏、可选更新/DLC 和 `prod.keys`。
- 支持直接使用 NSP/XCI/NSZ/XCZ，或解压包含这些文件的受支持 RAR 压缩包。
- 自动识别基础游戏 Title ID，也允许手动指定 16 位 Title ID。
- 对运行时检出的 NxNative 构建脚本应用 CI Guard 补丁，并监控 Runner 磁盘使用情况。
- Standard/NVN 路径在 Shader Split 后、Metal 编译前暂停，将独立 `RomFS.img` 上传为 `NxNative-ROMFS` Artifact；随后重新运行构建脚本、复用缓存并释放本地 RomFS 镜像。
- 上传未签名 IPA 和可用的构建日志。

BC fallback 使用单独固定版本的上游源码，不传入仅 Standard 版本支持的 `--romfs separate` 参数，也不执行 Standard 专用 RomFS 中转。

## 使用前准备

- GitHub 账户和本仓库。
- Runner 可直接下载的 Google Drive 文件链接。
- 自行合法取得的游戏文件，以及匹配的 `prod.keys`。
- 了解 GitHub Actions Runner 的可用性、运行时长限制和 Artifact 保留期限。

**不要将游戏文件、`prod.keys`、下载链接、访问令牌或其他凭据提交到仓库。**

## 配置步骤

### 1. 添加 Repository Secrets

进入 **Settings → Secrets and variables → Actions → New repository secret**，按名称添加：

| Secret | 必需 | 内容 |
| --- | --- | --- |
| `Game_URL` | 是 | 基础游戏文件或受支持 RAR 压缩包的 Google Drive 分享链接 |
| `Keys_URL` | 是 | `prod.keys` 的 Google Drive 分享链接 |
| `Update_URL` | 否 | 游戏更新文件/压缩包链接 |
| `DLC_URL` | 否 | DLC 文件/压缩包链接 |

名称必须完全一致（包括大小写和下划线）。工作流使用 `gdown` 下载文件；请确保链接无需交互式登录即可访问。没有更新或 DLC 时，无需添加对应 Secret。

### 2. 启动构建

1. 打开仓库的 **Actions** 页面。
2. 选择 **NxNative - Generic IPA Builder**。
3. 点击 **Run workflow**。
4. 选择设备/构建路径。
5. Title ID 保持默认值；只有确认需要覆盖自动识别时才修改。
6. 点击 **Run workflow**。

### 3. 下载产物

在构建运行的 Summary 页面下载：

- `NxNative-IPA-Standard` 或 `NxNative-IPA-BC-Fallback`：未签名 IPA。
- `NxNative-ROMFS`：仅在 Standard/NVN 独立 RomFS 中转流程触发时生成。
- `NxNative-Build-Logs`：构建诊断日志及可用的调查日志。

GitHub 通常将 Artifact 下载为 ZIP。解压 IPA 对应的 ZIP，取出 `.ipa` 文件，再使用常用的 iOS 侧载工具安装。RomFS Artifact 是独立文件，不是 IPA。

## 构建流程

```text
检出所选 NxNative 上游源码
        |
下载游戏包和 prod.keys
        |
预处理游戏包并识别 Title ID
        |
应用 CI Guard 补丁、准备 Shader 工具链
        |
运行 NxNative 构建脚本
        |
        +-- BC fallback：原有构建流程
        |
        +-- Standard/NVN：
                解包、重写并拆分 Shader
                Metal 编译前暂停
                上传 RomFS.img Artifact
                再次运行并复用已有缓存
                释放本地 RomFS 镜像
                编译 Metal Shader、打包 IPA
        |
上传 IPA 和构建日志
```

RomFS 中转不是所有构建都会触发。它仅适用于 Standard 路径实际进入受支持的 NVN + separate-RomFS 流程，并成功生成 handoff 标记和镜像的情况。其他图形路径可能在第一次运行时直接完成 IPA。

## 仓库文件

- `.github/workflows/build.yml`：GitHub Actions 工作流。
- `.github/scripts/nxnative_ci_guard.py`：CI 辅助脚本，负责上游脚本补丁、磁盘清理和磁盘监控。
- `README.md`：英文说明（默认显示）。
- `README.zh-CN.md`：本简体中文说明。

工作流在运行时动态检出 NxNative 上游源码。本仓库不是上游项目的 Fork 或源码镜像。

## 与 Pastebin 参考 YAML 的区别

本仓库工作流包含本项目的 CI 集成：两套上游源码选择、Secrets 下载、游戏包预处理、Title ID 识别、磁盘监控、CI Guard 补丁，以及 Standard/NVN 的 RomFS 中转流程。

**尚未完成与 [Pastebin YAML](https://pastebin.com/XbJt5p3c) 的逐行对比。** 当前无法读取该 Pastebin 的页面或 raw 内容，因此不能可靠判断参考文件中具体哪些步骤、参数或环境变量不同。为避免编造，本节暂不列出未经核实的差异。提供 YAML 原文后即可补充准确的逐项对照表。

## 常见问题

- **下载失败：** 检查 Secret 名称、Google Drive 分享权限和链接是否指向正确文件。
- **无法识别 Title ID：** 检查基础游戏包是否完整；必要时在工作流输入中填写正确的 Title ID。
- **Shader/Metal 构建失败：** 优先查看日志中的第一个实际错误，后续错误可能是连锁反应。
- **没有 RomFS Artifact：** 该产物仅适用于 Standard/NVN + separate-RomFS 路径。检查是否完成 Shader Split，以及是否生成 handoff 标记。
- **没有 IPA Artifact：** 检查 Actions 日志中的第一个失败步骤。
- **IPA 成功但游戏无法运行：** 构建成功不代表游戏兼容。核对游戏版本、更新/DLC、密钥、构建路径和上游兼容性说明。

分享日志寻求帮助前，请删除私有链接、令牌和其他凭据。不要分享密钥文件或游戏转储文件。

## 上游项目

- [seedds/nxnative](https://github.com/seedds/nxnative)：Standard 构建源码。
- [mianmuhammadse/nxnative](https://github.com/mianmuhammadse/nxnative)：BC fallback 固定版本源码。
- [本仓库工作流](.github/workflows/build.yml)。
