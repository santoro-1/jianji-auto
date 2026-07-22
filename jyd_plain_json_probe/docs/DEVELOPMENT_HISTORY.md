# pyJianYingDraft 明文草稿最小验证项目

当前依赖版本为 `pyJianYingDraft 0.3.0`。项目通过内部轨道创建兼容层同时支持 `0.2.7`，但生产环境应按 `requirements.txt` 固定到 `0.3.0`，避免 GitHub 主分支后续公共接口变化直接影响渲染服务。

`0.3.0` 的 `DraftFolder.fallback_loader` 只是外部草稿读取器接口，不包含解密实现。本项目仍保留 `jy-draftc -> 明文 JSON -> pyJianYingDraft` 的模板处理链路。

这个目录是第一阶段验证壳项目，不修改 pyJianYingDraft 源码。目标是验证：剪映 5.9 及以下明文 `draft_content.json` 能否被读取、识别结构、做最小字段替换，并保存成一个新的完整草稿目录。

## 项目结构

```text
jyd_plain_json_probe/
  requirements.txt          # 从 GuanYixuan/pyJianYingDraft.git 安装依赖
  run_probe.py              # Python 入口
  run_probe.ps1             # 固定使用 D:\Myanaconda\python.exe 的 PowerShell 入口
  simple_job.py             # 程序化调用示例，后续业务程序优先参考这个
  export_text_style.py      # 从参考文本片段导出字体/颜色/下划线等样式 JSON
  src/jyd_probe/cli.py      # 核心验证流程和最小替换逻辑
  src/jyd_probe/content_replace.py  # 程序化替换 API
```

## 验证流程

1. 用 `D:\Myanaconda\python.exe` 安装并导入 pyJianYingDraft。
2. 读取模板草稿目录里的明文 `draft_content.json`。
3. 统计 `tracks`、视频片段、音频片段、文本片段、特效轨道、`materials.video_effects` 等基础结构。
4. 用 pyJianYingDraft 加载原模板，确认模板模式可读。
5. 复制整个模板草稿目录到新的 output draft 目录，不覆盖原草稿。
6. 在输出副本上执行最小修改，可选：
   - `--replace-first-text` 替换第一条文本轨道的第一个文本片段。
   - `--replace-video-path` 按素材名替换视频/图片素材。
   - `--replace-audio-path` 按素材名替换音频素材。
   - `--first-video-target-duration-us` 修改第一条视频轨道第一个片段的目标时长。
   - `--dump-effects` 输出特效轨道和 `materials.video_effects` 的详细关联。
   - `--replace-first-effect-from-source` 从另一个来源草稿移植第一个视频特效到当前模板的第一个特效占位。
   - `--export-first-effect-json` 把剪映中选好的特效导出成可复用 JSON 文件。
   - `--add-effect-json-to-video` 把已导出的特效 JSON 添加到任意目标视频片段上。
   - `--replace-video-segment-path` 只替换指定视频轨道/片段的素材。
   - `--replace-audio-segment-path` 只替换指定音频轨道/片段的素材。
   - `--add-audio-path` 新增一条音乐轨道。
   - `--replace-text` 替换指定文本轨道/片段，并可改开始时间和持续时间。
7. 调用 `script.save()` 保存输出副本。
8. 再次读取输出副本 JSON，并再次用 pyJianYingDraft 加载，确认基础读写链路通过。
9. 人工在剪映中打开新草稿，确认剪映兼容性。

说明：程序能验证 JSON 明文读取、pyJianYingDraft 模板模式加载、修改、保存、再加载；“剪映正常打开”这一步仍需要你把 `--output-root` 指向剪映的 `JianyingPro Drafts` 目录，然后在剪映里手动打开确认。

## 安装

在本目录运行：

```powershell
D:\Myanaconda\python.exe -m pip install -r .\requirements.txt
```

如果你已经在该 Anaconda 环境里安装过 pyJianYingDraft，也可以直接运行验证脚本。

