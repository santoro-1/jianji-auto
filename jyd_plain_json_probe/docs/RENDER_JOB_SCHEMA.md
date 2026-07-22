# Render Job JSON

当前稳定版本：`jyd.render_job.v1`

后端入口：

```python
from jyd_probe.render_job import run_render_job, run_render_job_file

result = run_render_job_file("job.json")
print(result.as_dict())
```

命令行调试入口：

```powershell
D:\Myanaconda\python.exe .\tools\jobs\run_render_job.py --job .\examples\render_job_video.example.json
```

## 顶层结构

```json
{
  "schema": "jyd.render_job.v1",
  "source": {},
  "output": {},
  "captions": {},
  "texts": [],
  "text_templates": [],
  "audios": [],
  "effects": [],
  "stickers": [],
  "visual_variant": {},
  "export": {}
}
```

## source

上传 MP4 直接生成基础草稿，不需要解密：

```json
{
  "type": "video",
  "media_path": "D:/素材/input.mp4",
  "work_root": "D:/工作目录/generated_video_drafts",
  "canvas": {
    "width": 0,
    "height": 0,
    "fps": 30
  }
}
```

模板模式用于套用已经存在的剪映草稿。模板可能是明文，也可能是高版本加密草稿；加密草稿会按 `decrypt` 配置自动解密到工作副本：

```json
{
  "type": "template",
  "template_draft_dir": "D:/剪映草稿/JianyingPro Drafts/模板名"
}
```

更推荐的生产方式是先把模板导入模板库，然后渲染时只传 `template_id`：

```powershell
D:\Myanaconda\python.exe .\tools\draft\manage_templates.py import `
  --source-draft-dir "D:\剪映草稿\JianyingPro Drafts\模板名" `
  --template-id "demo_template" `
  --name "演示模板"
```

导入后会生成：

```text
jyd_plain_json_probe/data/template_library/demo_template/
  draft/
    draft_content.json
    draft_meta_info.json
  template_meta.json
