# 项目目录说明

## 应用和打包边界

```text
apps/
├─ collector/                     用户电脑上的草稿采集端
│  ├─ collector_windows.spec      PyInstaller 配置
│  ├─ run_local_collector.py      源码运行及打包入口
│  └─ frontend/                   采集器网页
└─ processor/                     处理机/Windows 服务器
   ├─ processor_windows.py        打包入口
   ├─ processor_windows.spec      PyInstaller 配置
   ├─ run_web_api.py              源码运行入口
   ├─ processor_config.example.json
   └─ frontend/                   用户页和管理后台
```

## 核心源码、工具和测试

```text
src/jyd_probe/                    共用核心代码
src/jyd_probe/project_store.py    新版统一项目、素材版本、操作和外部批次关联
tests/                            自动测试
examples/                         job.json 示例
tools/library/                    音乐、字体、贴纸、花字等提取工具
tools/draft/                      草稿检查、导入分析和母版管理
tools/jobs/                       旧版单任务及本地闭环工具
tools/probe/                      底层草稿探测工具
```

## 必须随项目迁移的数据

```text
data/libraries/                   永久素材库
data/template_library/            已导入剪辑母版
data/web_storage/                 网站账号、任务、上传记录及输出
vendor/jy-draftc/                 高版本草稿解密程序
```

这些目录已经从项目外部收进项目内部，所以直接压缩整个项目不会再遗漏素材库或解密工具。

## 构建和输出

```text
scripts/build/build_collector.ps1         只构建采集端
scripts/build/build_processor.ps1         只构建处理机
scripts/build/build_all_releases.ps1      构建两个正式发布包
scripts/build/build_portable_project.ps1  构建完整项目迁移包
release/                                  最终 ZIP
```

PyInstaller 环境、`build` 和 `dist` 位于项目同级的 `.jyd-build-cache`。它们不是源码，也不能直接迁移，因此不再放入项目目录。

## 运行期目录

`runtime/` 只保存解密副本、采集器本机状态、测试临时目录和历史开发产物。正式处理机发布包不会把这些临时文件带进去。