## 最小运行：只复制、读取、统计、保存

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts"
```

## Python 程序调用

主流程建议用 Python 程序调用，不再拼 PowerShell 参数。直接改 `simple_job.py` 顶部配置后运行：

```powershell
D:\Myanaconda\python.exe .\simple_job.py
```

核心入口是：

```python
from jyd_probe.content_replace import ContentReplaceJob, NestedVideoReplacement, run_content_replace_job

job = ContentReplaceJob(
    template_draft_dir=r"D:\剪映草稿\JianyingPro Drafts\模板测试2",
    output_root=r"D:\剪映草稿\JianyingPro Drafts",
    nested_video_replacements=[
        NestedVideoReplacement(
            media_path=r"D:\素材\new_image_01.png",
            nested_draft_index=0,
            video_track_index=0,
            segment_index=0,
        ),
        NestedVideoReplacement(
            media_path=r"D:\素材\new_image_02.png",
            nested_draft_index=0,
            video_track_index=0,
            segment_index=1,
        ),
    ],
)

result = run_content_replace_job(job)
print(result.output_dir)
```

## 本地闭环：输入视频并导出 MP4

如果目标是模拟网站流程，可以先用 `local_mp4_loop.py` 跑一个本地闭环：

1. 准备一个模板草稿，放在剪映的 `JianyingPro Drafts` 目录里。
2. 准备一个要替换进去的原始视频。
3. 先生成新草稿并检查结构。
4. 再让剪映自动导出 MP4。

`local_mp4_loop.py` 会先检查模板草稿里的 `draft_content.json`。如果已经是明文 JSON，就直接继续；如果是高版本剪映加密格式，会先把整个模板草稿复制到 `jyd_plain_json_probe/_decrypted_work`，再调用同级项目里的 `jy-draftc.exe` 解密这个工作副本，原模板草稿不会被改动。

如果 `jy-draftc/.env` 里配置的剪映版本不对，可以在命令里显式传入：

```powershell
  --jy-install-dir "D:\剪映安装目录\JianyingPro\版本号"
```

这个目录下面必须能找到 `videoeditor.dll`。调试时也可以加 `--jy-draftc-debug`；如果确实想关闭自动解密，才加 `--no-auto-decrypt`。

如果没有模板草稿，只是网页上传一个 MP4，也可以让脚本先自动创建基础剪映草稿，再继续添加文字、音乐、特效：

```powershell
D:\Myanaconda\python.exe .\local_mp4_loop.py `
  --source-kind video `
  --input-video "D:\素材\input.mp4" `
  --draft-root "D:\剪映草稿\JianyingPro Drafts" `
  --output-mp4 "D:\输出\result.mp4" `
  --text-mode add `
  --text "新的标题文案" `
  --text-style-json "D:\工作内容\轻盈健\公寓\text_style_library\抖音美好体测试.json" `
  --effect-json "D:\工作内容\轻盈健\公寓\effect_library\流星雨.json" `
  --resolution 1080P `
  --framerate 30fps `
  --skip-export
```

这条链路会先在 `jyd_plain_json_probe/_generated_video_drafts` 里生成一个临时基础草稿，再复制成最终草稿。因为这是程序新建的明文草稿，所以不需要解密。真正导出 MP4 时，`--draft-root` 应该指向剪映实际的 `JianyingPro Drafts` 目录。

注意：`source-kind=video` 创建的是“单条视频基础草稿”。这种模式下没有原始文字轨道和音乐轨道，所以文字、音乐通常用 `add`，不要用 `replace`。如果要复用复杂模板版式、转场、占位和预设节奏，仍然应该使用模板草稿模式。

第一次建议先跳过导出，只确认草稿能生成：

