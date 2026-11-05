# NX4Actions — 使用 GitHub Actions 构建 iOS IPA

[English](README.md) | **简体中文**

本项目通过 GitHub Actions 云端 macOS Runner，调用 [NxNative](https://github.com/seedds/nxnative) 构建未签名 iOS IPA。它是在这篇 [Reddit 原始指南](https://www.reddit.com/r/NativePortsOniOS/comments/1xh334e/how_to_compile_switch_games_into_native_ios_apps/) 基础上进一步优化的工作流，重点是降低 macOS Runner 的峰值磁盘占用。本仓库提供构建工作流和 CI 辅助补丁，不包含游戏文件、密钥或 NxNative 上游源码。

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

**BC fallback 特别说明：** BC 分支没有进行与 Standard 分支同等的磁盘空间优化，也没有经过本仓库的专项验证。构建可能失败；即使成功生成 IPA，也不代表游戏一定能够启动或正常运行。该分支不对构建结果作保证。

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

GitHub 通常将 Artifact 下载为 ZIP。请分别下载并解压两个产物。**对于 Standard/NVN 的 `--romfs separate` 构建，必须同时取得 IPA 和与之匹配的 `RomFS.img`；只有 IPA 不包含完整游戏数据，不能单独用于游玩。**

安装 IPA 后，需要将镜像放入已安装应用的容器目录：

`<App Container>/Documents/romfs.img`

文件名请使用小写的 `romfs.img`。不要放进 `DmIOS.app`、`Payload` 或 App 内部的 `romfs` 资源目录。上游提供了 [`scripts/push_romfs.sh`](https://github.com/seedds/nxnative/blob/main/scripts/push_romfs.sh)，用于将镜像复制到应用的 Documents 目录；具体部署方式可参考上游的 [packing/deployment 文档](https://github.com/seedds/nxnative/blob/main/docs/development.md)。运行该脚本时需要设备 UDID、应用 Bundle ID 和下载的镜像文件。镜像必须与构建 IPA 时使用的游戏及版本匹配；游戏版本或提取结果变化后，需要重新传输对应镜像。

`NxNative-ROMFS` 是独立的游戏数据镜像，不是可安装应用。

## 磁盘空间优化（本仓库的核心改动）

本仓库最主要的优化目标，是降低 GitHub 云端 macOS Runner 的峰值磁盘占用，尤其是 Metal Shader 编译阶段的空间压力。当前工作流主要采用以下措施：

1. **解压/准备完成后清理下载源文件和临时目录。** 游戏包已准备到构建输入目录后，删除下载阶段的 `.download` 文件副本和临时 RAR 解压目录；NxNative 后续仍需要使用的游戏包会保留。
2. **Shader Split 完成后先上传 `RomFS.img`。** 在受支持的 Standard/NVN + separate-RomFS 路径中，构建脚本在 Shader Split 成功后、Metal 编译前暂停。趁 RomFS 镜像仍在 Runner 上，将它上传为 `NxNative-ROMFS` Artifact。
3. **Metal 编译前删除 Runner 本地的 `RomFS.img`。** Artifact 上传完成后，工作流重新进入缓存构建流程，并在 Metal 编译前删除本地 RomFS 镜像，尽可能把磁盘空间留给 Xcode/Metal 编译。
4. **使用 `--romfs separate` 构建 IPA。** 因为本地 RomFS 镜像已被释放，IPA 不再内嵌完整游戏 RomFS。游戏数据单独交付，之后必须放入应用容器的 `Documents/romfs.img`。

### 实测案例：最终幻想共鸣（亚洲版）

这套磁盘优化主要是围绕**最终幻想共鸣亚洲版**进行设计和调整的。该游戏的一次实测构建结果如下：

| 项目 | 实测结果 |
| --- | ---: |
| 原始 XCI | **8.57 GB** |
| 独立 `RomFS.img` | **8.35 GB** |
| 最终未签名 IPA | **6.58 GB** |
| 原始 XCI 和 Runner 本地 `RomFS.img` 均释放后，Metal 编译峰值阶段剩余磁盘空间 | **430 MB** |

以上是该游戏该次构建的实测数据，不代表所有游戏的固定结果，也不是 Runner 容量保证。该案例中 IPA 与 RomFS.img 的合计容量明显大于原始 XCI，可能与该游戏自身的数据组织、解包结果或构建产物特性有关，不能据此推断其他游戏也会有相同的体积比例。Metal 编译峰值时仅剩 430 MB，也说明该游戏对 Runner 磁盘空间仍然非常紧张。

### 新增 Python 脚本：`.github/scripts/nxnative_ci_guard.py`

这个 Python 脚本不是游戏补丁，也不负责修改游戏内容。它是本仓库的 CI 磁盘管理与构建流程协调工具，主要职责包括：

- **构建前清理：** 只清理 Runner 临时目录中由本工作流管理的旧 `GameFiles`、`nxnative` 目录和磁盘监控文件；不会擅自删除共享的 Homebrew、Xcode 或 Runner 全局缓存。
- **给上游构建脚本打补丁：** 调整 Shader 构建过程中的清理逻辑，确保所有 Shader 收尾任务完成前不会提前删除仍在使用的中间文件，避免并发清理竞争。
- **协调 RomFS 两阶段构建：** 给 Standard 上游构建脚本增加 Shader Split 后暂停、准备 Artifact 上传文件，以及第二次运行时在 Metal 编译前释放本地 RomFS 镜像的逻辑。
- **保证 separate-RomFS 打包流程可继续：** 当镜像已按计划释放且启用 separate 模式时，允许 `build_ipa.sh` 跳过 RomFS 镜像标记检查；镜像仍存在时则保留正常检查。
- **磁盘监控和报告：** 定期记录剩余磁盘空间、文件系统使用情况、构建进度和关键构建目录大小，结束时输出报告，便于定位空间消耗最大的阶段。

工作流会调用该脚本执行构建前清理、上游脚本补丁、启动/停止磁盘监控和输出报告。它负责协调本仓库的磁盘优化措施，但不代替游戏解包，也不执行 Metal 编译。

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
