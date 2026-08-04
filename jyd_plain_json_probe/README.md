# 剪映自动化生成项目

开发、调试、扩展和打包请先阅读 [开发者指南](docs/DEVELOPER_GUIDE.md)。普通安装与使用从 [START_HERE.md](START_HERE.md) 开始。本轮数字人账号与任务收件箱改造见 [数字人任务接入变更记录](docs/DIGITAL_HUMAN_INTEGRATION_20260803.md)。

这是一个自包含的剪映草稿采集、素材管理、批量生成和处理机服务项目。源码、前端、母版、素材库以及 `jy-draftc` 解密程序都已经放进本项目目录；构建缓存放在项目外，因此整个 `jyd_plain_json_probe` 文件夹可以直接压缩并迁移。

> 当前渲染链路依赖 Windows 剪映客户端和 Windows UI 自动化。中央网站可以独立部署，但实际导出的 Agent 必须运行在安装了剪映且桌面会话保持可用的 Windows 电脑上。

## 最常用的四个入口

```powershell
# 启动处理机网站（默认 http://127.0.0.1:8010/app）
.\start_processor.ps1 -ProcessingMode standalone

# 启动本机草稿读取/上传工具（后台运行，不需要打开独立页面）
.\start_collector.ps1

# 启动隔离的测试网站与测试采集器（分别在两个 PowerShell 窗口运行）
.\start_test_processor.ps1
.\start_test_collector.ps1
# 测试页面：http://127.0.0.1:8001/app

# 多处理机模式：中央服务与独立处理机 Agent
.\start_processor.ps1 -ExecutionMode agent
# 不带参数会打开图形启动器
.\start_agent.ps1

# 重新生成采集器、中央服务和处理机 Agent 三个 Windows 发布包
.\build_release.ps1

# 当前单处理电脑部署：快速生成服务器和采集器两个包
.\build_deployment.ps1

# 生成包含最新三个发布包、源码、素材库、母版和解密工具的完整项目 ZIP
.\build_portable_project.ps1 -BuildReleases
```

## 本机与公用机切换

- 员工自己的处理端使用默认 `standalone`，访问 `http://127.0.0.1:8010/app`，视频直读本机路径。
- 普通用户账号和数字人任务统一来自数字人网站；本地默认连接 `http://127.0.0.1:8000`。
- 公用机使用独立发布包 `release/JianyingRenderServer-shared-windows-x64.zip`。它默认监听 `0.0.0.0`、继续用公用机自身的一套剪映顺序处理，不启用多 Agent 调度。
- 公用机页面继续显示同一组“本机处理 / 公用处理机”卡片；点击“本机处理”会返回员工电脑的 `http://127.0.0.1:8010/app`。

只生成公用机包：

```powershell
.\build_shared_processor.ps1
```

### 数字人账号与任务收件箱

工作台不再单独维护普通用户账号。本地测试使用本机数字人网站账号：

```text
http://127.0.0.1:8000/admin
```

工作台登录时由数字人网站验证账号并签发短期令牌，不保存用户密码。进入“数字人任务”后，每 15 秒自动拉取当前账号自己的任务：单条文本语音视频可一键导入视频和精确字幕；上传音频或多片段任务提供原始片段下载，人工粗剪后再选择成片。正式部署时在 `data/processor_config.json` 设置 `digital_human_server_url` 为正式数字人网站 HTTPS 地址，服务器现有账号无需迁移。

### 新版工作台与统一项目骨架

新版页面由工作台托管在 `/app/new`，成果库和声音中心分别使用
`/app/new/gallery`、`/app/new/voices`。新版登录页复用数字人网站账号，浏览器只持有
工作台设置的 HTTP-only 会话 Cookie；未登录访问会返回 `/app/new/login`，不会在
前端保存数字人访问令牌。

工作台已提供 `/api/new/projects` 统一项目接口作为后续业务模块的数据基础。一个项目
包含多条脚本行，每行分别保存当前音频、当前画面合成视频、原始视频片段、变体、字幕
绑定和历史素材版本。项目、素材、异步操作和外部批次关联全部绑定数字人账号；普通用户
只能访问自己的项目。

新版输入模块已经接通真实接口：用户可下载固定两列的 Excel 模板，上传 `.xlsx`/`.csv`
脚本，批量上传 JPG/PNG/WEBP，并选择“每图连续复用 N 行”或“逐行循环”策略。任务 ID、
脚本、图片池、逐行当前图片和图片历史版本均由工作台保存，刷新页面可恢复。

声音模块也已经接通真实接口：声音中心读取当前数字人账号的三个 MiniMax 官方音色及
已保存的克隆/融合音色，可先生成制作结果、试听后再保存到音色库；核心工作台的项目
默认音色会一次应用到全部脚本行，各行仍可单独覆盖。显式确认费用后可生成音频、轮询
状态、试听、下载和失败重试。生成结果及 MiniMax
原始时间戳会保存为项目素材版本，流程停在声音审核边界，不会自动创建 RunningHub
画面任务。画面合成、变体和成果库仍按后续模块接入。具体顺序见数字人工作区根目录的
`开发顺序.md`。

