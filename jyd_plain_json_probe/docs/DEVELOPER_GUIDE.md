# 开发者指南

本文面向需要继续开发、调试和发布“影变批剪工作台”的维护者。用户安装和日常操作请阅读根目录 `START_HERE.md`；具体素材格式、接口字段和部署方式请按本文末尾的专题文档索引继续阅读。

## 1. 项目定位与边界

本项目通过读写剪映草稿 JSON 和 Windows UI 自动化完成批量视频生产，主要能力包括：

- 读取本机剪映草稿，必要时通过 `jy-draftc` 解密高版本草稿。
- 从 MP4 创建基础草稿，或从已导入的剪辑母版生成副本。
- 替换或新增 BGM、视频特效、字幕字体、贴纸、花字和文字模板。
- 应用镜像、裁剪、背景填色、人物定位和封面等画面变化。
- 生成单个或批量任务，并调用剪映顺序导出 MP4。
- 管理公共素材、个人素材、母版、任务、输出和回收站。
- 以单机嵌入模式运行，或由中央服务把任务交给一台或多台 Windows Agent。

必须明确的技术边界：

- 真正的剪映导出只能运行在 Windows 桌面会话中，目标电脑必须安装兼容版本的剪映。
- UI 自动化会占用剪映窗口，不适合在同一桌面会话中并行操作多个剪映实例。
- Web 服务可以集中部署，但实际执行导出的 Agent 仍然必须是可交互的 Windows 电脑。
- 草稿中的本地绝对路径必须在执行任务的电脑上可访问，或在导入、采集阶段被复制和重定位。

## 2. 总体架构

```text
浏览器
  |
  v
Processor Web/API (FastAPI, :8000)
  |-- 用户页面、批量编辑器、素材管理、任务结果
  |-- SQLite 控制库和任务状态
  |-- embedded: 进程内顺序执行 Render Job
  `-- agent: Agent 领取任务、回传状态和结果
          |
          v
      Windows Render Agent
          |
          v
      render_job.py
          |-- 草稿创建/复制/解密
          |-- JSON 修改和资源应用
          `-- 剪映 UI 自动导出 MP4

Local Collector (:8765)
  |-- 扫描本机 JianyingPro Drafts
  |-- 分析、解密、采集素材和字体
  |-- 选择本机视频及输出目录
  `-- 向 Processor 上传母版或素材包
```

### 2.1 三个主要应用

| 应用 | 源码入口 | 默认地址 | 职责 |
| --- | --- | --- | --- |
| Processor | `apps/processor/run_web_api.py` | `127.0.0.1:8000` | 网站、API、账户、素材、任务和嵌入式执行 |
| Collector | `apps/collector/run_local_collector.py` | `127.0.0.1:8765` | 本机草稿扫描、采集、文件选择和上传 |
| Agent | `apps/agent/run_agent.py` | 主动连接 Processor | 领取任务并控制本机剪映导出 |

`apps/auth_center` 是独立账户中心，用于多工作台统一登录。它不是剪映渲染链路的一部分，单机开发不需要启动。

### 2.2 两种执行模式

- `embedded`：Processor 自己执行任务。适合本机开发、单机安装包和大部分功能调试。
- `agent`：Processor 只调度任务，Windows Agent 主动领取并执行。适合中央网站连接多台剪映处理机。

切换模式不会改变 Render Job 的业务结构，只改变任务由哪个进程执行。

## 3. 目录结构

```text
apps/                         可运行、可打包的应用入口和前端
  processor/frontend/         主工作台、批量编辑器、素材页、登录页
    new/                      `/app/new` 新版工作台静态页面
  collector/frontend/         独立采集器调试页面
  auth_center/                可选的统一账户服务
src/jyd_probe/                核心 Python 代码
data/
  libraries/                  随正式安装包发布的公共素材
  personal_libraries/         当前安装实例采集的个人素材
  template_library/           已导入的剪辑母版
  web_storage/                数据库、任务、上传、输出和会话数据
