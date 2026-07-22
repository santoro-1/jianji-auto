# Web API

## 网页入口

```text
普通用户生成页：http://127.0.0.1:8000/app
管理员登录页：  http://127.0.0.1:8000/admin/login
高级设置页：    http://127.0.0.1:8000/app/advanced
素材管理页：    http://127.0.0.1:8000/app/assets
接口文档：      http://127.0.0.1:8000/docs
```

普通生成页和业务 API 使用管理员在 `/admin` 创建的内测账号。高级设置、素材管理、用户管理、存储清理和接口文档使用管理员账号 `admin / admin123`。停用、删除或重置普通账号密码会立即撤销原会话。

素材管理页读取处理机上的永久素材库，支持重命名、音乐分类、管理标签、启用/停用、预览、移入回收站和恢复。移入回收站只写入 `data/web_storage/asset_admin.json`，不会立即删除素材文件；已停用或已回收的素材不会出现在普通产品页候选项中。

```text
GET    /api/admin/assets
PATCH  /api/admin/assets/{asset_kind}/{asset_identity}
DELETE /api/admin/assets/{asset_kind}/{asset_identity}
POST   /api/admin/assets/{asset_kind}/{asset_identity}/restore
```

启动后端：

```powershell
cd "D:\工作内容\轻盈健\公寓\jyd_plain_json_probe"
D:\Myanaconda\python.exe .\apps\processor\run_web_api.py --host 127.0.0.1 --port 8000
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

打开最小网页前端：

```text
http://127.0.0.1:8000/app
```

## 环境变量

可选：

```powershell
$env:JYD_WEB_STORAGE_ROOT="D:\工作内容\轻盈健\公寓\jyd_plain_json_probe\web_storage"
$env:JYD_TEMPLATE_LIBRARY_ROOT="D:\工作内容\轻盈健\公寓\jyd_plain_json_probe\template_library"
$env:JYD_WEB_DRAFT_ROOT="D:\剪映草稿\JianyingPro Drafts"
$env:JYD_AUDIO_LIBRARY_ROOT="D:\工作内容\轻盈健\公寓\audio_library"
$env:JYD_MEDIA_RETENTION_HOURS="24"
$env:JYD_TEMPLATE_RETENTION_HOURS="48"
$env:JYD_DRAFT_RETENTION_HOURS="48"
$env:JYD_OUTPUT_RETENTION_HOURS="72"
$env:JYD_FAILED_RETENTION_HOURS="24"
$env:JYD_METADATA_RETENTION_DAYS="30"
$env:JYD_CLEANUP_INTERVAL_MINUTES="30"
$env:JYD_ADMIN_USERNAME="admin"
$env:JYD_ADMIN_PASSWORD="请设置强密码"
$env:JYD_ADMIN_SESSION_SECRET="请设置长期固定的随机密钥"
$env:JYD_ADMIN_SESSION_HOURS="12"
$env:JYD_ADMIN_COOKIE_SECURE="false"
$env:JYD_SITE_USERNAME="operator"
$env:JYD_SITE_PASSWORD="自定义操作员密码"
$env:JYD_SITE_SESSION_SECRET="请设置长期固定的操作员会话密钥"
$env:JYD_EXECUTION_MODE="embedded" # 多处理机中央服务改为 agent
$env:JYD_DATABASE_PATH="D:\JydServer\control.db"
$env:JYD_AGENT_TOKEN="请设置长期固定的处理机接入令牌"
$env:JYD_MAX_VIDEO_UPLOAD_BYTES="2147483648"
$env:JYD_MAX_AUDIO_UPLOAD_BYTES="209715200"
$env:JYD_MAX_DRAFT_IMPORT_BYTES="5368709120"
$env:JYD_MAX_ACTIVE_JOBS="500"
```

公网 HTTPS 部署时将 `JYD_ADMIN_COOKIE_SECURE` 设为 `true`。生产环境应显式配置管理员密码和会话密钥，不依赖自动生成文件。

真实导出 MP4 时，建议把 `JYD_WEB_DRAFT_ROOT` 指向剪映实际的 `JianyingPro Drafts` 目录，或者在 render job 的 `output.draft_root` 里显式传入。

## 上传 MP4

上传接口不用 multipart；前端直接把文件二进制作为 body，文件名放到 `filename` 查询参数里，中文文件名需要 URL 编码。

```powershell
$bytes = [System.IO.File]::ReadAllBytes("C:\Users\san\Desktop\测试\1.mp4")
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/media/video?filename=1.mp4" `
  -ContentType "application/octet-stream" `
  -Body $bytes
```

