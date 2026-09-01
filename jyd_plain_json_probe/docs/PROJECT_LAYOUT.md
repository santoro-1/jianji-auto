# 项目目录说明

## 设备授权模块（开发中）

`device_command_authorization.py` 提供固定账号接口登录/验证、隐藏密码或显式标准输入令牌，以及共用的 `account_authorization` 会话。接入正式处理机 `--render-job`、渲染脚本、probe 建草稿和独立 Agent CLI/GUI；只读原密钥、不初始化/登记。其他私有脚本仍待审计，不能从这些模块的存在推断整包已覆盖。

独立 Agent 的模块边界：`device_agent_protocol.py` 定义固定请求上下文和证明；`device_agent_client.py` 请求云端专用许可；`device_agent_gate.py` 验签并一次性消费中央挑战；`device_agent_queue.py` 核对原任务归属和权限。实际 HTTP 在 `device_agent_routes.py`，注册/启动/回报事务在 `device_agent_operations.py`；`device_agent_transport.py` 负责中央安全传输，`device_agent_runtime.py` 负责本机授权执行，`device_agent_journal.py` 保存与程序版本无关的原执行/结果回执。`render_agent.py` 负责 CLI/GUI 接入与生命周期。执行中断的不确定回执尚无完整人工核实恢复工具。

`src/jyd_probe/device_identity_windows.py` 负责机器级 CNG 密钥；`device_auth_protocol.py` 与
`device_trust_roots.py` 负责持钥协议和发布信任根；`device_authorization.py` 负责会话、刷新与
非权威缓存；`device_authorization_routes.py` 提供复用网站账号的本地登记接口。
`device_identity_setup.py` 协调显式初始化/原密钥访问修复；`device_identity_setup_windows.py` 只启动并验证固定 EXE 辅助入口，`device_identity_acl.py` 合并已验证操作用户的原钥匙权限。普通读取和更新不调用提权。
`device_identity_store.py` 维护机器级的非授权性定位记录、原密钥冲突诊断与跨进程初始化互斥锁；`device_software_initialization.py` 校验服务器软件初始化许可，`device_initialization_channel.py` 只向指定辅助进程发送一次许可，不提供通用签名或命令接口。
`device_background_refresh.py` 为既有会话独立后台刷新；`device_h3_recovery_routes.py` 与 `device-h3-recovery.js` 提供 H3 原批次显式补授权，不自动重新生成。
`device_business_transport.py` 将设备会话接到 `auth_center.py` 的已审计 H3 业务路径，防止证明流向第三方或拒绝后降级重发。
`device_local_policy.py` 校验签名本地模式；`device_local_execution.py` 保护建草稿/导出核心；`device_local_web.py` 建立网站账号的内部执行上下文；`device_local_queue.py` 复核内嵌队列、保留授权等待并同步状态文件。
`apps/processor/frontend/new/device-authorization.html/.css/.js` 为账号菜单中的独立激活页面，由 `web_api.py` 的 `/app/new/device-authorization` 提供。
页面同时提供当前账号本地等待任务的显式恢复，不在加载/登录时自动执行。`task_store.py` 在既有状态 JSON 保存非秘密关联，不向任务载荷写入私钥或凭据。
这些模块不属于音视频处理算法。软件兼容初始化及 Agent/三处 CLI 的源码接线与模拟回归已加入；真实 TPM/无 TPM/不同 Windows 用户验证、其他私有入口、Agent 人工核实恢复、发布公钥、完整包保护和跨机验收尚未完成；当前不要打包分发。

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
      └─ new/                     `/app/new` 新版工作台、成果库、声音中心和登录页
```

## 核心源码、工具和测试

```text
src/jyd_probe/                    共用核心代码
src/jyd_probe/project_store.py    新版统一项目、素材版本、操作和外部批次关联
src/jyd_probe/h3_quote_recovery.py H3 费用预览输入指纹、稳定行 ID 和安全恢复判定
src/jyd_probe/project_inputs.py   新版四列 Excel/CSV、历史两列兼容解析及输入图片校验
src/jyd_probe/semantic_visual_folders.py 文件夹语义图库整理、SQLite 增量索引、图片/视频兼容缓存
src/jyd_probe/semantic_food_categories.py 核心食物实体、动作/分量归并、混合菜多食材归属
src/jyd_probe/semantic_food_matching.py 文件夹模式下的菜名精确匹配、食材组合及主食材分层选材
src/jyd_probe/semantic_food_reclassification.py 现有文件夹索引的显式归类、逐文件移动和可恢复记录
src/jyd_probe/project_audio.py    新版音色校验、数字人音频批次编排、状态同步和版本落盘
src/jyd_probe/audio_submission_recovery.py 声音提交中断后的只读回执查回、输入核对和安全恢复
src/jyd_probe/h3_audio_cleanup.py H3 原片逐段本地 ASR、等长片头静音、派生缓存和后台处理队列
src/jyd_probe/h3_cache_paths.py H3 平级短缓存目录、完整摘要编码与旧原片路径兼容
src/jyd_probe/h3_video_segments.py H3 不可变原片快照、有序版本清单与完整性校验
src/jyd_probe/video_sequence_apply.py 账号模板主视频槽的原生独立片段替换
src/jyd_probe/draft_media_paths.py 输出草稿长路径素材的内容校验、短路径副本与引用替换
src/jyd_probe/project_variants.py 新版变体配方冻结、最大差异组合、剪映批次和失败重试
src/jyd_probe/project_results.py  新版成果批次目录、原始脚本归档和真实成果查询
tests/test_new_frontend.py        新版路由、登录会话、退出和安全返回测试
tests/test_project_inputs.py      脚本导入、图片池、映射策略和刷新恢复测试
tests/test_project_audio.py       声音批次、项目关联、音频落盘和时间戳回流测试
tests/test_audio_submission_recovery.py 退出/断线/延迟提交/多行回执及防重复计费恢复测试
tests/test_project_video.py       当前视频上传替换、原始片段直下/ZIP 和字幕失效测试
tests/test_project_variants.py    模块 6 差异算法、配方冻结、补充生成和失败重试测试
tests/test_project_results.py     模块 7 日期/批次归档、筛选、权限和 ZIP 下载测试
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
