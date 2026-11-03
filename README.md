# 如何在没有 Mac 的情况下使用 GitHub Actions 和 nxnative 构建 iOS IPA

> 初学者指南：使用 Google Drive 托管游戏文件，并通过 GitHub Actions
> 的云端 macOS 运行器构建 IPA。
> 本文根据用户提供的指南整理(https://www.reddit.com/r/NativePortsOniOS/comments/1xh334e/how_to_compile_switch_games_into_native_ios_apps/)

## 目录

1.  [可与 nxnative 配合使用的游戏](#1-可与-nxnative-配合使用的游戏)
2.  [准备工作](#2-准备工作)
3.  [将文件上传到 Google Drive](#3-将文件上传到-google-drive)
4.  [创建 GitHub 账户](#4-创建-github-账户)
5.  [创建空白 GitHub 仓库](#5-创建空白-github-仓库)
6.  [将 Google Drive 链接添加为 GitHub
    Secrets](#6-将-google-drive-链接添加为-github-secrets)
7.  [下载通用 Workflow YAML](#7-下载通用-workflow-yaml)
8.  [将 Workflow 添加到仓库](#8-将-workflow-添加到仓库)
9.  [配置文件链接 Secrets](#9-配置文件链接-secrets)
10. [运行构建](#10-运行构建)
11. [查看进度并排查错误](#11-查看进度并排查错误)
12. [下载构建完成的 IPA](#12-下载构建完成的-ipa)
13. [最终检查清单](#13-最终检查清单)

------------------------------------------------------------------------

How to compile Switch games into native iOS apps without a Mac.

This beginner-friendly guide explains how to use GitHub Actions to build
an iOS IPA with nxnative without needing a Mac. You will use Google
Drive to host your game files and GitHub to run the build on a cloud
macOS machine.

> 这份适合初学者的指南解释了如何使用 GitHub Actions 在不使用 Mac
> 的情况下，用 nxnative 构建 iOS 的 IPA。你会用 Google Drive
> 托管游戏文件，GitHub 在云端 macOS 机器上运行版本。

You do not need to know how to code, and you do not need to fork either
nxnative source repository. You will create your own GitHub repository
containing the build workflow.

> 你不需要懂编程，也不需要分支任何一个 nxnative
> 源代码仓库。你将创建一个包含构建工作流程的 GitHub 仓库。

## 1. 可与 nxnative 配合使用的游戏

The following combined list comes from the game lists in the two
nxnative repositories. Compatibility varies by iPhone model, game
version, and build configuration.

> 以下合并列表来自两个 nxnative 仓库的游戏列表。兼容性因 iPhone
> 型号、游戏版本和构建配置而异。

13 Sentinels: Aegis Rim 13哨兵：护盾边缘

Absolum 阿布索鲁姆

Ace Attorney Investigations Collection

> 逆转裁判调查合集

Advance Wars 1+2: Re-Boot Camp

> 高级战争1+2：重启训练营

AI: The Somnium Files AI：梦晶档案

AI: The Somnium Files -- nirvanA Initiative

> AI：Somnium Files------nirvanA 倡议

Animal Crossing: New Horizons

> 动物森友会：新地平线

Animal Well 动物井

Astral Chain 星链

Balatro 巴拉特罗

BALL x PIT 球 x 坑

Bayonetta 猎天使魔女

Bayonetta 2 猎天使魔女2

Bayonetta 3 猎天使魔女3

Big Brain Academy: Brain vs. Brain

> 大脑学院：大脑对决

Blasphemous 亵渎

Blasphemous 2 亵渎2

Brain Memory Training Academy

> 脑记忆训练学院

Captain Toad: Treasure Tracker

> 蟾蜍队长：宝藏追踪者

Catherine: Full Body 凯瑟琳：全身

Celeste 塞莱斯特

Cuphead 杯头

DARK SOULS: REMASTERED 黑暗之魂：重制版

Digimon Story Cyber Sleuth: Complete Edition

> 数码宝贝物语 网络侦探：完整版

Donkey Kong Country Returns HD

> 大金刚乡村归来高清版

Donkey Kong Country: Tropical Freeze

> 大金刚乡村：热带冰冻

DRAGON QUEST VII Reimagined

> 勇者斗恶龙 VII 再构想版

DRAGON QUEST XI S: Echoes of an Elusive Age -- Definitive Edition

> 勇者斗恶龙 XI S：难以捉摸的时代回声 -- 终极版

FINAL FANTASY CRYSTAL CHRONICLES Remastered Edition

> 最终幻想水晶编年史 重制版

FINAL FANTASY RESONANCE 最终幻想共鸣

FINAL FANTASY TACTICS: The Ivalice Chronicles

> 最终幻想战略版：伊瓦利斯编年史

Fire Emblem Engage 火焰纹章：启程

Fire Emblem: Three Houses

> 火焰纹章：风花雪花

Ghost Trick: Phantom Detective

> 鬼怪诡计：幻影侦探

The Great Ace Attorney Chronicles

> 伟大的逆转裁判编年史

Hades 哈迪斯

Hades II 哈迪斯 II

Hollow Knight: Silksong 空洞骑士：丝歌

Hyrule Warriors: Age of Calamity

> 《海拉鲁无双：灾厄纪元》

Kirby and the Forgotten Land

> 卡比与被遗忘之地

Luigi's Mansion 3 路易吉洋楼3

Mario + Rabbids Sparks of Hope

> 马里奥+兔子 希望火花

Mario Kart 8 Deluxe 马里奥赛车8豪华版

Mario vs. Donkey Kong 马里奥大战大金刚

Metroid Dread 银河战士：恐惧

Monster Hunter Rise 怪物猎人崛起

Monster Train 2 怪兽列车2

NieR:Automata The End of YoRHa Edition

> 尼尔：自动纪元：YoRHa 终结版

OCTOPATH TRAVELER 八方旅人

Octopath Traveler 0 八方旅人0

Octopath Traveler II 八方旅人 II

Paper Mario: The Thousand-Year Door

> 纸片马里奥：千年之门

Patrick's Parabox 帕特里克伞兵

Persona 5 Royal 女神异闻录5 皇家版

Pikmin 4 皮克敏4

Pokémon Brilliant Diamond

> 宝可梦 璀璨钻石

Pokémon Legends: Z-A 宝可梦传说：Z-A

Pokémon Scarlet 宝可梦猩红

Pokémon Shield 宝可梦盾牌

Pokémon Sword 宝可梦 剑

Portal 门户

Raging Loop 狂暴循环

Return of the Obra Dinn

> 奥布拉丁的回归

Rhythm Heaven Groove 节奏天堂律动

ROMANCE OF THE THREE KINGDOMS 8 REMAKE

> 三国演义8 重制版

Sea of Stars 星海

SHIN MEGAMI TENSEI V: Vengeance

> 真·女神转生 V：复仇

Silver Pines 银松

Stardew Valley 星露谷物语

STEINS;GATE RE:BOOT 《命运石之门》;门 重启

Super Mario 3D World + Bowser's Fury

> 超级马里奥 3D 世界+库巴之怒

Super Mario Bros. Wonder 超级马里奥兄弟奇迹

Super Mario Galaxy 超级马里奥银河

Super Mario Galaxy 2 超级马里奥银河2

Super Mario Odyssey 超级马里奥奥德赛

Super Smash Bros. Ultimate

> 任天堂明星大乱斗特别版

Taiko Risshiden V DX 太鼓立志传 V DX

The Legend of Zelda: Breath of the Wild

> 塞尔达传说：旷野之息

The Legend of Zelda: Echoes of Wisdom

> 塞尔达传说：智慧回声

The Legend of Zelda: Link's Awakening

> 塞尔达传说：林克的觉醒

The Legend of Zelda: Tears of the Kingdom

> 塞尔达传说：王国之泪

Unicorn Overlord 独角兽霸主

Xenoblade Chronicles 2 异度神剑2

Xenoblade Chronicles 3 异度神剑3

Yoshi's Crafted World 耀西的手工世界

WARNING: Any game not on this list is not guaranteed to work. Even games
on the list may fail to build or run correctly on your particular
device. This is a list of reported titles, not a guarantee that every
game is compatible.

> 警告：
> 列表中不存在的游戏并不保证能正常使用。即使是列表中的游戏，也可能无法在你的设备上正常构建或运行。这是报告标题列表，并不保证所有游戏都兼容。

Use game dumps and keys you are legally entitled to use.

> 使用你依法有权使用的游戏转储和密钥。

3.  What you need 2. 你需要什么

Before starting, gather these items:

> 开始前，收集以下物品：

A GitHub account: https://github.com/

> 一个 GitHub 账号：https://github.com/

A Google account with Google Drive: https://drive.google.com/

> 一个带有 Google Drive 的 Google 账户：https://drive.google.com/

A legally obtained Nintendo Switch game dump, normally an .nsp or .xci
file, or an archive containing one.

> 合法获得的任天堂 Switch 游戏转储，通常是.nsp 或.xci
> 文件，或包含此类的档案。

The matching prod.keys file.

> 匹配的 prod.keys 文件。

The matching game update, if applicable.

> 如果适用，匹配游戏更新。

The matching DLC files, if applicable.

> 如果适用，是匹配的 DLC 文件。

The universal nxnative workflow YAML: https://pastebin.com/XbJt5p3c

> 通用的 nxnative 工作流程 YAML：https://pastebin.com/XbJt5p3c

You do not need a Mac. GitHub Actions provides the cloud build machine.

> 你不需要 Mac。GitHub Actions 提供云构建机器。

Keep your keys private. Do not post them publicly or share them with
other people. Anyone with access to your keys may be able to access
protected game content.

> 保持钥匙私密。
> 请勿公开发布或与他人分享。任何拥有你密钥的人都可能访问受保护的游戏内容。

## 3. 将文件上传到 Google Drive

Google Drive will host the files so the GitHub workflow can download
them during the build.

> Google Drive 会托管这些文件，GitHub 工作流程可以在构建过程中下载。

Step 1: Upload the files

> 步骤1：上传文件

Open https://drive.google.com/ and sign in.

> 打开 https://drive.google.com/ 并签到。

Click New. 点击 "新"。

Choose File upload.

> 选择上传文件 。

Select your base game file and wait for it to finish uploading.

> 选择你的基础游戏文件，等待上传完成。

Repeat for your prod.keys file.

> 对你的 prod.keys 文件重复这个过程。

Upload the game update and DLC files if you have them and intend to use
them.

> 如果你有游戏更新和 DLC 文件并打算使用，请上传它们。

Keep each file separate so you can identify which link belongs to which
file.

> 保持每个文件独立，这样你才能识别哪个链接属于哪个文件。

Step 2: Set sharing permissions

> 步骤2：设置共享权限

Repeat these steps for each file you want the workflow to download:

> 对每个你想下载的文件重复以下步骤：

Find the file in Google Drive.

> 在 Google Drive 找到文件。

Right-click it, or tap its three-dot menu.

> 右键点击，或者点击它的三点菜单。

Select Share or Manage access.

> 选择共享或管理访问权限 。

Under General access, change Restricted to Anyone with the link.

> 在 "一般访问"中，更改为"限制 "仅限持有该链接的任何人 。

Leave the permission set to Viewer.

> 权限设置留给查看器 。

Click Copy link.

> 点击复制链接 。

Click Done. 点击完成 。

Repeat for the base game, keys, update, and DLC files as applicable.

> 对基础游戏、密钥、更新和 DLC 文件（视情况）重复操作。

Google's sharing instructions:
https://support.google.com/drive/answer/2494822

> 谷歌的分享说明：https://support.google.com/drive/answer/2494822

Privacy warning: Anyone with these links may be able to access the
files. Do not post the links publicly. After the build, consider
changing the files back to Restricted.

> 隐私警告：
> 任何拥有这些链接的人都可能访问这些文件。请勿公开发布链接。构建完成后，考虑把文件改回受限。

## 4. 创建 GitHub 账户

If you already have a GitHub account, skip to Section 5.

> 如果你已经有 GitHub 账户，请跳到第 5 节。

Open https://github.com/.

> 开门 https://github.com/。

Click Sign up. 点击注册 。

Enter your email address and create a password.

> 输入您的电子邮件地址并创建密码。

Complete the verification steps.

> 完成验证步骤。

Verify your email if requested.

> 如有要求，请核实您的邮箱。

Sign in to GitHub. 登录 GitHub。

You do not need a paid plan just to try this workflow, although usage
limits and runner availability can vary.

> 你不需要付费套餐来尝试这种工作流程，尽管使用限制和运行者的可用性可能有所不同。

## 5. 创建空白 GitHub 仓库

A repository is where you will store the workflow file and its private
settings.

> 仓库是你存放工作流程文件及其私有设置的地方。

While signed in, open https://github.com/new.

> 登录时，打开 https://github.com/new。

Enter a repository name, such as nxnative-ipa-builder.

> 输入一个仓库名称，比如 nxnative-ipa-builder。

Choose Private or Public. Private is a sensible default for a personal
build project.

> 选择私人或公共。 私密是个人构建项目的合理默认选择。

You can leave the description blank.

> 你可以把描述留空。

Do not upload game files or keys to the repository.

> 不要将游戏文件或密钥上传到仓库。

Click Create repository.

> 点击创建仓库 。

That's it. You do not need to fork either nxnative source repository.
The workflow checks out the selected source repository automatically
when it runs.

> 就这样。你不需要分支任何一个 nxnative
> 源代码仓库。该工作流运行时会自动检查所选源仓库。

## 6. 将 Google Drive 链接添加为 GitHub Secrets

GitHub secrets store the links privately so you don't have to write them
directly into the workflow.

> GitHub 秘密会私密存储链接，这样你就不必直接写入工作流程。

Open your new repository.

> 打开你的新仓库。

Click Settings. 点击设置 。

In the sidebar, find Secrets and variables.

> 在侧边栏，找到 "秘密"和"变量 "。

Click Actions. 点击操作 。

Under Repository secrets, click New repository secret.

> 在"存储库秘密"中，点击 "新存储库秘密"。

Enter the secret name exactly as shown below.

> 输入密码，完全按照下面所示。

Paste the matching Google Drive sharing link into the Secret field.

> 将匹配的 Google Drive 分享链接粘贴到秘密字段中。

Click Add secret.

> 点击添加秘密 。

Required secrets 必需秘密

Secret name 秘密名称

What to put in it

> 放什么

Game_URL

Google Drive sharing link for the base game

> 基础游戏的 Google Drive 分享链接

Keys_URL

Google Drive sharing link for your prod.keys file

> Google Drive 分享你的 prod.keys 文件链接

Optional secrets 可选秘密

Secret name 秘密名称

What to put in it

> 放什么

Update_URL

Google Drive sharing link for the game update

> 游戏更新的 Google Drive 分享链接

DLC_URL

Google Drive sharing link for the DLC

> DLC 的 Google Drive 分享链接

Only add the update and DLC secrets if you have the corresponding files
and want to use them.

> 只有当你有对应文件并想使用时，才添加更新和 DLC 秘密。

Important: The names must match exactly, including capitalization and
underscores. Game_URL is not the same as game_url.

> 重要提示： 名字必须完全匹配，包括大小写和下划线。Game_URL 和 game_url
> 不一样。

Do not paste the contents of your keys file into a secret. The workflow
expects a link from which it can download the file.

> 不要把密钥文件的内容粘贴到秘密文件里。工作流程需要一个链接来下载文件。

GitHub's instructions for repository secrets:
https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets

> GitHub
> 关于仓库秘密的说明：https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets

## 7. 下载通用 Workflow YAML

The YAML file contains the instructions that tell GitHub how to build
the IPA.

> YAML 文件包含了告诉 GitHub 如何构建 IPA 的指令。

Open this link: https://pastebin.com/XbJt5p3c

> 打开这个链接：https://pastebin.com/XbJt5p3c

Find the full YAML text.

> 查找完整的 YAML 文本。

Copy the entire file, from the first line to the last line.

> 从第一行复制到最后一行完整文件。

Keep it ready to paste into GitHub.

> 准备好粘贴到 GitHub。

Do not paste the YAML into Google Drive, the repository's README, or a
terminal. It must be saved as a GitHub Actions workflow.

> 不要将 YAML 粘贴到 Google Drive、仓库的 README 或终端中。它必须保存为
> GitHub Actions 的工作流程。

## 8. 将 Workflow 添加到仓库

Return to your GitHub repository's main page.

> 返回你的 GitHub 仓库主页。

Click Add file. 点击添加文件 。

Select Create new file.

> 选择创建新文件 。

In the filename field, enter this exact path:

> 在文件名字段中输入这条精确路径：

`.github/workflows/build.yml`

GitHub will create the required folders automatically.

> GitHub 会自动创建所需的文件夹。

Click inside the large editor area.

> 点击大编辑区内。

Paste the entire YAML you copied from Pastebin.

> 粘贴你从 Pastebin 复制的整个 YAML 文件。

Check that you included the beginning and end of the file.

> 检查你是否包含了文件的开头和结尾。

Click Commit changes.

> 点击提交更改 。

If prompted, confirm the commit to your default branch, normally main.

> 如果被提示，确认提交到你的默认分支，通常是主分支。

You should now have a workflow file at .github/workflows/build.yml.

> 你现在应该会有一个工作流文件，地址是 .github/workflows/build.yml。

GitHub requires workflow files to be inside .github/workflows/. A
manually triggered workflow must be available on the default branch to
be run from the Actions interface.

> GitHub 要求工作流文件必须在 .github/workflows/
> 内部。默认分支必须有手动触发的工作流程，才能从动作界面运行。

## 9. 配置文件链接 Secrets

Now connect the files you uploaded to the workflow.

> 现在把你上传的文件连接到工作流程。

For example: 例如：

Game_URL gets the sharing link for your base game file.

> Game_URL 会获得你基础游戏文件的共享链接。

Keys_URL gets the sharing link for your prod.keys file.

> Keys_URL 会获得你 prod.keys 文件的共享链接。

Update_URL gets the update file's sharing link, if applicable.

> 如果适用，Update_URL 会获得更新文件的共享链接。

DLC_URL gets the DLC file's sharing link, if applicable.

> 如果适用，DLC_URL 会获得 DLC 文件的共享链接。

To create or change a secret:

> 创建或更改秘密：

Open Settings → Secrets and variables → Actions.

> 打开设置→秘密和变量→动作 。

Select the secret you need to create or update.

> 选择您需要创建或更新的秘密。

Paste the appropriate Google Drive link.

> 粘贴相应的 Google Drive 链接。

Save it. 省省吧。

GitHub won't show you the full value of an existing secret after saving
it, so double-check the link before you click Add secret.

> GitHub
> 保存后不会显示现有秘密的全部数值，所以点击添加秘密前请仔细检查链接。

### What if the Google Drive link doesn't work?

如果 Google Drive 链接失效怎么办？

The workflow needs to download the actual file, not a page that asks you
to sign in. Make sure:

> 工作流程需要下载实际的文件，而不是让你登录的页面。确保：

The sharing permission is set to Anyone with the link --- Viewer.

> 分享权限设置为 "任何持有链接的人------查看者"。

You copied the link for the correct file.

> 你复制了正确的文件链接。

The file is fully uploaded.

> 文件已完全上传。

Google Drive isn't blocking the download or requiring an extra
confirmation.

> Google Drive 并没有阻止下载，也没有要求额外的确认。

10. Run the build 10. 运行构建

Open your repository. 打开你的仓库。

Click the Actions tab.

> 点击 "操作"标签。

Select the workflow from the left sidebar.

> 从左侧边栏选择工作流程。

Click Run workflow.

> 点击运行工作流程 。

Select the branch containing your workflow, usually main.

> 选择包含你工作流程的分支，通常是主分支。

Choose the device option.

> 选择设备选项。

The workflow provides these intended build paths:

> 该工作流程提供了以下预期的构建路径：

iPhone 15 or older (BC fallback): selects the pinned BC-texture fallback
build.

> iPhone 15 及以上版本（BC 备选）： 选择钉顶的 BC 纹理备用构建。

iPhone 15 Pro/Pro Max or newer (standard): selects the standard upstream
build.

> iPhone 15 Pro/Pro Max 或更新版本（标准）： 选择标准上游配置。

These are build-path choices, not guarantees that every game will work
on every device. If you aren't sure which option to choose, consult the
compatibility information for your device and build.

> 这些是构建路径的选择，并不保证每款游戏都能在所有设备上运行。如果不确定该选哪个选项，可以查阅你设备和组装机的兼容性信息。

If the workflow asks for a profile ID override, leave it blank or at its
default unless you know you need to override automatic detection.

> 如果工作流程要求覆盖配置文件
> ID，除非你知道需要覆盖自动检测，否则保持空白或默认状态。

Click Run workflow to start the build.

> 点击运行工作流程开始构建。

GitHub will allocate a runner and execute the workflow. The build can
take some time while dependencies are installed, files are downloaded,
and the game is compiled.

> GitHub
> 会分配一个运行者并执行工作流程。构建过程中可能需要一些时间，比如安装依赖、下载文件和编译游戏。

## 11. 查看进度并排查错误

After starting the workflow:

> 开始工作流程后：

Stay on the Actions tab.

> 请继续查看操作标签。

Click the new workflow run.

> 点击新的工作流程运行。

Click the job to open its detailed log.

> 点击该职位以查看详细日志。

Watch each step as it runs.

> 每一步都要注意它运行的过程。

A green check mark means the workflow completed successfully. A red X
means something failed.

> 绿色勾选表示工作流程已成功完成。红色 X 表示某处失败。

Common problems 常见问题

A. Google Drive download fails

> 答：Google Drive 下载失败

Possible causes: 可能原因：

The file is still Restricted.

> 该文件仍然是受限状态。

The URL was copied incorrectly.

> URL 被错误复制了。

Google Drive requires a confirmation that the workflow cannot handle.

> Google 云端硬盘需要确认该工作流程无法处理。

The file is too large or Google Drive has temporarily limited downloads.

> 文件太大，或者 Google Drive 暂时限制了下载。

Check the sharing settings and confirm that the secret points to the
correct file.

> 检查共享设置，确认密钥指向正确的文件。

B. The keys file is missing or invalid

> B.钥匙文件缺失或无效

Check that Keys_URL points to the actual keys file and that the file is
valid and compatible with your game dump.

> 检查 Keys_URL
> 是否指向实际的钥匙文件，并且该文件是否有效且与你的游戏转储兼容。

C. The game file cannot be detected

> C. 无法检测到游戏文件

Check that the game dump downloaded completely and is in a supported
format. If the workflow cannot identify the title ID, the log may
contain a detection error.

> 检查游戏转储是否完整下载且格式支持。如果工作流程无法识别标题
> ID，日志中可能包含检测错误。

D. The build fails while installing dependencies or compiling

> D. 构建在安装依赖或编译过程中失败

Read the first meaningful error in the log. Later errors may simply be
consequences of the first failure. The standard upstream source and
pinned fallback source may also change or behave differently.

> 读日志中的第一个有意义的错误。后续错误可能仅仅是第一次失败的结果。标准的上游源和固定的备用源也可能发生变化或行为不同。

E. The build succeeds, but the game doesn't run properly

> E.这个构建成功了，但游戏运行不正常

A successful build does not guarantee compatibility. Check whether the
game appears in the reported game list, whether you chose the intended
device option, and whether the game dump, update, DLC, and keys match.

> 成功的构建并不保证兼容性。检查游戏是否出现在报告的游戏列表中，是否选择了目标设备选项，以及游戏转储、更新、DLC
> 和密钥是否匹配。

### Use an AI assistant to diagnose errors

### 使用 AI 助手诊断错误

If you're stuck, copy the relevant error message and surrounding log
lines into an AI assistant.

> 如果卡住了，可以把相关的错误信息和周围的日志条复制到 AI 助手里。

You can use this prompt:

> 你可以使用这个提示：

I'm trying to build an iOS IPA using nxnative and a GitHub Actions
workflow. The build failed at the following step. Please identify the
first actual error, explain what caused it, and give me step-by-step
instructions to fix it. Don't assume the build succeeded if the logs say
otherwise.

> 我正在尝试用 nxnative 和 GitHub Actions 工作流程构建一个 iOS 的
> IPA。但构建在下一步失败了。请指出第一个实际错误，解释原因，并给我逐步的修复说明。如果日志显示不是这样，也不要假设构建成功了。

\[Paste the relevant log lines here.\]

> \[将相关日志贴到这里。\]

Include the failed step's name and the device option you selected.

> 请包含失败步骤的名称和你选择的设备选项。

Remove sensitive information before sharing logs. Check for Google Drive
URLs, tokens, private repository information, and other credentials.
Never upload your keys file or game dump to an AI assistant just to
diagnose an error. Usually, the error message and nearby log lines are
enough.

> 在分享日志前，先删除敏感信息。 检查 Google
> 云端硬盘的网址、令牌、私有仓库信息及其他凭证。千万不要为了诊断错误而把钥匙文件或游戏转储上传给
> AI 助手。通常，错误信息和附近的日志就足够了。

## 12. 下载构建完成的 IPA

Once the workflow completes successfully:

> 一旦工作流程成功完成：

Open the completed run under the Actions tab.

> 在操作标签下打开已完成的游戏。

Scroll down to the Artifacts section on the run summary page.

> 往下滚动到游戏总结页的神器部分。

Find the IPA artifact. Its name may identify the build type, such as
BC-Fallback or Standard.

> 找到那个 IPA 文物。其名称可能指代构建类型，如 BC-Fallback 或
> Standard。

Click the artifact name to download it.

> 点击文物名称下载。

GitHub will normally download the artifact as a ZIP file.

> GitHub 通常会以 ZIP 文件形式下载该文件。

Open the ZIP and extract the .ipa file.

> 打开 ZIP，解压.ipa 文件。

You now have the IPA produced by the workflow. You can proceed with your
usual iOS sideloading method.

> 你现在有了由工作流程产生的国际音标。你可以继续用你平时的 iOS
> 侧载方式。

If there is no IPA artifact, check the workflow log for the first failed
step. A build that fails before the upload step will not produce the
expected artifact.

> 如果没有国际音标伪影，检查第一个失败步骤的工作流程日志。如果在上传步骤前失败的构建不会产生预期的伪影。

Final checklist 最终检查清单

-   [ ] Game dump and matching keys prepared.
-   [ ] 游戏导出和匹配的密钥已准备好。
-   [ ] Update and DLC prepared, if applicable.
-   [ ] 如果有更新，DLC 已准备好。
-   [ ] Files uploaded to Google Drive.
-   [ ] 文件已上传到 Google Drive。
-   [ ] Required files shared with the appropriate link access.
-   [ ] 必须通过相应链接访问共享文件。
-   [ ] GitHub account and repository created.
-   [ ] GitHub 账户和仓库已创建。
-   [ ] Required secrets added with exact names.
-   [ ] 必须添加带有确切姓名的秘密。
-   [ ] Universal YAML saved as .github/workflows/build.yml.
-   [ ] 通用 YAML 保存为.github/workflows/build.yml。
-   [ ] Workflow committed to the default branch.
-   [ ] 工作流程已提交到默认分支。
-   [ ] Correct device option selected.
-   [ ] 已选中正确的设备选项。
-   [ ] Build completed successfully.
-   [ ] 组装顺利完成。
-   [ ] IPA artifact downloaded and extracted.
-   [ ] IPA 伪影已下载并解压。 That's it! Create your repository once,
    add your own secrets, and use the workflow whenever you want to
    build another compatible game.

> 就是这样！ 创建一个仓库，添加自己的秘密，想做兼容游戏时用这个流程。

Remember that this is a community workflow, not a guarantee that every
game will build or run correctly on every device. If a build fails, save
the relevant log lines and troubleshoot the first error before trying
again.

> 请记住，这是社区工作流程，并不保证每款游戏都能在所有设备上正确构建或运行。如果构建失败，保存相关日志并排查第一个错误后再尝试。