```powershell
D:\Myanaconda\python.exe .\local_mp4_loop.py `
  --template-draft-dir "D:\剪映草稿\JianyingPro Drafts\模板草稿名" `
  --input-video "D:\素材\input.mp4" `
  --output-mp4 "D:\输出\result.mp4" `
  --target-kind video-segment `
  --video-track-index 0 `
  --video-segment-index 0 `
  --skip-export
```

如果是复合模板内部的图片/视频占位，先 dump 结构：

```powershell
D:\Myanaconda\python.exe .\local_mp4_loop.py `
  --template-draft-dir "D:\剪映草稿\JianyingPro Drafts\模板草稿名" `
  --input-video "D:\素材\input.mp4" `
  --output-mp4 "D:\输出\result.mp4" `
  --target-kind nested-video `
  --dump-nested-drafts `
  --skip-export
```

确认下标后，真正导出 MP4 前需要先手动打开剪映，并停在草稿首页：

```powershell
D:\Myanaconda\python.exe .\local_mp4_loop.py `
  --template-draft-dir "D:\剪映草稿\JianyingPro Drafts\模板草稿名" `
  --input-video "D:\素材\input.mp4" `
  --output-mp4 "D:\输出\result.mp4" `
  --target-kind nested-video `
  --nested-draft-index 0 `
  --nested-video-track-index 0 `
  --nested-video-segment-index 0 `
  --text "新的标题文案" `
  --text-style-json "D:\工作内容\轻盈健\公寓\text_style_library\抖音美好体测试.json" `
  --effect-json "D:\工作内容\轻盈健\公寓\effect_library\流星雨.json" `
  --resolution 1080P `
  --framerate 30fps
```

说明：MP4 导出依赖 pyJianYingDraft 的 `JianyingController` 自动控制剪映界面，目前只适合本机单任务或队列执行。剪映必须已经打开，窗口标题应为“剪映专业版”，并且账号/会员权限要允许导出草稿中使用的素材和效果。

## 检查模板并用任务 JSON 执行

后续做网页时，推荐先检查模板，让后端把可替换位置返回给网页：

```powershell
D:\Myanaconda\python.exe .\inspect_draft.py `
  --draft-dir "D:\剪映草稿\JianyingPro Drafts\用来测试" `
  --output "D:\输出\用来测试_inspect.json"
```

`inspect_draft.py` 和 `local_mp4_loop.py` 使用同一套自动解密参数，所以网页端拿模板结构、后端生成新草稿/导出 MP4 时都可以直接传原始草稿目录。

检查结果会包含：
- `targets.text_segments`：顶层文字片段。
- `targets.nested_text_segments`：复合模板内部文字片段。
- `targets.audio_segments`：已有音乐/音频片段。
- `targets.effect_apply_video_segments`：可以挂特效的顶层视频片段。
- `libraries.text_styles`：当前 `text_style_library` 里的样式。
- `libraries.effects`：当前 `effect_library` 里的特效。

只改文字、音乐和特效时，可以复制并修改示例任务：

```text
jyd_plain_json_probe/examples/text_audio_effect_job.example.json
jyd_plain_json_probe/examples/add_text_audio_effect_job.example.json
```

文字支持两种模式：

```json
{
  "type": "replace",
  "scope": "top",
  "track_index": 0,
  "segment_index": 0,
  "text": "替换已有文字",
  "style_json_path": "D:/工作内容/轻盈健/公寓/text_style_library/抖音美好体测试.json"
}
```

```json
{
  "type": "add",
  "scope": "top",
  "track_name": "auto_title",
  "text": "新增一条文字",
  "start_us": 0,
  "duration_us": 5000000,
  "style_json_path": "D:/工作内容/轻盈健/公寓/text_style_library/抖音美好体测试.json"
}
```

音乐支持三种模式：

```json
{
  "type": "add",
  "media_path": "D:/素材/music.mp3",
  "target_start_us": 0,
  "target_duration_us": 0
}
```

```json
{
  "type": "replace-segment",
  "media_path": "D:/素材/music.mp3",
  "track_index": 0,
  "segment_index": 0,
  "source_start_us": -1,
  "source_duration_us": 0,
  "target_start_us": -1,
  "target_duration_us": 0
}
```

```json
{
  "type": "replace-named",
  "media_path": "D:/素材/music.mp3",
  "material_name": ""
}
```

先不导出，只生成草稿验证：

```powershell
D:\Myanaconda\python.exe .\local_mp4_loop.py `
  --job ".\examples\text_audio_effect_job.example.json"
```

