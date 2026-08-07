# 语义前景图片素材库维护

语义前景图片素材库位于：

```text
data/libraries/semantic_visual_library/
  catalog.json
  bundles/
```

当前 MVP 有 6 个概念、7 张图片，其中鸡蛋概念有两张可切换素材。工作台启动时一次性读取
并严格校验目录，因此修改素材库后必须重启 Processor。

## 项目行内增加或移除图片

表格“语义配图”列进入审核窗口：

- “加入本行”把模型候选加入当前脚本行。
- “关闭显示”保留配方但不在预览和成片中显示。
- “移除本行”从当前脚本行配方中移除，不删除本地图库文件。
- 换图、位置、时间、缩放、透明度和开关修改均自动切换为人工配方并锁定。

修改后点击“保存配方”。取消或直接关闭窗口不会写入项目。

## 向整个图库新增图片

当前渲染类型是剪映贴纸包，不支持只把一张 PNG 随意放进目录。新增素材必须准备一个完整、
已验证的 bundle，至少包含：

```text
bundles/<新目录>/
  sticker.json
  resources/sticker/singleImage.png
```

若 `sticker.json` 还引用其他资源，必须连同整个目录一起复制。然后在 `catalog.json` 的
`assets` 数组增加一项：

```json
{
  "asset_id": "food.egg.new_unique_id",
  "concept_id": "food.egg",
  "name": "新鸡蛋图片",
  "bundle": "bundles/<新目录>",
  "image": "bundles/<新目录>/resources/sticker/singleImage.png",
  "default_corner": "top_right",
  "default_scale": 0.28,
  "default_opacity": 1.0
}
```

`asset_id` 必须永久唯一，不能复用旧 ID。若新增概念，还要在 `concepts` 中添加唯一
`concept_id`、名称、描述和非空关键词别名；别名应具体，并按实际语言补齐长词。

重启前运行：

```powershell
$env:PYTHONPATH='src'
D:\Myanaconda\python.exe -m pytest -q -p no:cacheprovider tests\test_semantic_visuals.py
```

## 从整个图库停用或删除图片

当前清单没有 `enabled` 字段。要阻止新项目继续选择某张图片，可从 `catalog.json` 的
`assets` 数组移除对应项后重启工作台，但应继续保留原 bundle 目录。历史冻结配方保存了
bundle 路径，提前删除物理目录会让旧项目缺图。

只有确认所有历史项目、历史版本和待执行任务都不再引用该 `asset_id` 后，才能物理删除
bundle。当前 MVP 没有跨全部项目的安全清理界面，因此默认不执行物理删除；需要彻底清理时
应先做引用审计和备份。

## 校验边界

- 路径必须位于语义素材库目录内，不能使用绝对路径或 `..` 越界。
- 每个 bundle 必须存在，预览图片必须存在，且 bundle 根目录必须含 `sticker.json`。
- `default_corner` 只允许 `top_left` 或 `top_right`。
- `default_scale` 范围是 `0.05` 到 `2.0`；透明度范围是 `0` 到 `1`。
- 目录内容变化会改变 `catalog_version`，自动视觉分析需要重新验证；人工锁定项不会被静默覆盖。
