# 人名板、字幕与顶部固定标题开发文档

日期：2026-08-10

## 目标与基准

本功能以 1080×1920、9:16 竖屏为设计基准，解决三项统一排版问题：放大人名板、放大并上移
字幕、增加可参数化的顶部双行标题。所有位置同时用于浏览器预览、普通剪映成片和模块 6 变体。

人名板参数来自人工调整草稿 `jyd_eab56dad6e7e` 的启用轨道：

- 受控素材：`data/libraries/semantic_visual_library/fixed/nameplate_zhangluo/resources/sticker/singleImage.png`
- `scale=0.7331057670319187`
- `transform_x=-0.26689423296808135`
- `transform_y=-0.22258064516128995`
- `opacity=1.0`，从正文第 1 帧持续到正文结束

字幕参数来自人工参考图：

- 字号 `14`
- `transform_x=0`
- `transform_y=-856/1920=-0.44583333333333336`
- 最大宽度 `0.8`，单行，默认白字与黑色 `0.06` 描边
- 单行参考容量约 `10.21em`；服务端继续按实际字体 glyph advance 断句，不按固定汉字数硬切

## 顶部标题参数契约

标题是后处理设置中的可选对象：

```json
{
  "top_title": {
    "label": "减肥大实话",
    "headline": "只有坚持才能达成目标"
  }
}
```

`label` 是黄色小标题，最多 12 个字符，字号 11，`transform_y=1535/1920`；`headline` 是白色
主标题，最多 20 个字符，字号 13，`transform_y=1350/1920`。两行均水平居中、单行、宽度上限
0.92、黑色 `0.04` 描边。换行和连续空白会被折叠为空格。

两个字段可独立为空；都为空或完全不传 `top_title` 时不创建标题轨道，现有项目不会出现占位文字。
后续文本分析模型只负责生成 `label` 与 `headline`，不能改变字号、颜色、坐标和轨道时长。

## API 与持久化

以下两个入口接受同一 `top_title` 对象：

- `POST /api/new/projects/{project_id}/postprocess/generate` 的 `items[*].top_title`
- `PATCH /api/new/projects/{project_id}/items/{item_id}/postprocess-settings` 的 `top_title`

规范化结果保存在 `item.settings.postprocess.top_title`。后处理请求未携带该字段时保留已存配置；显式
传入两个空字符串才关闭标题。标题设置变化只使最终后处理结果失效，不重新调用语音或 RunningHub。

## 渲染与层级

导出时服务端把非空标题转换成两个全时长 `texts` 新增项，并冻结所选字幕字体。人名板仍是
`fixed_overlays` 图片轨道。视觉层级为：基础画面/特效 < 语义图片/小窗 < 人名板 < 全屏 B-roll <
顶部标题/字幕。封面偏移统一在正文轨道生成后处理，标题和人名板不会显示在 3 帧封面上。

## 验收标准

1. 受控人名板素材与人工草稿启用 PNG 一致，剪映 JSON 的 scale/x/y 与实测值完全一致。
2. 字幕剪映 JSON 为 14 号、Y=-856；浏览器按同一归一化坐标居中显示。
3. 字幕最大宽度保持 80%，较长脚本重新断句且任何 cue 都不换行。
4. 标题为空时没有 `texts` 标题项；非空时两条轨道覆盖完整正文，颜色、字号和 Y 坐标固定。
5. 普通导出与变体任务冻结同一标题、人名板和字幕参数。

封面短标题及其固定视觉参数已独立记录在
[AI_TITLE_AND_COVER_20260810.md](AI_TITLE_AND_COVER_20260810.md)。封面属于项目后处理，不再由模块 6
逐行手工填写。