如果要真实导出，把任务 JSON 里的 `skip_export` 改成 `false`，并确保剪映已经打开且停在草稿首页。

## 后端任务入口：render_job.py

后续网站后端优先调用 `src/jyd_probe/render_job.py`，不要再拼 PowerShell 参数。稳定任务格式见：

```text
jyd_plain_json_probe/RENDER_JOB_SCHEMA.md
jyd_plain_json_probe/examples/render_job_video.example.json
jyd_plain_json_probe/examples/render_job_template.example.json
```

Python 调用：

```python
from jyd_probe.render_job import run_render_job_file

result = run_render_job_file("job.json")
print(result.as_dict())
```

命令行调试：

```powershell
D:\Myanaconda\python.exe .\run_render_job.py --job .\examples\render_job_video.example.json
```

`source.type="video"` 表示用户上传 MP4，脚本会直接创建低版本明文基础草稿，不需要解密。`source.type="template"` 表示套用剪映模板，模板如果是高版本加密草稿，会先自动解密到工作副本；后续更适合把解密后的模板做成模板库缓存，渲染时直接拿缓存模板复制。

## 模板库

把模板导入模板库：

```powershell
D:\Myanaconda\python.exe .\manage_templates.py import `
  --source-draft-dir "D:\剪映草稿\JianyingPro Drafts\模板名" `
  --template-id "demo_template" `
  --name "演示模板"
```

如果源模板是高版本加密草稿，导入时会自动解密并缓存成明文模板。默认模板库存放在：

```text
jyd_plain_json_probe/template_library
```

查看模板列表：

```powershell
D:\Myanaconda\python.exe .\manage_templates.py list
```

查看某个模板：

```powershell
D:\Myanaconda\python.exe .\manage_templates.py show --template-id demo_template
```

渲染时使用模板库：

```json
{
  "source": {
    "type": "template",
    "template_id": "demo_template"
  }
}
```

`ContentReplaceJob` 当前支持在同一次处理中执行：

- `NestedVideoReplacement`：替换复合模板内部图片/视频。
- `VideoSegmentReplacement`：替换普通顶层视频轨道里的指定片段。
- `TextReplacement`：替换指定文本片段，并可调出现时间。
- `TextFontReplacement`：替换顶层已有文本片段的字体。
- `NestedTextFontReplacement`：替换复合模板内部已有文本片段的字体。
- `TextStylePresetReplacement`：把导出的文本样式 JSON 应用到顶层已有文本片段。
- `NestedTextStylePresetReplacement`：把导出的文本样式 JSON 应用到复合模板内部已有文本片段。
- `AudioAddition`：新增一条音乐轨道。
- `EffectAddition`：把已导出的特效 JSON 添加到目标视频片段上。

命令行脚本 `run_probe.ps1` 仍保留，主要用于临时调试和快速 dump 结构。

常用参数含义：

| 参数 | 含义 |
| --- | --- |
| `template_draft_dir` | 原模板草稿目录；可以是明文草稿，也可以是高版本加密草稿，脚本会自动解密到工作副本。 |
| `output_root` | 新草稿输出父目录，通常是剪映的 `JianyingPro Drafts`。 |
| `output_name` | 新草稿文件夹名；留空自动生成，不覆盖原草稿。 |
| `media_path` | 新素材路径；图片、视频、音频都用这个字段传入对应文件。 |
| `font_name` | pyJianYingDraft 字体名，例如 `文轩体`、`HarmonyOS_Sans_SC_Regular`、`SourceHanSansCN_Regular`。 |
| `font_id` | 剪映字体资源 id；如果已从模板库记录到字体 id，可以用它代替 `font_name`。 |
| `font_path` | 写入 JSON 的字体 path 字段，普通剪映字体保持默认 `D:`。 |
| `nested_draft_index` | 复合模板内部草稿下标，对应日志 `materials.drafts[*].draft`，通常是 `0`。 |
| `video_track_index` | 视频轨道下标。嵌套替换时对应日志 `nested video track[...]`；普通替换时对应顶层 `type="video"` 轨道。 |
| `text_track_index` | 嵌套草稿内部文本轨道下标，只统计嵌套草稿内 `type="text"` 的轨道，从 `0` 开始。 |
| `track_index` | 文本/音频/普通视频等顶层轨道下标，只统计同类型轨道，从 `0` 开始。 |
| `segment_index` | 目标轨道里的片段下标，从 `0` 开始。 |
| `source_start_us` | 从新素材第几微秒开始截取；`-1` 表示默认。 |
| `source_duration_us` | 从新素材截取多长；`0` 表示默认。 |
| `target_start_us` / `start_us` | 放到时间线上的开始时间；`-1` 表示不改或跟随目标片段。 |
| `target_duration_us` / `duration_us` | 放到时间线上的持续时间；`0` 表示不改或跟随目标片段。 |

时间单位都是微秒：`1_000_000` 表示 1 秒，`2_200_000` 表示 2.2 秒。

替换已有文本字体示例：

```python
from jyd_probe.content_replace import ContentReplaceJob, TextFontReplacement, run_content_replace_job

