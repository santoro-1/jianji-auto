# 语义视觉素材库维护

语义图片与视频共用同一素材库：

```text
data/libraries/semantic_visual_library/
  catalog.json
  bundles/
  videos/
  fixed/nameplate_zhangluo/
```

`catalog.json` 使用统一图片/视频协议；工作台启动时一次性读取并严格校验目录，
因此修改素材库后必须重启 Processor。`fixed/nameplate_zhangluo` 不属于语义 catalog，作为
每条项目视频的固定人名牌从正文第 1 帧显示到结束，默认位于左侧胸口区域、宽度约占画面
46%；封面 3 帧不显示，也不得引用桌面原始路径。

## 项目行内增加或移除素材

表格“语义视觉”列进入审核窗口：

- “加入本行”把模型候选加入当前脚本行。
- “关闭显示”保留配方但不在预览和成片中显示。
- “移除本行”从当前脚本行配方中移除，不删除本地图库文件。
- 更换素材、位置、时间、缩放、透明度和开关修改均自动切换为人工配方并锁定。
- 图片和视频使用同一占用表；保存时任何启用项时间重叠都会被拒绝。

修改后点击“保存配方”。取消或直接关闭窗口不会写入项目。

## 向整个图库新增图片

素材库存储仍使用完整 bundle，不能只把一张 PNG 随意放进目录。这样目录可整体搬迁、版本可
校验，也能兼容已经冻结的历史项目。新增素材至少包含：

```text
bundles/<新目录>/
  sticker.json
  resources/sticker/singleImage.png
```

`sticker.json` 当前作为 bundle 完整性与历史兼容元数据保留；语义贴图和固定人名牌实际渲染
会把 `resources/sticker/singleImage.png` 写成剪映 `photo` 素材，放在独立视频轨道上，不再写成
剪映贴纸素材。若 `sticker.json` 还引用其他资源，仍须连同整个目录一起复制。然后在
`catalog.json` 的 `assets` 数组增加 catalog v2 项：

```json
{
  "asset_id": "food.egg.new_unique_id",
  "concept_ids": ["food.egg"],
  "name": "新鸡蛋图片",
  "description": "图片内容的简短事实描述",
  "media_type": "image",
  "renderer": "jyd_sticker_bundle",
  "tags": ["食物", "照片"],
  "resource": {
    "bundle": "bundles/<新目录>",
    "preview": "bundles/<新目录>/resources/sticker/singleImage.png"
  },
  "defaults": {
    "corner": "bottom_center",
    "scale": 0.78,
    "opacity": 1.0,
    "duration_us": 1800000
  }
}
```

`asset_id` 必须永久唯一，不能复用旧 ID。若新增概念，还要在 `concepts` 中添加唯一
`concept_id`、名称、描述和非空关键词别名；别名应具体，并按实际语言补齐长词。

## 向素材库新增视频

每条视频使用独立、发布后不覆盖的目录：

```text
videos/<新目录>/
  video.mp4
  poster.png
  metadata.json  # 可选
```

catalog v2 项示例：

```json
{
  "asset_id": "activity.running.video.01",
  "concept_ids": ["activity.running"],
  "name": "户外跑步视频",
  "description": "人物在户外持续跑步的动作画面",
  "media_type": "video",
  "renderer": "video_overlay",
  "tags": ["运动动作", "动态", "可循环"],
  "resource": {
    "video": "videos/<新目录>/video.mp4",
    "preview": "videos/<新目录>/poster.png",
    "metadata": "videos/<新目录>/metadata.json",
    "duration_us": 6000000,
    "width": 1920,
    "height": 1080,
    "has_audio": true
  },
  "defaults": {
    "corner": "center",
    "scale": 1.0,
    "opacity": 1.0,
    "duration_us": 3000000,
    "source_start_us": 0,
    "mute": true,
    "loop": false,
    "fit": "cover"
  }
}
```