```

渲染任务里使用：

```json
{
  "type": "template",
  "template_id": "demo_template",
  "library_root": ""
}
```

`library_root` 留空时使用 `jyd_plain_json_probe/template_library`。模板库里的草稿应当已经是明文，所以渲染时不会重复解密。

## output

```json
{
  "draft_root": "D:/剪映草稿/JianyingPro Drafts",
  "draft_name": "",
  "mp4_path": "D:/输出/result.mp4",
  "skip_export": false
}
```

`draft_name` 留空时自动生成。真实导出 MP4 时，`draft_root` 应该是剪映实际的 `JianyingPro Drafts` 目录。

## captions

上传 MP4 时，可以把长文案自动切分为一条字幕轨道上的多个片段：

```json
{
  "text": "与视频口播对应的完整长文案……",
  "start_us": 0,
  "duration_us": 0,
  "max_chars": 16,
  "style_json_path": "D:/项目/text_style_library/抖音美好体测试.json",
  "size": 15,
  "color": "#FFFFFF",
  "transform_x": 0.0,
  "transform_y": -0.8,
  "line_max_width": 0.82
}
```

`duration_us=0` 表示覆盖上传视频从 `start_us` 开始的剩余时长。程序按换行、标点和 `max_chars` 生成 SRT，再通过 `ScriptFile.import_srt` 导入。每条字幕的时间按文字显示宽度比例分配。

`captions` 会在视频替换和其他草稿修改完成后写入最终草稿，因此直接上传 MP4 和“上传 MP4 + 套用模板”两种流程都可使用。`texts` 继续负责单个标题的新增和模板已有文字替换。

## texts

新增文字：

```json
{
  "type": "add",
  "scope": "top",
  "track_name": "auto_title",
  "text": "新的标题",
  "start_us": 0,
  "duration_us": 5000000,
  "style_json_path": "D:/项目/text_style_library/style.json",
  "text_effect_json_path": "D:/项目/text_effect_library/bundles/双描边紫色渐变花字/text_effect.json",
  "apply_clip": true
}
```

`text_effect_json_path` 是可选的花字素材，只应用于这条新增文字。`start_us=0` 表示从视频开头开始，`duration_us=0` 表示从开始时间持续到视频结尾。

替换已有文字：

```json
{
  "type": "replace",
  "scope": "top",
  "track_index": 0,
  "segment_index": 0,
  "text": "替换后的文字",
  "style_json_path": "D:/项目/text_style_library/style.json"
}
```

## text_templates

复合文字模板会复制模板中的多段文字、花字、贴纸和动画资源，并按文字槽顺序替换内容：

```json
{
  "template_json_path": "D:/项目/text_template_library/bundles/新年愿望清单标题模板/text_template.json",
  "texts": [
    "· 一夜暴富\n· 减肥成功\n· 工作顺利\n· 厄运退散",
    "「新年愿望」"
  ],
  "start_us": 0,
  "duration_us": 0,
  "track_name": "new_year_wishes"
}
```

`texts` 按模板元数据里的文字槽顺序对应；少传的槽保留模板原文，显式传空字符串会清空对应槽。`duration_us=0` 同样表示持续到视频结尾。

## audios

给上传 MP4 添加 BGM 时用 `add` 或 `bgm`，不会静音原视频人声：

```json
{
  "type": "add",
  "media_path": "D:/素材/bgm.mp3",
  "target_start_us": 0,
  "target_duration_us": 0,
  "fit_to_video": true,
  "volume": 0.3
}
```

`fit_to_video=true` 且 `target_duration_us=0` 时，BGM 自动覆盖视频剩余时长；如果音乐本身更短，则截到音乐末尾。`volume` 支持 `0.0` 到 `2.0`，网页默认 `0.3`。

通过 Web API 提交时，`media_path` 还可以替换成以下任意一种引用：

```json
{"type": "add", "library_identity": "固定音乐素材 ID", "fit_to_video": true}
```

```json
{"type": "add", "library_category_id": "分类 ID", "selection_mode": "next", "fit_to_video": true}
```

`library_category_id` 会在任务入队时按音乐清单顺序选择下一首并推进持久化游标。`render_job.py` 的直接 Python/命令行入口仍使用已经解析好的 `media_path`。

模板里已有独立音频轨道时，也可以替换指定音频片段：

```json
{
  "type": "replace-segment",
  "media_path": "D:/素材/bgm.mp3",
  "track_index": 0,
  "segment_index": 0
}
```

## effects

```json
{
  "effect_json_path": "D:/项目/effect_library/流星雨.json",
  "target_video_track_index": 0,
  "target_video_segment_index": 0,
  "start_us": -1,
  "duration_us": 0
}
```

`start_us=-1`、`duration_us=0` 表示跟随目标视频片段。

## visual_variant

画面变化套装会先按全局时间轴切开视频片段并交替镜像，再做人脸居中裁剪和纯色画布填充：

```json
{
  "enabled": true,
  "mirror_interval_seconds": 10,
  "crop_ratio": "1:1",
  "background_color": "#000000",
  "face_centered": true,
  "face_sample_count": 3,
  "video_track_index": 0
}
```

`mirror_interval_seconds=10` 表示 `0-10s` 保持原方向、`10-20s` 水平镜像、`20-30s` 再恢复。当前网页提供 `1:1`、`3:4` 两种裁剪比例；底层接受任意合法的 `宽:高` 正数比例。检测不到人脸或视频路径不可读时自动使用画面中心，不中断任务。

## stickers

普通全屏贴纸仍不传 `corner`。四角贴纸为同一个任务追加四项：

```json
[
  {"sticker_json_path": "D:/项目/sticker_library/a/sticker.json", "corner": "top_left", "visible_ratio": 0.05},
  {"sticker_json_path": "D:/项目/sticker_library/b/sticker.json", "corner": "top_right", "visible_ratio": 0.05},
  {"sticker_json_path": "D:/项目/sticker_library/c/sticker.json", "corner": "bottom_left", "visible_ratio": 0.05},
  {"sticker_json_path": "D:/项目/sticker_library/d/sticker.json", "corner": "bottom_right", "visible_ratio": 0.05}
]
```

`visible_ratio` 当前网页可选 `0.05` 或 `0.10`。四角贴纸沿用已采集并打包进贴纸库的资源，不依赖原电脑的剪映缓存绝对路径。

## export

```json
{
  "resolution": "1080P",
  "framerate": "30fps",
  "timeout": 1200
}
```

导出依赖剪映客户端处于打开状态，并停在草稿首页。