job = ContentReplaceJob(
    template_draft_dir=r"D:\剪映草稿\JianyingPro Drafts\文本模板",
    output_root=r"D:\剪映草稿\JianyingPro Drafts",
    text_font_replacements=[
        TextFontReplacement(
            font_name="文轩体",
            track_index=0,
            segment_index=0,
        ),
    ],
)

run_content_replace_job(job)
```

如果文字在复合模板内部，用嵌套版本：

```python
from jyd_probe.content_replace import ContentReplaceJob, NestedTextFontReplacement, run_content_replace_job

job = ContentReplaceJob(
    template_draft_dir=r"D:\剪映草稿\JianyingPro Drafts\模板草稿",
    output_root=r"D:\剪映草稿\JianyingPro Drafts",
    nested_text_font_replacements=[
        NestedTextFontReplacement(
            font_name="文轩体",
            nested_draft_index=0,
            text_track_index=0,
            segment_index=0,
        ),
    ],
)

run_content_replace_job(job)
```

更稳的做法是先从剪映里做一个“参考文本”，再导出整套文本样式。它会记录字体、颜色、字号、下划线、描边、阴影、对齐、位置等 JSON 字段。

第一步：改 `export_text_style.py` 顶部配置，然后运行：

```powershell
D:\Myanaconda\python.exe .\export_text_style.py
```

第二步：在 `simple_job.py` 里应用这个样式：

```python
from jyd_probe.content_replace import ContentReplaceJob, TextStylePresetReplacement, run_content_replace_job

job = ContentReplaceJob(
    template_draft_dir=r"D:\剪映草稿\JianyingPro Drafts\目标草稿",
    output_root=r"D:\剪映草稿\JianyingPro Drafts",
    text_style_preset_replacements=[
        TextStylePresetReplacement(
            style_json_path=r"D:\工作内容\轻盈健\公寓\text_style_library\style_01.json",
            text="新的文字内容",
            apply_clip=True,
            track_index=0,
            segment_index=0,
        ),
    ],
)