docs/                         开发、接口、部署及素材专题文档
examples/                     Render Job JSON 示例
runtime/                      解密副本、测试环境和临时运行数据
scripts/                      开发环境及 Windows 打包脚本
tests/                        自动化测试
tools/                        草稿诊断、素材提取和任务调试工具
vendor/jy-draftc/             高版本剪映草稿解密程序
release/                      最终交付 ZIP
```

新版统一项目数据由 `src/jyd_probe/project_store.py` 管理。它与渲染队列共用
`control.db`，但只创建 `project_*` 表和独立的 `project_schema_meta`，不会修改既有
`schema_meta`、`batches`、`jobs` 或 `agents`。`Project` 包含多条 `ProjectItem`；
音频、原始片段、画面合成视频、上传视频和变体都按不可覆盖的素材版本保存。
模块 2 把 `project_schema_meta` 升级到版本 2：为脚本行增加当前输入图片指针，并增加
`project_input_images` 项目图片池。模块 3 升级到版本 3，增加按数字人账号保存的默认
音色和语音参数；逐行音色、音频素材版本、MiniMax 时间戳、数字人批次关联和异步操作
继续复用现有项目表。模块 4A 升级到版本 4，增加当前基础视频指针；基础视频与最终
`composition_video` 分离，RunningHub 原始分段继续按不可覆盖版本保存。模块 4B 升级到
版本 5，增加浏览器预览配方、按需导出和字幕渲染状态绑定；旧版
`POSTPROCESS_RUNNING` 剪映任务仍可同步完成。升级只执行
`CREATE TABLE IF NOT EXISTS` 和缺失列
`ALTER TABLE ADD COLUMN`，不会重建或清空既有项目及剪映任务表。

智能内容分析模块 5 将项目 schema 升级到版本 7，为 `project_items` 增加
`content_analysis_json`。快照按当前脚本 SHA-256 绑定，分别保存音乐、字幕分支状态和
结果；脚本变化只重置该行快照，音色、音频、字体或宽度变化不删除语义分析。工作台通过
`project_content_analysis.py` 把一个项目拆成逐行请求，单批并发最多 10；每行失败独立
落盘并继续其余行。内容分析状态不参与原有音频、4A、4B 或变体状态机，不得借分析失败
清空 MiniMax `raw_cues`、当前音视频指针或历史素材。

智能内容分析模块 6 将项目 schema 升级到版本 8，但不新增数据库列。字幕 JSON 增加
`semantic_mapping`；`semantic_subtitles.py` 负责严格原文复核和 MiniMax cue 锚点内的确定性
字符时间映射，`project_postprocess.py` 负责语义组真实字宽排版和失败降级。新音频素材的
metadata 保存脚本 SHA-256/长度；只有脚本、分析、音频和 raw cues 绑定四方一致时使用
`subtitle_units`，否则继续使用既有 raw cues 排版。任何路径都不得覆盖 `raw_cues`。

日志第一阶段将项目 schema 升级到版本 9，为 `project_operations` 增加独立
`correlation_id`。项目操作、云端声音批次、4A 画面生成和本地渲染都应传递该字段；
`idempotency_key` 只负责防重复提交，不得兼作关联号。历史操作以原 `operation_id` 回填。

Processor 日志位于 `data/logs/workbench.log`，本地渲染位于 `data/logs/render.log`，内嵌
Collector 位于 `data/logs/collector.log`，`server.log` 只保留启动和致命错误。独立 Collector
使用其状态目录下的 `logs/collector.log`；独立 Agent 使用
`%LOCALAPPDATA%/JianyingRenderAgent/logs/agent.log`。本地日志默认单文件 10 MB、保留 14 天，
写入前统一脱敏，不得记录访问令牌、API Key、完整脚本或完整请求体。

`GET /api/new/projects/{project_id}/diagnostics` 仅允许项目所有者下载临时 ZIP。摘要不得包含
脚本文本、素材路径、操作 `payload/result` 或错误正文；日志仅从 14 天内的 `workbench.log`、
`render.log`、`collector.log` 及其轮转文件中选取与当前 `project_id`、`operation_id` 或
`correlation_id` 精确匹配的行，并在打包前再次脱敏。独立 Agent 的 `agent.log` 不在本机包内。

不要把以下数据混为一类：

- `data/libraries`：公共、长期保留、可随完整安装包分发。
- `data/personal_libraries`：某个运行实例采集的个人素材，更新包默认不会覆盖；需要迁移时复制整个目录。
- `data/web_storage`：运行状态，不应从开发机直接覆盖生产机。
- `runtime`：临时数据，通常不参与正式发布。

## 4. 开发环境

### 4.1 前置条件

- Windows 10 或 Windows 11。
- Python 3.11，当前开发机也可显式指定已有 Python。
- 已安装兼容版本剪映，并能正常手工打开草稿和导出视频。
- PowerShell 5.1 或更高版本。
- `vendor/jy-draftc/jy-draftc.exe` 存在。

安装运行依赖：

```powershell
python -m pip install -r .\requirements.txt
python -m pip install pytest
```

当前主要依赖包括 `pyJianYingDraft==0.3.0`、FastAPI、Uvicorn、FontTools、OpenCV 和 NumPy。

### 4.2 启动单机开发环境

在项目根目录执行：

```powershell
.\start_processor.ps1 `
  -Python "D:\Myanaconda\python.exe" `
  -ProcessingMode standalone `
  -ExecutionMode embedded
```

访问：

```text
工作台：http://127.0.0.1:8000/app
高级页面：http://127.0.0.1:8000/app/advanced
素材管理：http://127.0.0.1:8000/app/assets
接口文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/api/health
```

如需读取本机草稿、弹出文件夹选择器或采集个人素材，再开一个 PowerShell：

```powershell
.\start_collector.ps1 `
  -Python "D:\Myanaconda\python.exe" `
  -ServerUrl "http://127.0.0.1:8000"
```

默认端口是 `8765`。主页面会通过本地接口检测 Collector 是否在线。

### 4.3 前端开发

前端主体是原生 HTML、CSS 和 JavaScript，修改后刷新浏览器即可：

- `apps/processor/frontend/product.*`：普通用户工作台和批量任务主流程。
- `apps/processor/frontend/advanced.*`：高级任务页面。
- `apps/processor/frontend/assets.*`：素材和母版管理。
- `apps/processor/frontend/app.*`：旧版/通用页面逻辑，修改前先确认路由实际加载的脚本。

`apps/processor/frontend/new/` 的 Tailwind 与 Font Awesome 必须随工作台本地提供，运行时
不得依赖 CDN，否则断网或 CDN 不可达时会导致 `hidden`、布局和弹层样式整体失效。页面新增
或修改 Tailwind class 后，在项目根目录重新生成并提交 `tailwind.generated.css`：

```powershell
npx --yes tailwindcss@3.4.17 -c apps/processor/frontend/new/tailwind.config.cjs -i apps/processor/frontend/new/tailwind.input.css -o apps/processor/frontend/new/tailwind.generated.css --minify
```

Font Awesome 的 CSS 和字体位于 `apps/processor/frontend/new/vendor/fontawesome/`；打包与迁移
不得遗漏该目录。`tests/test_new_frontend.py` 会校验四个新版页面只引用本地关键样式、静态
路由可访问，并确保 `.woff2` 以 `font/woff2` 返回。

浏览器缓存导致代码未更新时，先使用 `Ctrl+F5` 强制刷新，再检查开发者工具 Network 中返回的 JS 是否为当前文件。不要通过复制同一份逻辑到多个页面解决缓存问题。

### 4.4 隔离测试环境

测试网站使用独立端口和独立数据副本，不修改正式 `data`：

