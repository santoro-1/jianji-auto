# 剪映自动化生成项目

这是一个自包含的剪映草稿采集、素材管理、批量生成和处理机服务项目。源码、前端、母版、素材库以及 `jy-draftc` 解密程序都已经放进本项目目录；构建缓存放在项目外，因此整个 `jyd_plain_json_probe` 文件夹可以直接压缩并迁移。

> 当前渲染链路依赖 Windows 剪映客户端和 Windows UI 自动化。中央网站可以独立部署，但实际导出的 Agent 必须运行在安装了剪映且桌面会话保持可用的 Windows 电脑上。

## 最常用的四个入口

```powershell
# 启动处理机网站（默认 http://127.0.0.1:8000/app）
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

- 员工自己的处理端使用默认 `standalone`，访问 `http://127.0.0.1:8000/app`，视频直读本机路径。
- 员工工作台直接点击“公用处理机”卡片后，会按 `data/processor_config.json` 的 `auth_server_url` 自动进入公用机，不额外显示按钮，也不在页面展示或填写 IP。
- 公用机使用独立发布包 `release/JianyingRenderServer-shared-windows-x64.zip`。它默认监听 `0.0.0.0`、继续用公用机自身的一套剪映顺序处理，不启用多 Agent 调度。
- 公用机页面继续显示同一组“本机处理 / 公用处理机”卡片；点击“本机处理”会返回员工电脑的 `http://127.0.0.1:8000/app`。

只生成公用机包：

```powershell
.\build_shared_processor.ps1
```

### 临时统一账号中心

内测期固定使用 `http://192.168.11.28:8000` 作为统一账号中心。管理员只在：

```text
http://192.168.11.28:8000/admin
```

创建、停用、删除和重置账号。所有员工本机处理端以及公用机网页都使用这一套账号。本机登录成功后保存的是公用机签发的短期令牌，每次业务请求都会向公用机确认账号仍有效；公用机停用账号后，本机和公用机登录都会立即失效。从本机进入公用机时使用 60 秒内有效且只能消费一次的登录接力码，不需要再次输入密码。公用机离线时其他电脑无法登录或继续下发新操作。

向日葵更新已有公用机时，使用 `JianyingRenderServer-update-windows-x64.zip` 覆盖程序文件并保留原 `data` 目录，避免丢失账号、素材和任务数据。

管理员账号默认为 `admin / admin123`。全新安装先访问 `/admin`，在“内测账号管理”中创建允许登录工作台的普通账号；已有版本会把原 `operator` 账号迁移到新账号库。用户密码只保存加盐哈希。采集器内部接入密码仍可通过 `JYD_SITE_PASSWORD` 修改，处理机令牌首次启动生成在 `data/web_storage/agent_token.txt`。多处理机部署见 [docs/MULTI_PROCESSOR.md](docs/MULTI_PROCESSOR.md)。

日常操作统一在中央网站 `/app` 完成：上传 MP4、扫描并导入本机剪映草稿、选择素材、提交批量任务以及下载结果都不需要切换页面。本地采集器和剪映 Agent 仍是两个后台进程，分别负责读取本机文件和控制剪映。

本机独立模式下，采集器还负责选择本机视频和导出目录。视频只登记本机路径，不经过网页上传；结果页改为“打开视频 / 打开所在文件夹”。公共素材继续位于 `data/libraries`，个人素材库首次为空，用户可从自己的剪映草稿一键采集到 `data/personal_libraries`。公用处理机模式仍保留原有上传、网页预览和下载流程。

## 正式环境和测试环境

- 正式网站固定使用 `http://127.0.0.1:8000/app`，数据保存在 `data`。
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
