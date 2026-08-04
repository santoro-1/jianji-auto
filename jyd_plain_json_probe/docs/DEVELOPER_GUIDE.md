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

前端是无构建步骤的原生 HTML、CSS 和 JavaScript，修改后刷新浏览器即可：

- `apps/processor/frontend/product.*`：普通用户工作台和批量任务主流程。
- `apps/processor/frontend/advanced.*`：高级任务页面。
- `apps/processor/frontend/assets.*`：素材和母版管理。
- `apps/processor/frontend/app.*`：旧版/通用页面逻辑，修改前先确认路由实际加载的脚本。

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
| `draft_factory.py` | 从 MP4 创建基础草稿 |
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

新版浏览器入口为 `/app/new`，成果库为 `/app/new/gallery`，声音中心为
`/app/new/voices`。三页均受普通站点会话保护；公开的 `/app/new/login` 调用现有
`/api/auth/login`，由工作台后端向数字人账号中心验证账号并把令牌保存在 HTTP-only
Cookie 中。前端只通过 `/api/auth/session` 读取用户摘要，通过 `/api/auth/logout`
退出，不得读取或保存数字人访问令牌。

任务和批次会同时涉及 SQLite 元数据及 `data/web_storage` 下的 JSON/媒体文件。调试数据异常前先停止服务并备份整个 `data/web_storage`，不要只复制或修改 `control.db`。

新版项目 API 只允许普通数字人账号访问，技术管理员会话不能代替普通账号成为项目
所有者。项目详情中的 `allowed_actions` 是页面按钮权限的唯一业务来源；前端不得根据
显示文本或本地定时器自行推进项目状态。当前公共骨架只负责持久化和聚合；新版页面
目前只完成登录、会话、导航和退出，其他原型模拟逻辑按后续模块逐项替换，不会提前调用
MiniMax、RunningHub 或剪映。

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
| 历史开发记录 | `docs/DEVELOPMENT_HISTORY.md` |

遇到文档与代码不一致时，以当前测试、FastAPI `/docs` 和实际入口代码为准，并在修复代码的同一个改动中更新文档。