```powershell
.\start_test_processor.ps1 -Python "D:\Myanaconda\python.exe"
.\start_test_collector.ps1 -Python "D:\Myanaconda\python.exe"
```

访问 `http://127.0.0.1:8001/app`。首次创建或需要重新从正式素材初始化时：

```powershell
.\start_test_processor.ps1 -ResetData
```

测试环境位于 `runtime/test_environment`。正式环境和测试环境仍会控制同一个本机剪映，不要同时提交真实导出任务。

## 5. 核心调用链

### 5.1 从网页提交到导出

1. 前端提交 `/api/render` 或 `/api/render/batch`。
2. `src/jyd_probe/web_api.py` 校验媒体、母版和素材引用。
3. 批量请求通过维度候选展开、去重和数量限制生成子任务。
4. `src/jyd_probe/task_store.py` 持久化批次及任务状态。
5. `RenderJobQueue` 顺序执行，或等待 Agent 领取。
6. `src/jyd_probe/render_job.py` 准备视频源或母版副本。
7. 按顺序应用字幕、文字、音频、特效、贴纸、画面套装和封面。
8. 保存草稿并调用剪映 UI 自动化导出 MP4。
9. 状态和输出写回 `data/web_storage`，前端轮询展示结果。

### 5.2 Render Job

稳定结构版本为 `jyd.render_job.v1`。主要入口：

```python
from jyd_probe.render_job import run_render_job, run_render_job_file

result = run_render_job_file("job.json")
print(result.as_dict())
```

命令行调试：

```powershell
D:\Myanaconda\python.exe .\tools\jobs\run_render_job.py `
  --job .\examples\render_job_video.example.json
```

完整字段说明见 `docs/RENDER_JOB_SCHEMA.md`。修改任务结构时应同时更新：

- `render_job.py` 的解析与校验。
- `web_api.py` 的媒体和素材引用解析。
- 前端任务构造逻辑。
- `examples` 中至少一个示例。
- 对应自动化测试和 `docs/RENDER_JOB_SCHEMA.md`。

### 5.3 草稿处理顺序

`render_job.py` 是业务编排入口，底层职责分散在以下模块：

| 模块 | 主要职责 |
| --- | --- |
| `draft_crypto.py` | 高版本草稿检测和解密 |
| `draft_factory.py` | 从单个 MP4 或按顺序排列的多个原始视频创建基础草稿 |
| `draft_transfer.py` | 草稿复制、重定位和元数据处理 |
| `draft_compat.py` | 剪映版本兼容字段处理 |
| `content_replace.py` | 视频、文字、音频和特效的基础修改 |
| `subtitles.py` | 长文本切分、SRT 生成和字幕导入 |
| `text_asset_apply.py` | 花字和复合文字素材应用 |
| `sticker_apply.py` | 全屏贴纸和四角贴纸应用 |
| `visual_variant.py` | 镜像、人物定位、裁剪和背景填充 |
| `cover_apply.py` | 封面帧、矩形和文字轨道 |

新增处理步骤时，要先确定它在时间线中的顺序以及是否会改变草稿总时长。不要在多个模块中重复修改同一轨道。

## 6. 素材库与母版

### 6.1 公共素材与个人素材

所有素材类型都应通过统一的清单或 bundle 结构被读取，避免运行时依赖原电脑的剪映缓存绝对路径。

```text
data/libraries/<kind>/              公共素材
data/personal_libraries/<kind>/     本机采集素材
```

常见 `<kind>`：

- `audio_library`
- `effect_library`
- `font_library`
- `sticker_library`
- `corner_sticker_library`
- `text_effect_library`
- `text_style_library`
- `text_template_library`

四角贴纸示例结构：

```text
corner_sticker_library/
  bundles/<素材标识>/...
  manifest/sticker_manifest.json
```

迁移个人素材时复制整个 `data/personal_libraries`，不能只复制资源文件而遗漏 manifest。完整安装包目前主要自动带入 `data/libraries`；运行后采集到 `personal_libraries` 的内容需要明确决定是否随交付包分发。

### 6.2 素材管理状态

素材管理支持重命名、分类、启用/停用、软删除和恢复。软删除不会立即物理清除文件，而是在元数据中标记为回收站状态；默认保留 7 天后由生命周期清理器删除。

涉及素材删除时必须使用 `asset_admin.py` 和现有 API，不要在前端直接拼路径删除文件。

### 6.3 母版

母版位于：

```text
data/template_library/<template_id>/
  draft/
  template_meta.json