返回：

```json
{
  "media_id": "...",
  "kind": "video",
  "filename": "1.mp4",
  "path": "..."
}
```

音频上传：

```powershell
$bytes = [System.IO.File]::ReadAllBytes("D:\素材\bgm.mp3")
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/media/audio?filename=bgm.mp3" `
  -ContentType "application/octet-stream" `
  -Body $bytes
```

## 音乐库

查看音乐、分类和轮换位置：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/audio-library"
```

网页支持上传单次使用的 BGM、固定选择音乐库中的一首，以及在某个分类内按导入顺序轮换。分类轮换在提交任务时原子地推进游标，并把实际选中的音乐写入任务记录。

## 导入模板

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/templates/import" `
  -ContentType "application/json" `
  -Body '{
    "source_draft_dir": "D:/剪映草稿/JianyingPro Drafts/模板名",
    "template_id": "demo_template",
    "name": "演示模板",
    "replace": false
  }'
```

查看模板：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/templates"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/templates/demo_template"
```

## 提交渲染任务

上传 MP4 模式：

```json
{
  "schema": "jyd.render_job.v1",
  "source": {
    "type": "video",
    "media_id": "上传接口返回的 media_id"
  },
  "output": {
    "draft_root": "D:/剪映草稿/JianyingPro Drafts",
    "skip_export": false
  },
  "captions": {
    "text": "与视频口播对应的完整长文案……",
    "start_us": 0,
    "duration_us": 0,
    "max_chars": 16,
    "style_json_path": "D:/项目/text_style_library/抖音美好体测试.json",
    "font_id": "剪映字体 resource_id",
    "font_path": "D:/项目/font_library/files/字体文件.ttf",
    "font_title": "优设标题黑",
    "size": 15,
    "color": "#FFFFFF",
    "transform_x": 0,
    "transform_y": -0.8,
    "line_max_width": 0.82
  },
  "texts": [],
  "audios": [
    {
      "type": "add",
      "library_category_id": "分类 ID，也可以改用 media_id 或 library_identity",
      "target_start_us": 0,
      "target_duration_us": 0,
      "fit_to_video": true,
      "volume": 0.3
    }
  ],
  "effects": [],
  "export": {
    "resolution": "1080P",
    "framerate": "30fps",
    "timeout": 1200
  }
}
```

字体与字幕样式是两类独立素材：

```text
GET /api/assets/fonts        读取 font_library/manifest/font_manifest.json
GET /api/assets/text-styles  读取 text_style_library/*.json
GET /api/assets/fonts/{font_identity}/file  返回字体文件，用于网页预览
```

剪辑母版仅更换普通字幕字体时使用 `existing_text_font`。它只更新字体引用，不修改字幕内容、时间、字号、颜色、描边和位置，也不会处理复合文字模板：

```json
{
  "existing_text_font": {
    "font_id": "剪映字体 resource_id",
    "font_path": "D:/项目/font_library/files/字体文件.ttf",
    "font_title": "优设标题黑"
  }
}
```

模板库模式：

```json
{
  "schema": "jyd.render_job.v1",
  "source": {
    "type": "template",
    "template_id": "demo_template"
  },
  "output": {
    "draft_root": "D:/剪映草稿/JianyingPro Drafts",
    "skip_export": false
  },
  "texts": [],
  "audios": [],
  "effects": []
}
```

提交：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/render" `
  -ContentType "application/json" `
  -Body (Get-Content ".\examples\render_job_video.example.json" -Raw)
```

查询任务：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/jobs/{job_id}"
```

下载 MP4：

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/api/jobs/{job_id}/download" `
  -OutFile "D:\输出\result.mp4"
```

`/api/render` 会把任务写入 SQLite 并立即返回 `job_id`。`embedded` 模式由本机内置 worker 顺序执行；`agent` 模式由多台 Windows Agent 原子领取任务。每台 Agent 仍然一次只控制一个剪映窗口。

## 批量排列组合

网页的“批量排列组合”模式会一次上传视频，再按通用素材维度生成子任务。BGM、视频特效、花字和复合文字模板都支持三种模式：

- `disabled`：不使用，不参与任务数量计算。
- `fixed`：固定使用一个候选项，应用到每个子任务。
- `product`：所选候选项参与笛卡尔积。

例如固定 1 首 BGM，选择 10 个视频特效和 5 个花字参与组合，会创建 `10 × 5 = 50` 个独立子任务：

```text
POST /api/render/batch
GET  /api/batches/{batch_id}
```

请求结构：

```json
{
  "job": {
    "schema": "jyd.render_job.v1",
    "source": {"type": "video", "media_id": "video-media-id"},
    "output": {"skip_export": false},
    "texts": [],
    "videos": [],
    "export": {"resolution": "1080P", "framerate": "30fps"}
  },
  "dimensions": [
    {
      "key": "bgm",
      "label": "BGM",
      "mode": "fixed",
      "candidates": [
        {
          "id": "music_id:1",
          "label": "固定音乐",
          "append": {
            "audios": [{"type": "add", "library_identity": "music_id:1", "volume": 0.3}]
          }
        }
      ]
    },
    {
      "key": "video_effect",
      "label": "视频特效",
      "mode": "product",
      "candidates": [
        {
          "id": "effect-1",
          "label": "特效 1",
          "append": {"effects": [{"effect_json_path": "D:/项目/effect_library/特效1.json"}]}
        },
        {
          "id": "effect-2",
          "label": "特效 2",
          "append": {"effects": [{"effect_json_path": "D:/项目/effect_library/特效2.json"}]}
        }
      ]
    }
  ],
  "max_jobs": 500
}
```

候选项的 `patch` 用于覆盖任务字段，`append` 用于向 `audios`、`effects`、`texts`、`text_templates` 等数组追加内容。固定维度必须且只能有一个候选项；参与组合的维度至少有一个候选项。每个子任务会生成唯一草稿名、MP4 输出路径和所选维度摘要。

当前默认单批上限为 500 个子任务。旧版 `music + effects` 请求结构暂时兼容。批量表示自动连续处理；一台电脑上的剪映 worker 仍然逐个导出，不会同时操控多个剪映窗口。

批次状态会返回 `counts.cancelled`、`average_job_seconds` 和 `estimated_remaining_seconds`。完成首个任务后，网页会按本批次实际平均耗时估算剩余时间。结果中心使用以下接口：

```text
POST /api/batches/{batch_id}/cancel
POST /api/batches/{batch_id}/retry-failed
POST /api/batches/{batch_id}/downloads
POST /api/batches/{batch_id}/delete-outputs
GET  /api/batch-downloads/{download_id}
```

- `cancel` 只取消尚未启动的任务，正在处理的任务会继续完成。
- `retry-failed` 把失败项复制到一个新批次，并重新生成任务 ID、草稿名和 MP4 路径。
- `downloads` 接收 `{"job_ids": ["..."]}`，生成一次性 ZIP；下载响应结束后服务器会删除 ZIP 临时文件。
- `delete-outputs` 接收相同结构，只删除 `storage_root/outputs` 下的 MP4 和 `default_draft_root` 下的生成草稿，不删除输入视频、母版或素材库。

## 存储生命周期

管理员可以在生产页“最近任务”中永久删除已经结束的测试批次。删除会同步清理该批次的任务记录、输出 MP4、生成草稿和受管临时目录；排队中或运行中的批次不能删除。

音乐、特效、字体、花字、复合文字和贴纸素材库属于永久数据。通过本地采集器上传的剪辑母版默认保留 48 小时；网页上传的视频、临时音频、输出 MP4、程序生成草稿和批量 ZIP 也属于临时数据：

- 上传素材默认保留 24 小时；排队中或正在运行的任务仍引用该素材时不会删除。
- 成功任务的 MP4 默认保留 72 小时。
- 成功、失败或取消任务在处理机剪映目录中生成的草稿统一保留 48 小时；草稿和 MP4 独立计时、独立清理。
- 失败或取消任务的其他临时结果默认保留 24 小时。
- ZIP 下载响应结束后立即删除；没有下载的遗留 ZIP 最多保留 24 小时。
- 任务和批次 JSON 元数据默认保留 30 天，之后整批删除。
- 服务每 30 分钟扫描一次。升级前的旧记录第一次只补到期时间，从升级时重新开始计时，不会立即删除。

查看占用与策略、手动扫描或只预演清理：

```text
GET  /api/storage
POST /api/storage/cleanup                 body: {}
POST /api/storage/cleanup                 body: {"dry_run": true}
```

清理器只删除本地采集器上传且已到期、未被运行中任务使用的剪辑母版，不删除内置或管理员手动导入的永久模板，也不会删除音乐库、特效库、字体、花字、复合文字模板或贴纸库。

长文案切分预览使用与渲染任务相同的后端算法：

```text
POST /api/captions/preview
```

普通用户页把字体与字幕样式分开：剪辑母版只选择字体；上传 MP4 时可选择字体，并单独设置基础样式、字号、颜色和位置。字体来自 `font_library`，完整字幕样式来自 `text_style_library`。

注意：SQLite 只能由一个中央 API 实例访问，启动后端时不要配置多个 uvicorn workers，也不要让 Agent 直接打开数据库文件。多处理机接口和部署方法见 [MULTI_PROCESSOR.md](MULTI_PROCESSOR.md)。

## 网页测试顺序

1. 启动后端并打开 `http://127.0.0.1:8000/app`。
2. 确认右上角显示“后端已连接”。
3. 选择 MP4 视频文件；需要套模板时勾选“套用模板”并选择模板。
4. 模板只作为可选加工方式，上传的 MP4 会自动替换第一个普通视频片段或第一个嵌套视频槽。
5. 输入长文案，选择字体样式，调整字号、颜色、最大宽度和位置，检查切分及视频叠加预览。
6. BGM 可选择分类内顺序轮换、固定音乐库素材、临时上传或不添加；这些配置与模板使用同一份渲染任务。
7. 第一次建议勾选“只生成草稿，不导出 MP4”，点击“开始生成”并确认状态为 `completed`。
8. 第二次取消勾选，并确保剪映已打开且停在草稿首页，再测试真实 MP4 导出。

网页始终以上传 MP4 为入口。文字样式来自 `text_style_library/*.json`，特效来自 `effect_library/*.json`；模板库管理只负责扫描、解密和导入剪映草稿。未勾选模板时从 MP4 新建草稿，勾选模板时先替换模板视频，再统一添加字幕、BGM 和特效。
## 服务器草稿扫描

网页模板库区域会调用 `/api/drafts` 扫描服务器电脑上的剪映草稿目录：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/drafts?root=D:/剪映草稿/JianyingPro%20Drafts"
```

返回里的 `plain_json=false` 表示这个草稿可能是高版本加密草稿；导入模板库时会自动调用解密流程。