run_content_replace_job(job)
```

如果目标文字在复合模板内部，用：

```python
NestedTextStylePresetReplacement(
    style_json_path=r"D:\工作内容\轻盈健\公寓\text_style_library\style_01.json",
    text="新的文字内容",
    apply_clip=True,
    nested_draft_index=0,
    text_track_index=0,
    segment_index=0,
)
```

## 推荐首测：替换第一条文本

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceFirstText "第一阶段 pyJianYingDraft 明文草稿替换验证"
```

运行成功后，日志最后会输出新草稿完整目录。打开剪映，刷新草稿列表或重启剪映，再打开这个新草稿检查文本是否变更。

## 替换视频或音频素材

默认替换草稿里的第一个同类素材：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceVideoPath "D:\素材\new_video.mp4"
```

如果草稿里有多个素材，建议显式指定原素材名：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceVideoMaterialName "old_video.mp4" `
  -ReplaceVideoPath "D:\素材\new_video.mp4"
```

音频同理使用 `-ReplaceAudioMaterialName` 和 `-ReplaceAudioPath`。

## 按片段替换视频

如果一个草稿里同一条视频轨道有多个片段，可以通过轨道下标和片段下标指定其中一个：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceVideoSegmentPath "D:\素材\new_video.mp4" `
  -TargetVideoTrackIndex 0 `
  -TargetVideoSegmentIndex 2
```

这个例子只替换第 0 条视频轨道里的第 2 个视频片段，也就是第三个片段。不会影响同一个素材在其它片段里的引用。

可以同时控制素材截取范围和时间线范围：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceVideoSegmentPath "D:\素材\new_video.mp4" `
  -TargetVideoTrackIndex 0 `
  -TargetVideoSegmentIndex 2 `
  -VideoSourceStartUs 1000000 `
  -VideoSourceDurationUs 3000000 `
  -VideoTargetStartUs 5000000 `
  -VideoTargetDurationUs 3000000
```

单位是微秒，`1000000` 表示 1 秒。`StartUs=-1` 表示不改开始时间，`DurationUs=0` 表示不改持续时间。

## 模板内部图片/视频替换

如果日志里顶层只有 1 条视频轨道、1 个视频片段，但剪映界面里能“替换模板图片”，说明它通常是复合模板片段。真正的图片/视频在 `materials.drafts[*].draft` 这个嵌套草稿里面。

第一步先打印内部结构，找到要替换的内部轨道和片段下标：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\剪映草稿\JianyingPro Drafts\模板测试1" `
  -OutputRoot "D:\剪映草稿\JianyingPro Drafts" `
  -DumpNestedDrafts
```

日志会出现类似：

```text
nested video track[0] raw_track_index=0 ...
nested video segment[track=0, segment=0] material=(name='xxx.jpg', ...)
nested video track[1] raw_track_index=2 ...
nested video segment[track=1, segment=0] material=(name='yyy.png', ...)
```

第二步按内部下标替换。下面表示：替换第 0 个嵌套草稿里，第 1 条内部视频轨道的第 0 个片段：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\剪映草稿\JianyingPro Drafts\模板测试1" `
  -OutputRoot "D:\剪映草稿\JianyingPro Drafts" `
  -DumpNestedDrafts `
  -ReplaceNestedVideoSegmentPath "D:\素材\new_image.png" `
  -TargetNestedDraftIndex 0 `
  -TargetNestedVideoTrackIndex 1 `
  -TargetNestedVideoSegmentIndex 0
```

这类替换会保留模板里原片段的裁剪、缩放、位置、动画、蒙版和特效引用，只更新该内部素材的本地文件路径、名称、宽高、时长和素材类型。输出仍然是新的草稿目录，不覆盖原模板。

## 文本片段

替换指定文本片段，并控制出现时间：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceText "新的字幕内容" `
  -TargetTextTrackIndex 0 `
  -TargetTextSegmentIndex 1 `
  -TextStartUs 2000000 `
  -TextDurationUs 4000000
