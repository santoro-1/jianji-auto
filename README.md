# 影变批剪工作台（Jianji Auto）

这是一个面向 Windows 剪映专业版的批量视频生产工作台。它把脚本、人物图、数字人音视频、字幕、BGM、语义贴图/空镜、封面和视频变体组织成可追踪的项目，并通过剪映草稿 JSON 与 Windows UI 自动化完成最终 MP4 导出。

> 主程序、开发文档和测试位于 [`jyd_plain_json_probe`](jyd_plain_json_probe/)；仓库根目录的其他素材目录主要用于历史素材整理与迁移。开始开发前，请先进入主项目目录。

## 主要能力

- 从 Excel/CSV 批量导入脚本，并按任务 ID、文章类型和账号管理项目。
- 批量分配人物图、音色、语速、字幕样式和 BGM，保留每次生成的历史版本。
- 复用数字人网站账号，调用 MiniMax 生成声音，并通过 RunningHub 与 SeedVR2 获取数字人清晰片段。
- 根据 MiniMax 原始时间戳和本机 FunASR 生成精确单行字幕。
- 使用统一内容分析结果完成字幕断句、音乐匹配、语义贴图和相关空镜编排。
- 生成剪映可编辑草稿，按需调用剪映导出普通成片和批量视频变体。
- 管理公共素材、个人素材、草稿模板、任务状态、运行日志和最终成果。
- 支持本机嵌入执行，也支持中央 Processor 调度一台或多台 Windows Render Agent。

## 系统组成

```text
浏览器工作台
    |
    v
Processor Web/API（FastAPI，默认 8010）
    |-- 项目、素材、字幕、BGM、视觉配方和任务状态
    |-- embedded：本机顺序渲染
    `-- agent：把任务交给 Windows Render Agent
                         |
                         v
                    剪映专业版导出 MP4

Local Collector
    `-- 扫描本机草稿、选择文件、采集素材和导入模板
```

数字人、声音和内容分析能力由配套云端项目提供：

- [RunningHub 数字人网站 / rh-api](https://github.com/santoro-1/rh-api)

工作台不会在浏览器中保存数字人服务访问令牌，也不会直接向浏览器下发 MiniMax、RunningHub 或内容分析服务的密钥。

## 环境要求

- Windows 10 或 Windows 11
- Python 3.11
- PowerShell 5.1 或更高版本
- 已安装并可正常导出的兼容版剪映专业版
- FFmpeg / FFprobe
- 主项目内存在 `vendor/jy-draftc/jy-draftc.exe`

真正的剪映导出依赖可交互的 Windows 桌面会话。Web 服务可以集中运行，但执行导出的电脑必须安装剪映，且运行期间不能锁屏。

## 快速开始

```powershell
git clone https://github.com/santoro-1/jianji-auto.git
cd .\jianji-auto\jyd_plain_json_probe

python -m pip install -r .\requirements.txt

# 启动本机工作台
.\start_processor.ps1 `
  -Python "C:\Path\To\Python311\python.exe" `
  -ProcessingMode standalone `
  -ExecutionMode embedded
```

启动后访问：

- 新版工作台：`http://127.0.0.1:8010/app/new`
- 旧版工作台：`http://127.0.0.1:8010/app`
- API 文档：`http://127.0.0.1:8010/docs`

如果需要扫描本机剪映草稿、选择本机文件或采集素材，再启动 Collector：

```powershell
.\start_collector.ps1
```

普通用户账号来自数字人网站。源码联调默认可连接本机数字人服务 `http://127.0.0.1:8000`；正式工作台应在 `data/processor_config.json` 中配置正式 HTTPS 地址。

## 测试

在主项目目录执行：

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

隔离测试工作台与正式数据分开：

```powershell
.\start_test_processor.ps1
.\start_test_collector.ps1
```

默认测试页面为 `http://127.0.0.1:8001/app`。测试环境和正式环境仍可能控制同一个剪映客户端，不要同时提交真实导出任务。

## 构建与更新

首次构建前准备独立打包环境：

```powershell
.\scripts\setup_build_environment.ps1 -Python "C:\Path\To\Python311\python.exe"
```

常用构建命令：

```powershell
# 构建 Processor、Collector 和 Agent
.\build_release.ps1

# 当前单机部署包
.\build_deployment.ps1

# 仅构建 Processor 程序更新包，不包含 data
.\scripts\build\build_processor.ps1 -UpdateOnly
```

`UpdateOnly` 包不会携带或覆盖目标机器的素材、模板、账号、任务、配置、数据库和个人素材库。公共素材首次交付应使用完整包；素材增量需要单独审核和发布。

## 目录导航

| 路径 | 用途 |
| --- | --- |
| `jyd_plain_json_probe/apps` | Processor、Collector、Agent 入口和前端 |
| `jyd_plain_json_probe/src/jyd_probe` | 核心 Python 业务代码 |
| `jyd_plain_json_probe/data/libraries` | 受控公共素材库 |
| `jyd_plain_json_probe/docs` | 接口、部署、渲染和专题文档 |
| `jyd_plain_json_probe/tests` | 自动化测试 |
| `jyd_plain_json_probe/scripts` | 环境安装和 Windows 打包脚本 |
| `jyd_plain_json_probe/tools` | 草稿诊断、素材提取和任务工具 |
| `jyd_plain_json_probe/vendor/jy-draftc` | 高版本剪映草稿解密工具 |

## 推荐阅读顺序

1. [主项目 README](jyd_plain_json_probe/README.md)
2. [安装与使用入口](jyd_plain_json_probe/START_HERE.md)
3. [开发者指南](jyd_plain_json_probe/docs/DEVELOPER_GUIDE.md)
4. [数字人集成说明](jyd_plain_json_probe/docs/DIGITAL_HUMAN_INTEGRATION_20260803.md)
5. [Render Job 结构](jyd_plain_json_probe/docs/RENDER_JOB_SCHEMA.md)
6. [程序更新说明](jyd_plain_json_probe/docs/PROCESSOR_UPDATE.md)

## 数据与安全边界

Git 仓库用于保存源码、文档、测试和经过审核的公共资源，不应提交以下内容：

- API Key、访问令牌、Cookie、密码或 `.env`。
- 本地 SQLite 运行数据库、项目日志、任务输出和用户上传内容。
- 未经审核的个人素材、生成视频或包含用户隐私的数据。

如果只是代码审阅，提供本仓库和配套数字人仓库的访问权限即可；如果需要实际运行，还必须单独配置数字人服务地址、账号权限、剪映环境及未纳入 Git 的运行资源。

## 许可说明

仓库中可能包含第三方工具、字体、音频、图片、视频或剪映资源。使用和分发前请分别核对其授权范围；第三方组件的许可文件优先于本说明。