```

母版可能来自高版本加密草稿。导入阶段负责解密、分析、复制依赖和生成元数据；生成任务应引用 `template_id`，不要重新读取用户原始草稿路径。

复合文字模板通常依赖人工排版，剪辑母版默认应保持原样，不能作为普通字体、BGM 或特效一样自动参与随机变化。

## 7. 配置与环境变量

源码启动脚本会设置大部分变量。常用变量如下：

| 变量 | 作用 | 常见默认值 |
| --- | --- | --- |
| `JYD_WEB_STORAGE_ROOT` | 任务、上传和输出根目录 | `data/web_storage` |
| `JYD_RESULT_LIBRARY_ROOT` | 新版最终变体成果归档根目录 | `D:\auto` |
| `JYD_DATABASE_PATH` | SQLite 控制库 | `data/web_storage/control.db` |
| `JYD_TEMPLATE_LIBRARY_ROOT` | 母版库 | `data/template_library` |
| `JYD_PERSONAL_LIBRARY_ROOT` | 个人素材根目录 | `data/personal_libraries` |
| `JYD_WEB_DRAFT_ROOT` | 实际剪映草稿目录 | 自动检测或手工指定 |
| `JYD_DRAFTC_EXE` | `jy-draftc.exe` 路径 | `vendor/jy-draftc` 或打包资源 |
| `JYD_EXECUTION_MODE` | `embedded` 或 `agent` | `embedded` |
| `JYD_ALLOW_LOCAL_FILE_ACCESS` | 是否允许网页引用本机路径 | 源码单机启动为 `true` |
| `JYD_AUTH_SERVER_URL` | 统一账户中心地址 | 由部署配置决定 |
| `JYD_SHARED_PROCESSOR_URL` | 公用工作台地址 | 空 |
| `JYD_AGENT_TOKEN` | Agent 接入令牌 | 空 |
| `JYD_MAX_ACTIVE_JOBS` | 单批最大任务数 | `500` |
| `JYD_MEDIA_RETENTION_HOURS` | 上传媒体保留时间 | `24` |
| `JYD_TEMPLATE_RETENTION_HOURS` | 临时母版保留时间 | `48` |
| `JYD_DRAFT_RETENTION_HOURS` | 生成草稿保留时间 | `48` |
| `JYD_OUTPUT_RETENTION_HOURS` | 成功输出保留时间 | `72` |
| `JYD_ASSET_TRASH_RETENTION_DAYS` | 素材回收站保留时间 | `7` |

发布包优先使用 `data/processor_config.json` 和 Windows 启动器保存的配置。开发环境不要把真实令牌、管理员密码或生产地址提交到源码。

## 8. API 与状态存储

开发时以 FastAPI 自动文档 `/docs` 为当前接口事实来源，专题说明见 `docs/WEB_API.md`。

主要 API 分组：

- `/api/auth/*`：用户登录和登录接力。
- `/api/admin/*`：账户、素材和测试批次管理。
- `/api/media/*`：视频和音频上传。
- `/api/draft-imports`、`/api/templates/*`：母版导入和读取。
- `/api/assets/*`、`/api/local-assets/*`：公共及个人素材。
- `/api/render`、`/api/render/batch`：单任务和批量任务。
- `/api/jobs/*`、`/api/batches/*`：状态、结果、重试、取消和下载。
- `/api/agents/*`：处理机注册、心跳、领取和回传。
- `/api/new/projects*`：新版统一项目、脚本行、素材版本、状态和可执行操作。
- `/api/new/script-imports/preview`：严格解析两列 `.xlsx`/`.csv` 脚本。
- `/api/new/projects/{id}/images*`、`image-mapping`：项目图片池、逐行图片版本和后端分配策略。
- `/api/new/voices*`、`/api/new/voice-creations*`：当前数字人账号的官方/自定义音色、试听和声音制作。
- `/api/new/voices/{id}/activate`、`DELETE /api/new/voices/{id}`：显式激活或移除自定义音色卡。
- `/api/new/projects/{id}/voice`：原子地把已保存音色设为项目默认值并应用到全部脚本行。
- `/api/new/projects/{id}/items/{item_id}/voice`：覆盖单个脚本行的音色。
- `/api/new/projects/{id}/audio*`：项目声音生成、状态同步、单行重试、试听和下载。
- `/api/new/projects/{id}/composition*`：4A 画面启动、真实状态同步和失败阶段重试。
- `/api/new/projects/{id}/items/{item_id}/base-video`：下载当前标准化基础视频。
- `/api/new/postprocess/options`：返回实际可读的真实字体和现有 BGM 素材。
- `/api/new/projects/{id}/postprocess*`：4B 浏览器预览配方生成与状态查询。
- `/api/new/projects/{id}/items/{item_id}/postprocess/export`：用户明确下载时按需启动一次剪映导出。
- `GET/POST /api/new/projects/{id}/items/{item_id}/current-video`：下载当前视频或上传本地视频并切换版本。
- `GET /api/new/projects/{id}/videos/download`：一次性 ZIP 下载项目所有未变体当前成片。
- `/api/new/projects/{id}/items/{item_id}/original-materials`：下载单个原始片段或包含顺序清单的多片段 ZIP。

新版浏览器入口为 `/app/new`，成果库为 `/app/new/gallery`，声音中心为
`/app/new/voices`。三页均受普通站点会话保护；公开的 `/app/new/login` 调用现有
`/api/auth/login`，由工作台后端向数字人账号中心验证账号并把令牌保存在 HTTP-only
Cookie 中。前端只通过 `/api/auth/session` 读取用户摘要，通过 `/api/auth/logout`
退出，不得读取或保存数字人访问令牌。

任务和批次会同时涉及 SQLite 元数据及 `data/web_storage` 下的 JSON/媒体文件。调试数据异常前先停止服务并备份整个 `data/web_storage`，不要只复制或修改 `control.db`。

新版项目 API 只允许普通数字人账号访问，技术管理员会话不能代替普通账号成为项目
所有者。项目详情中的 `allowed_actions` 是页面按钮权限的唯一业务来源；前端不得根据
显示文本或本地定时器自行推进项目状态。新版页面已经完成登录、脚本/图片输入、声音和
画面 4A/4B 模块。声音编排由 `project_audio.py` 完成：工作台只把脚本、音色和语音参数提交
给数字人后端 MiniMax 批次能力，强制停在 `AWAITING_REVIEW`，下载音频和原始时间戳后
创建本地不可覆盖素材版本；声音阶段不上传图片。`project_composition.py` 只有在用户再次
确认费用后才上传该行当前图片，调用数字人后端把图片与已审核音频绑定并放行既有任务，
保存全部成功原始分段及标准化 `base_video`，并按真实后端状态驱动页面。
它不添加字幕/BGM、不创建最终 `composition_video`，也不生成变体。音频完成后到 4A
启动前，图片仍可替换；4A 上传的永远是提交时的当前图片。
`project_audio.py` 不提交本地硬编码的 RunningHub 提示词；行级未显式设置时由数字人网站
配置的默认提示词接管，避免工作台旧值截断服务器配置。

`project_postprocess.py` 负责 4B：保存 MiniMax 原始 cues 不变，使用所选真实字体文件的
glyph advance 测量宽度，把过长文本在原 cue 时间内派生为连续的单行 render cues。
语义排版先修复过短逗号前缀，再把剩余软/硬标点边界视为不可跨越的分句边界；局部字宽
切分统一保护数字与量词表达式，避免出现“十 / 年”“5 万 / 名”这类字幕断裂。
普通 4B 立即把 `base_video`、render cues、字体和 BGM 登记为浏览器预览配方，不向
`RenderJobQueue` 提交任务。固定参数为居中、画面宽度 `0.8`、`transform_y=-0.6`
（距底部约 20%）、`DouyinSansBold` 11 号、默认白字、黑色 `0.06` 描边、BGM 音量 0.3。
浏览器直接读取同一冻结样式，不得为溢出字幕临时缩字；
无法可靠排版时状态为 `REVIEW_REQUIRED`，不会静默显示溢出字幕。只有用户明确下载普通
成片时才调用 `postprocess/export` 提交一次剪映任务。后续变体必须把基础/上传视频与已
冻结的字幕、BGM 配方合并到同一个变体任务中一次导出，不能依赖一个预先导出的普通成片。
若该按需导出失败但 `base_video` 和 `PREVIEW_READY` 配方仍在，行级失败重试必须直接以新的
幂等键再次调用 `postprocess/export`；不得把全项目行重新提交给 `postprocess/generate`。
若 4A 返回多个 RunningHub 原始片段，浏览器预览使用已按音频时长标准化的 `base_video`；
4B 按需导出和模块 6 使用按 `video_index` 排序的 `video_sequence`，让剪映草稿保留真实分段。
每段目标时长来自原分段计划：素材过长裁尾，素材略短则对该段画面轻微放慢到目标时长；
所有片段原声静音，并从 0 写入一条完整、已审核的 MiniMax 音频。字幕仍直接使用 MiniMax
绝对时间戳，因此供应商 MP4 容器时长误差不会在后续片段中累计。相邻片段继续使用 250000
微秒剪映原生叠化，画面、权威语音、字幕、BGM 和封面共享同一绝对时间轴。

`ProjectPostprocessCoordinator.sync()` 必须扫描全部仍为 `PENDING/RUNNING` 的 4B 操作，
不能只检查每行最新一条。更新操作时通过 `operation_id` 精确定位；被新尝试取代的旧操作只
回收自身终态，不覆盖当前行状态、字幕或成片指针。

新版页面把字幕效果卡直接放在表格“字幕样式”列，点击效果卡才打开字体和颜色配置；BGM
继续在相邻列直接选择。修改任一设置只把对应脚本行退回 `BASE_VIDEO_READY` 并保留
`base_video`、付费任务和历史成片。前端用同一个 `POST /postprocess/generate` 仅提交该行
`item_id`，即可重新派生字幕并刷新浏览器 BGM 预览；服务端只处理请求中明确列出的脚本行。
字幕效果卡固定显示“这是字幕预览”，不绑定脚本或 render cue。BGM 下拉框隐藏内部 `auto`
哨兵：自动 Top1 成功时直接显示解析后的具体曲目，尚无解析结果时显示“无音乐”；提交时仍
保留既有 `bgm_selection_mode=auto`。单行分析按钮在请求开始后立即切换为“AI 分析中”，成功
后直接保存并展示 Top1；手动曲目或手动无音乐不被覆盖。
每条表格任务在任务 ID 下提供 `DELETE /api/new/projects/{project_id}/items/{item_id}` 入口。
后端拒绝删除运行中或内容分析中的任务；其他状态删除时级联清理该行素材版本、操作、外部
关联和未被其他行引用的本地生成文件，再重新排列 `position`。任务可删到 0 行并通过“添加
分段”重新创建。共享图片池及其他任务不删除，前端必须先提示本地记录删除和第三方费用不可撤销。
从音频已就绪点击“生成完整成片”时，只对 RunningHub 费用确认一次，4A 完成后自动执行
4B 并进入视频预览，不再弹出字幕/BGM 二次确认。

模块 5 直接复用 `ProjectStore` 的素材版本和用户归属校验。上传视频以原始请求体写入当前
用户的项目目录，限制为 MP4/MOV/AVI/MKV/WebM 和 `JYD_MAX_VIDEO_UPLOAD_BYTES`；新增
`source_type=user_upload` 的 `composition_video` 并设为当前版本。`ProjectStore` 会保留
旧成片和 RunningHub 原始片段，同时解绑并失效原 MiniMax 字幕。原始素材下载按
`external_ref.video_index` 排序；单片段直接返回文件，多片段使用一次性 ZIP 并附加
`片段顺序清单.json`，响应结束后删除临时 ZIP。
底部“一键下载未变体视频”在所有行普通成片预览就绪后启用。前端对仅有浏览器动态预览的
行顺序调用 `POST /postprocess/export` 并等待真实 `composition_video`，再通过项目级
`GET /videos/download` 打包；variant 素材不参与，临时 ZIP 在响应结束后删除。

`project_content_analysis.py` 负责新增智能内容分析模块 5。Excel/CSV 导入、添加分段和编辑
脚本只把相应快照置为 `NOT_REQUESTED`，不发起分析。用户点击“生成声音预览和脚本分析”时，前端在
提交声音任务的同时，对本批声音目标中 `NOT_REQUESTED` 的行调用
`POST /api/new/projects/{project_id}/content-analysis`；协调器为每个需要分析的
`ProjectItem` 单独调用数字人后端 `/api/workbench/content-analysis`，不会把多条脚本
拼成一个模型输入。脚本哈希未变化时，声音重生成不会重做文本分析；普通调用跳过已有
`PENDING`/`SUCCESS`/`PARTIAL`/`FAILED` 尝试，单行显式重试使用 `force_refresh=true`。
服务端响应在工作台再次核对脚本哈希、长度、分支状态和
字幕文字完整覆盖后才落盘。刷新重试时，新失败不得覆盖同一脚本此前已经成功的分支。
项目批量调用最多并发 10 行，失败按行保存并继续。模块 5 不进行字符到时间轴映射或字体
排版；音乐分支成功后会调用 `ProjectMusicSelector.resolve_for_analysis` 产生不依赖音频时长的
初步 Top1，并通过 `save_item_auto_music_selection` 保存，但不会覆盖显式 manual 设置。

`semantic_subtitles.py` 负责智能内容分析模块 6。工作台再次拒绝带大模型时间字段、未连续
覆盖原文或语义属性非法的 `subtitle_units`；MiniMax cue 文本允许省略原文空格/换行，但
所有非空白字符必须精确一致，`~` 不作通配符。每条 cue 的真实 `start_us/end_us` 是唯一
时间锚点，cue 内字符时间只做确定性比例派生。`bind=left/right/both` 和
`break_after=avoid` 先形成不可拆语义组，再按 11 号真实字宽组合为 `render_cues`。脚本、
分析、当前音频脚本摘要或 raw cues 音频绑定不一致，以及映射/排版失败时，4B 记录
`semantic_mapping.status=FALLBACK` 并调用原有 `layout_one_line_captions`；raw cues 永久保留。
本模块不执行音乐 Top1。

当前单行参考宽度为 13em。若只有某个已映射语义组超过真实字宽，排版器会在该组时间范围内
局部补切并继续使用其余 AI 断点；只有脚本、版本、原文或时间轴映射不安全等全局问题才整篇
回退 `layout_one_line_captions`。模型组边界和局部补切必须共用保护词边界：完整词内部的模型
断点先合并，局部补切只遍历安全字符位置，并把少量完整语义短语结尾作为优先候选。不能为了
行宽均衡拆成“女｜性”“核心｜逻辑”“以｜及”或“形｜式”。

`project_music.py` 负责智能内容分析模块 7。内容分析完成时先从当前行已校验的
`music_intent` 和本地 `music_profiles.v1.json` 返回可见的初步唯一 Top1；同一项目批量处理时
按脚本行顺序传递 `recent_identity_counts`，在语义评分之后施加确定性的已使用次数惩罚，
让分数接近的合格曲目适度轮换。4B 自动模式按相同项目计数加入当前 MiniMax 音频真实时长
复核并保存最终 `jyd.project-music-selection.v1` 快照，不保存候选列表或 Top3。声音版本变化
保留已选 identity 并标记 `STALE`，避免界面退回“无音乐”，4B
会按新音频时长刷新绑定。音乐分支失败按项目默认音乐或无 BGM 降级；手动曲目及手动无 BGM
始终优先。变体只冻结继承 4B 最终 BGM。

智能内容分析模块 8 的跨项目验收位于数字人项目
`tests/test_content_analysis_workbench_integration.py`。它直接把数字人服务端
`analyze_content` 的实际响应传入本项目 `_validated_remote_result`、
`map_subtitle_units_to_raw_cues` 和 `MusicProfileMatcher`，覆盖双成功、两种部分成功、安全
索引重算、空格、换行和 `~`。新增测试 `3 passed`；最终完整 mock 回归为数字人
`216 passed`、本项目 `260 passed`。本轮没有真实第三方请求或生产变更。

`project_variants.py` 负责模块 6。推荐设置启用视频特效、全屏贴纸和画面变化套装，组合
选择使用确定性的加权 maximin，而不是随机抽样：裁剪比例、视频特效、全屏贴纸和四角贴纸
的权重大于背景色，并把已有成功签名作为补充生成的距离参照。每行冻结基础视频（用户上传
视频则冻结上传版本）、模块 4B 的 render cues/字体/BGM、手动封面和素材身份；项目级生成
可合并为一次 `submit_batch`，行级生成则只提交指定 `item_id`，不会先导出普通
`composition_video`。封面固定 3 帧，封面
视频片段并入主视频轨道首段，临时视频轨道随后删除；底层统一后移所有正文轨道。操作类型为
`VARIANT_GENERATE`、`VARIANT_SUPPLEMENT` 和
`VARIANT_RETRY`；成功文件保存为不可覆盖的 `variant_video`，失败项可原样重试。

`project_results.py` 负责模块 7 的物理归档和成果查询。`project_script_sources` 保存用户原始
XLSX/CSV 的版本与校验信息；`project_result_batches` 使用 SQLite 当日计数器原子分配
`D:\auto\月.日\批次号`。脚本文件先复制到批次目录，模块 6 的 MP4 随后直接输出到该目录。
成果页不把目录扫描结果当作用户归属，而是按 `owner_user_id` 查询项目/素材/剪映批次索引，
再检查 `managed_path` 是否真实存在。这样手工移动或删除文件会显示为缺失，但不会跨账号泄露。

新版表格采用版本化修改而不是完成后永久锁定。非运行中脚本行可以随时修改：脚本或音色
清空当前音频/基础视频/成片指针并回到 `DRAFT`；图片只清空基础视频和成片指针并保留当前
音频；BGM 或字幕设置只清空当前成片并保留基础视频。历史资产、操作和外部链接不删除。
声音总按钮在存在待生成行时只处理待生成行；全部行均已有音频时再次点击会为全部行创建
新的声音批次和音频素材版本。同一秒创建的多批外部链接按数据库插入顺序选择最新版本。

核心工作台只能选择数字人账号中已经保存的音色。项目默认音色由后端统一写入全部脚本
行，前端逐行下拉框只负责展示和提交单行覆盖。声音中心的克隆/融合是两阶段流程：先生成
可试听结果，用户试听确认后再保存。保存后的自定义音色仍是 `READY`，必须由用户二次
确认激活，后端执行第一次正式 TTS 并切换到 `ACTIVE` 后才能进入核心工作台。删除音色卡
只从可用音色库移除，不破坏历史任务和历史音频；当前项目仍引用时拒绝删除。

## 9. 自动化测试

运行全部不依赖真实剪映导出的测试：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest -q
```

运行单个测试文件：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest -q .\tests\test_visual_variant.py
```

建议按修改范围选择测试：

- Render Job 或草稿结构：`test_mother_draft_rendering.py`、`test_draft_*`。
- 批量组合：`test_batch_dimensions.py`、`test_web_batch_naming.py`。
- 画面、贴纸、封面：`test_visual_variant.py`、`test_sticker_library.py`、`test_cover_apply.py`。
- 素材管理：`test_asset_admin.py`、`test_personal_asset_management.py`。
- 多处理机：`test_multi_processor_api.py`。
- 前端批量流程：`test_batch_editor_frontend.py`、`test_batch_result_center.py`。

自动化测试不能代替真实剪映回归。涉及 UI 导出、剪映版本兼容、缓存资源或字体渲染的修改，最终必须在目标剪映版本上完成一次真实 MP4 闭环。

## 10. Windows 打包与发布

### 10.1 初始化构建环境

```powershell
.\scripts\setup_build_environment.ps1 `
  -Python "D:\Myanaconda\python.exe"
```

构建缓存位于项目同级 `.jyd-build-cache`，不属于源码。

### 10.2 常用构建命令

```powershell
# 本机完整工作台、采集器和 Agent
.\build_release.ps1

# 当前单机交付所需包
.\build_deployment.ps1

# 只构建公用处理机
.\build_shared_processor.ps1

# 完整可迁移源码包，可选同时重建发布包
.\build_portable_project.ps1 -BuildReleases
```

底层单独构建 Processor：

```powershell
.\scripts\build\build_processor.ps1 -CompressionLevel Fastest
.\scripts\build\build_processor.ps1 -DeploymentMode shared -CompressionLevel Fastest
.\scripts\build\build_processor.ps1 -UpdateOnly -CompressionLevel Fastest
```

`UpdateOnly` 会排除整个 `data` 目录，适合更新程序且保留目标机账户、任务、素材和配置；它不能用来分发新增素材。

完整 Processor 构建会复制 `data/libraries` 中受支持的公共素材和 `data/template_library`。运行实例后来采集的 `data/personal_libraries` 默认属于实例数据，交付前如需预装，必须显式复制并验证 manifest 和 bundle 都存在。

### 10.3 发布前检查

1. 运行相关自动化测试。
2. 启动全新的测试数据目录，确认页面和 API 能打开。
3. 检查 ZIP 根目录包含 EXE、`_internal`、`tools`、说明文件和预期的 `data`。
4. 检查 `jy-draftc.exe` 已进入 `tools`。
5. 检查公共素材、个人素材和母版是否符合本次发布范围。
6. 在非开发电脑上解压运行，验证不依赖开发机 Python。
7. 最后执行一次真实草稿生成和 MP4 导出。

## 11. 常见扩展方法

### 11.1 新增一种素材类型

1. 定义素材目录和 manifest/bundle 格式。
2. 编写或扩展 `tools/library` 下的采集工具。
3. 在 Web API 的素材列表、引用校验和个人素材导入中注册类型。
4. 在 `asset_admin.py` 注册管理类型，确保启停、软删除和恢复一致。
5. 在 Render Job 中实现应用逻辑。
6. 增加前端选择和批量维度构造。
7. 更新打包脚本的素材复制列表。
8. 增加提取、API、应用和打包覆盖测试。

遗漏第 4 或第 7 步通常会导致“网页可以采集，但管理接口报不支持”或“开发机可用，安装包缺素材”。

### 11.2 新增一个可排列组合元素

组合维度由 `web_api.py` 的批量展开逻辑处理。候选项应包含稳定 `id`、简短 `label`，以及用于覆盖任务的 `patch` 或追加数组的 `append`。

修改时需要保证：

- 在生成草稿前完成筛选，不能先生成大量无用草稿再删除。
- 同一批内组合不重复。
- 任务数不超过服务端上限。
- 固定、参与组合、不使用三种模式语义一致。
- 组合名称简短但任务 ID 保持唯一。
- 批量失败不阻断已成功结果的预览和下载。

### 11.3 新增一个画面处理步骤

先决定处理对象是视频素材、轨道片段还是整个画布，再确定与镜像、裁剪、贴纸、字幕和封面的执行顺序。时间轴切段会影响后续片段索引，优先让一个模块统一完成切段并返回稳定结果。

## 12. 调试与故障定位

### 后端返回 500

先看启动 Processor 的控制台 traceback，再根据请求路径定位 `web_api.py` 对应路由。不要只根据前端的 `Internal Server Error` 修改 UI。

### 网页显示旧版本

确认启动的是源码目录还是旧发布包；使用 `Ctrl+F5`，并在 Network 中检查脚本响应。发布包必须重新构建，修改源码不会自动改变已解压的 EXE。

### 本地采集器已连接但处理机离线

Collector 和 Render Agent 是两个不同角色。Collector 在线只表示网页可以读取本机文件；是否能执行任务取决于 Processor 使用 `embedded`，或 `agent` 模式下是否有 Agent 注册并持续心跳。

### 开发环境有素材，发布包没有

依次检查：

1. 素材位于 `data/libraries` 还是运行实例的 `data/personal_libraries`。
2. 构建是否使用了 `UpdateOnly`。
3. manifest 和 bundles 是否一起复制。
4. 页面当前连接的是本机工作台还是另一台公用处理机。

### 剪映导出失败

确认剪映已安装、桌面未锁屏、没有遮挡导出对话框、草稿目录正确、素材路径有效。保留失败任务的 job JSON、草稿副本、Processor 日志和剪映版本号，这四项是定位兼容问题的最低信息集合。

## 13. 开发约定

- 先读现有模块和测试，再扩展已有模式，避免重新创建平行实现。
- 草稿 JSON 使用结构化读写，不使用大段字符串替换。
- 公共路径通过 `runtime_paths.py` 和环境变量解析，不在核心模块硬编码开发机盘符。
- 临时文件必须进入受管理目录，并明确到期清理规则。
- 永久素材和一次性视频必须分开存储。
- 修改 API、任务 schema、素材格式或部署步骤时同步更新文档和测试。
- 不覆盖用户已有的 `data`，程序更新优先使用 UpdateOnly 包。
- 涉及用户本地文件的接口只在明确允许本地访问的单机模式启用。

## 14. 专题文档索引

| 主题 | 文档 |
| --- | --- |
| 项目目录 | `docs/PROJECT_LAYOUT.md` |
| 当前状态 | `docs/PROJECT_STATUS.md` |
| Web API | `docs/WEB_API.md` |
| Render Job | `docs/RENDER_JOB_SCHEMA.md` |
| 本地采集器 | `docs/LOCAL_COLLECTOR.md` |
| 多处理机 | `docs/MULTI_PROCESSOR.md` |
| 处理机部署 | `docs/PROCESSOR_DEPLOYMENT.md` |
| 公用机快速部署 | `docs/SHARED_PROCESSOR_QUICK_START.md` |
| 程序更新 | `docs/PROCESSOR_UPDATE.md` |
| 快速打包 | `docs/FAST_BUILD.md` |
| 母版导入分析 | `docs/DRAFT_IMPORT_ANALYZER.md` |
| 音乐库 | `docs/AUDIO_LIBRARY.md` |
| 特效库 | `docs/EFFECT_LIBRARY.md` |
| 字体库 | `docs/FONT_LIBRARY.md` |
| 贴纸库 | `docs/STICKER_LIBRARY.md` |
| 花字库 | `docs/FLOWER_TEXT_LIBRARY.md` |
| 复合文字模板 | `docs/TEXT_TEMPLATE_LIBRARY.md` |
| 语音标点停顿配方（跨项目、待开发） | `D:\工作内容\轻盈健\数字人\语音标点停顿配方开发文档.md` |

遇到文档与代码不一致时，以当前测试、FastAPI `/docs` 和实际入口代码为准，并在修复代码的同一个改动中更新文档。

## 15. 新版工作台 2026-08-05 细节修正

- 4A 通过数字人工作台接口启动时使用 `exact_timestamps` 内部模式：音频时长仅向上取整到
  RunningHub 接受的整秒，不使用旧版上传音频的静音尾垫。
- `/api/new/postprocess/options` 返回 `default_font_identity`；当前默认是
  `resource_id:7244518590332801592`（`DouyinSansBold`）。前端新配置以此初始化，历史行的
  `settings.postprocess.font_identity` 优先级更高。
- 成果库首页只渲染批次缩略卡，批次弹层才渲染全部视频卡；选择状态使用真实变体
  `asset_id`，支持当前查询结果的总全选、单批次全选、ZIP 下载和删除选中。删除接口先对
  整批 ID 做账号归属校验，再原子删除数据库记录和对应受管导出文件。
- 核心工作台脚本列采用固定表格布局和 `overflow-wrap:anywhere`，编辑区最大高度内纵向
  滚动，避免长文本改变其他列宽度。
- 核心工作台左侧输入区可通过表格标题栏按钮收起；状态保存在本机
  `localStorage`，收起时右侧表格跨满工作区。表头类 `table-header-input` 使用低饱和深色
  底配靛蓝标线和圆点表示输入/操作列，`table-header-output` 使用深青色底配青绿标线和
  圆点表示三个预览输出列；标题栏显示对应图例，只改变表头，不改变正文单元格状态配色。

## 16. 语义前景图片（2026-08-07）

- `semantic_visuals.py` 负责受控目录校验、内容哈希版本、最长别名召回、稳定字符候选、
  MiniMax `raw_cues` 时间映射、素材选择和密度规则；本地路径从不发送到云端。
- `project_visual_analysis.py` 逐行并发（上限 10）调用数字人网站，只接受严格的
  `jyd.visual-analysis.v1`。脚本、目录、音频或 raw cues 变化会让自动配方失效；人工锁定项
  保留为待复核，迟到结果需继续匹配脚本、目录和候选集合。
- 每行 `visual_analysis` 保存语义决策、映射状态和最终 `recipe`。用户保存后条目标记
  `selection_mode=manual`；重新分析只能保留并尊重锁定人工项。
- 浏览器播放预览和 `project_postprocess.py` / `project_variants.py` 的 4B 冻结任务读取同一
  配方。剪映写入独立“语义前景图片”贴纸轨道，单张失败按 optional 跳过。
- 新版表格把“语义配图”保持在 BGM、字幕的配置区域，并将“单条生成”移到最右侧；审核
  弹窗的“移除本行”只修改当前行配方，不删除素材库文件。全局图库新增、停用和物理删除
  保护规则见 `docs/SEMANTIC_VISUAL_LIBRARY.md`。

## 17. 语音标点停顿配方（方案已确认，尚未实施）

- 权威方案位于 `D:\工作内容\轻盈健\数字人\语音标点停顿配方开发文档.md`。它是独立的
  本地确定性语音配方，不复用内容分析或语义配图的大模型结果。
- 工作台负责解析人工控制语法、保存原始脚本和紧凑覆盖、显示生成前预检；数字人服务端
  负责按同一规则版本复核并编译 MiniMax 专用标记。
- 普通空格不代表停顿；真实换行参与规则，页面自动折行不参与。字幕、字数、内容分析和
  语义配图始终读取不含控制标记的原始脚本。
- 当前 `project_audio.py` 仍提交原始 `script_text`。在项目 schema、API 契约、幂等摘要和
  跨项目测试完成前，不得把本节写成已经上线的能力。
