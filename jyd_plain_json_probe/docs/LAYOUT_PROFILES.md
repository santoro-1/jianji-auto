# 新工作台站姿 / 坐姿画面规范

新工作台按任务保存 `settings.postprocess.layout_profile`：

- `standing`：站姿，历史任务和未设置任务的默认值。
- `seated`：坐姿。

前端表格的“姿态”列可以逐条设置；勾选多条任务后，可用批量工具栏的“设为站姿 / 设为坐姿”。切换姿态只清除当前后处理预览和已导出的合成成片，不清除声音、RunningHub 数字人基础视频或原始分段。

两套参数的唯一代码来源是 `src/jyd_probe/layout_profiles.py`。字幕、顶部固定标题、底部免责声明、人名板底图、人名板三行文字和语义图片位置都由该文件统一下发给浏览器预览、成片导出和变体导出。

固定字体为金陵体 `resource_id:7086699209738424840`，文件存放在 `data/libraries/font_library`。人名板底图是从两个规范草稿的剪映缓存中提取的透明 PNG：

- 站姿：`data/libraries/semantic_visual_library/fixed/nameplate_standing`
- 坐姿：`data/libraries/semantic_visual_library/fixed/nameplate_seated`

完整人工提取数值和来源记录见工作区文档 `D:\工作内容\轻盈健\数字人\规范站与规范坐参数提取记录_20260812.md`。