`corner=center + scale>=0.95` 作为全屏 B-roll：轨道位于固定人名牌上方、字幕下方，因此会
自然遮住人名牌，不需要隐藏/恢复事件。其他位置作为小窗视频，位于固定人名牌下方。视频默认
静音；动作 concept 在同时存在图片和视频时优先视频，无视频时回退图片。

长视频不必先物理切割。若整段是同一种动作，保留原文件，通过 `source_start_us` 和
`duration_us` 只取适合入镜的区间；若一个文件包含多个动作，可登记多个永久唯一的逻辑
`asset_id`，分别引用同一 `video.mp4` 的不同源区间和标签。只有源文件难以稳定 seek、解码异常
或必须独立发布时，才另行物理切片。

需要作为相关素材或空镜参与 20～30 秒视觉空窗补充时，必须在 `tags` 中显式加入 `空镜`、
`相关素材`、`b-roll`、`broll` 或 `enrichment` 之一。没有这些标签的普通图片/动作素材只会按
明确语义触发。明确语义触发在存在普通素材时不会误选 enrichment 专用素材；空窗补充则只从
上述显式标签的素材中选择。enrichment 候选不会增加第二次模型调用，且每 60 秒最多采用 2 条。

当前默认库包含 37 个概念、40 个资产（38 张图片、2 条视频）。两条视频都从
`D:\迅雷下载\贴图素材-巧如\贴图1\视频素材\腹部核心燃脂操` 复制进入受控库，原文件不修改，
且未导入 `爆款动作.mp4`：

- `activity.aerobic.crotch_clap.video.01`：胯下击掌动作，源片从 0 秒取 4 秒，作为底部中轴小窗，
  供“胯下击掌/有氧操/燃脂操”等明确语义使用。
- `activity.aerobic.core_broll.video.01`：腹部核心燃脂动作，保留 42.766341 秒源文件，从 12 秒
  取 5 秒，作为全屏、带 `相关素材/b-roll/enrichment` 标签的空窗补充素材。

重启前运行：

```powershell
$env:PYTHONPATH='src'
D:\Myanaconda\python.exe -m pytest -q -p no:cacheprovider tests\test_semantic_visuals.py
```

## 从整个素材库停用或删除素材

当前清单没有 `enabled` 字段。要阻止新项目继续选择某项素材，可从 `catalog.json` 的
`assets` 数组移除对应项后重启工作台，但应继续保留原 bundle 目录。历史冻结配方保存了
bundle 路径，提前删除物理目录会让旧项目缺图。

只有确认所有历史项目、历史版本和待执行任务都不再引用该 `asset_id` 后，才能物理删除
bundle。当前 MVP 没有跨全部项目的安全清理界面，因此默认不执行物理删除；需要彻底清理时
应先做引用审计和备份。

## 校验边界

- 路径必须位于语义素材库目录内，不能使用绝对路径或 `..` 越界。
- 每个 bundle 必须存在，预览图片必须存在，且 bundle 根目录必须含 `sticker.json`。
- 图片与小窗视频允许左上、右上、左下、右下、底部居中或居中。`bottom_center` 是口播默认：
  横向与画面中轴对齐，动作视频约占 61.5% 画面宽度；较高的食物图约占 78% 宽度，最多
  显示约 37% 画面高度，超出的底部允许裁出画面。浏览器与剪映使用同一换算。
- `default_scale` 范围是 `0.05` 到 `2.0`；透明度范围是 `0` 到 `1`。
- 视频文件、poster 和可选 metadata 必须都在素材库内；登记的时长、宽高、音轨必须来自实际探测。
- 视频默认 `mute=true`，`fit` 只允许 `cover` 或 `contain`；非循环默认截取不能越过源视频结尾。
- 目录内容变化会改变 `catalog_version`，下一次统一内容分析会使用新候选；已有计划不能误命中
  旧 catalog 缓存，人工锁定项不会被静默覆盖。
