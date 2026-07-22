# 全屏贴纸素材库

全屏贴纸通过一个专用剪映草稿采集。该草稿只放允许自动铺满整段视频的贴纸；局部贴纸不应放入采集草稿。

## 采集

```powershell
D:\Myanaconda\python.exe .\tools\library\export_sticker_library.py `
  --draft-dir "D:\剪映草稿\JianyingPro Drafts\全屏贴纸草稿"
```

工具会自动解密高版本草稿，并把每个贴纸的完整缓存目录复制到工作区 `sticker_library`。再次采集时会按 `resource_id` 去重；需要刷新已有资源时增加 `--replace`。

## 素材结构

每个贴纸包包含：

- `sticker.json`：剪映贴纸素材和片段模板。
- `resources/sticker`：PNG、Lua、JSON 等完整运行资源。
- `preview_file`：从资源目录选出的本地预览图。

普通产品页将素材库中的每个贴纸视为一个组合候选项。每条输出视频只添加一个候选贴纸，开始时间为 0，持续到视频结尾。