```

## 音乐测试

如果模板里已经有音频片段，可以按轨道/片段替换它：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -ReplaceAudioSegmentPath "D:\素材\music.mp3" `
  -TargetAudioTrackIndex 0 `
  -TargetAudioSegmentIndex 0 `
  -AudioSourceStartUs 10000000 `
  -AudioSourceDurationUs 8000000 `
  -AudioTargetStartUs 3000000 `
  -AudioTargetDurationUs 8000000
```

这个例子表示：从音乐素材第 10 秒开始截取 8 秒，放到时间线第 3 秒，持续 8 秒。

如果模板里没有音频轨道，可以直接新增一条音乐轨道：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -AddAudioPath "D:\素材\music.mp3" `
  -AudioTargetStartUs 0 `
  -AudioTargetDurationUs 5000000
```

## 特效测试

特效建议分两步测。

第一步只观察结构。先在模板草稿里加一个视频特效，然后运行：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\业务模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -DumpEffects
```

日志会打印：

- `materials.video_effects` 里的特效素材。
- `tracks[type='effect']` 里的特效轨道和片段。
- 每个特效片段的 `material_id` 对应到了哪个 `video_effects[id]`。

第二步测试特效移植。准备两个草稿：

- 业务模板草稿：放正常视频/文本，并放一个任意视频特效作为“占位特效”。
- 特效来源草稿：只需要放一个你真正想移植的目标视频特效。

然后运行：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\业务模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -DumpEffects `
  -EffectSourceDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\特效来源草稿名" `
  -ReplaceFirstEffectFromSource
```

这个测试会复制业务模板草稿到新的输出草稿，然后把来源草稿的第一个 `materials.video_effects` 写到输出草稿第一个特效占位的 material id 上。特效片段的时间范围、轨道位置、开始结束时间都保留业务模板里的设置。

## 特效库主流程

如果你的目标是“在剪映里找到特效，记录 JSON，然后批量加到其它视频上”，用这一套。

第一步：在剪映里新建一个“特效来源草稿”，放一个视频并加上你要的特效。然后导出特效 JSON：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\特效来源草稿名" `
  -DumpEffects `
  -ExportFirstEffectJson "D:\工作内容\轻盈健\公寓\effect_library\example_effect.json"
```

导出的 JSON 里会保存：

- `material`：`materials.video_effects` 中的特效素材定义。
- `segment_template`：`tracks[type='effect']` 里的特效片段模板。

第二步：把这个特效 JSON 添加到目标草稿的某个视频片段上：

```powershell
.\run_probe.ps1 `
  -TemplateDraftDir "D:\你的剪映草稿目录\JianyingPro Drafts\业务模板草稿名" `
  -OutputRoot "D:\你的剪映草稿目录\JianyingPro Drafts" `
  -EffectJsonPath "D:\工作内容\轻盈健\公寓\effect_library\example_effect.json" `
  -AddEffectJsonToVideo `
  -TargetVideoTrackIndex 0 `
  -TargetVideoSegmentIndex 0 `
  -DumpEffects
```

这会生成一个新的剪映草稿，不覆盖原草稿。脚本会读取目标视频片段的 `target_timerange`，新增一个 `materials.video_effects` 条目，并新增一条 `type="effect"` 的特效轨道，让特效覆盖该视频片段的时间范围。

如果想手动控制特效出现时间，而不是跟随目标视频片段，可以加：

```powershell
  -EffectStartUs 2000000 `
  -EffectDurationUs 3000000
```

## 后续扩展位置

后续要替换特效库时，建议在 `src/jyd_probe/cli.py` 里新增独立函数，例如：

```python
def replace_video_effects_in_json(data, effect_mapping):
    ...
```

优先处理两块结构：

- `materials.video_effects`
- `tracks` 中 `type == "effect"` 的轨道和片段

第一阶段先不要把这部分做复杂。等确认明文草稿能稳定复制、保存、被剪映打开后，再加特效、音乐、字幕、批量任务。