自定义音色保存后先以“未激活”状态显示在声音中心，用户明确确认后点击“激活”，由
数字人后端执行第一次正式语音合成并记录为 `ACTIVE`；只有官方音色和已激活自定义音色
能进入核心工作台。自定义音色卡可二次确认后删除；仍被项目选中的音色必须先更换。

向日葵更新已有公用机时，使用 `JianyingRenderServer-update-windows-x64.zip` 覆盖程序文件并保留原 `data` 目录，避免丢失账号、素材和任务数据。

工作台素材和机器设置仍保留独立技术管理员，入口为 `/local-admin/login`；普通员工账号只在数字人网站管理。采集器内部接入密码仍可通过 `JYD_SITE_PASSWORD` 修改，处理机令牌首次启动生成在 `data/web_storage/agent_token.txt`。多处理机部署见 [docs/MULTI_PROCESSOR.md](docs/MULTI_PROCESSOR.md)。

日常操作统一在中央网站 `/app` 完成：上传 MP4、扫描并导入本机剪映草稿、选择素材、提交批量任务以及下载结果都不需要切换页面。本地采集器和剪映 Agent 仍是两个后台进程，分别负责读取本机文件和控制剪映。

本机独立模式下，采集器还负责选择本机视频和导出目录。视频只登记本机路径，不经过网页上传；结果页改为“打开视频 / 打开所在文件夹”。公共素材继续位于 `data/libraries`，个人素材库首次为空，用户可从自己的剪映草稿一键采集到 `data/personal_libraries`。公用处理机模式仍保留原有上传、网页预览和下载流程。

## 正式环境和测试环境

- 正式网站固定使用 `http://127.0.0.1:8010/app`，数据保存在 `data`。
- 测试网站默认使用 `http://127.0.0.1:8001/app`，测试采集器默认使用 `http://127.0.0.1:8766`。
- 测试数据库、母版、素材库副本、上传文件和任务输出都保存在 `runtime/test_environment`，不会修改正式数据。
- 第一次启动测试环境时会从正式 `data/libraries` 和 `data/template_library` 复制初始数据；之后两边独立变化。
- 需要重新用正式数据初始化测试环境时，先停止测试进程，再运行一次 `.\start_test_processor.ps1 -ResetData`，随后正常启动测试采集器。不要同时在正式环境和测试环境提交剪映导出任务，两边仍会控制同一个本机剪映。

处理机启动器第一次使用时填写中央服务地址和令牌、确认剪映草稿目录并选择“一号处理机/二号处理机”；设置会保存在当前 Windows 用户目录，之后启动时不需要重复填写。发布包用户直接双击 `JianyingRenderAgent.exe` 即可打开同一界面。

## 目录用途

```text
apps/                 可运行和可打包的三个应用
  collector/          本机草稿读取/上传服务和 PyInstaller 配置
  processor/          中央网站/API、统一前端和 PyInstaller 配置
  agent/              剪映处理机 Agent 和 PyInstaller 配置
data/                 需要随项目迁移的业务数据
  libraries/          音乐、字体、贴纸、花字、特效、文字模板等素材库
  template_library/   已导入的剪辑母版
  web_storage/        账号、任务、上传记录和生成结果
docs/                 各功能说明和历史开发文档
examples/             渲染任务 JSON 示例
release/              最终交付用 ZIP
runtime/              解密副本、隔离测试环境、测试临时文件和本机运行状态（不进入正式项目 ZIP）
scripts/              环境安装和打包脚本
src/jyd_probe/         核心 Python 源码
tests/                 自动测试
tools/                 素材提取、草稿诊断和旧任务工具
vendor/jy-draftc/      高版本剪映草稿解密程序
```

更详细的文件导航见 [START_HERE.md](START_HERE.md) 和 [docs/PROJECT_LAYOUT.md](docs/PROJECT_LAYOUT.md)。

## 换电脑继续开发

1. 直接压缩整个项目目录，或者运行 `.\build_portable_project.ps1`。
2. 在另一台 Windows 电脑解压。
3. 安装 Python 3.11，然后运行：

```powershell
python -m pip install -r .\requirements.txt
```

4. 使用 `.\start_processor.ps1 -Python "C:\你的Python路径\python.exe"` 启动。
5. 如果要重新生成免 Python 的发布包，先运行：

```powershell
.\scripts\setup_build_environment.ps1 -Python "C:\你的Python路径\python.exe"
.\build_release.ps1
```

构建环境和 PyInstaller 临时产物会放在项目同级的 `.jyd-build-cache`，不会污染项目目录。

## 素材提取示例

所有提取工具都在 `tools\library`。例如按剪映草稿名提取并分类音乐：

```powershell
D:\Myanaconda\python.exe .\tools\library\export_audio_library.py `
  --draft-dir "D:\剪映草稿\JianyingPro Drafts\音乐采集_鸡汤人设" `
  --category-from-draft-name
```

默认输出会进入 `data\libraries` 下对应的素材库。
