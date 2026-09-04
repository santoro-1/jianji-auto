# 开发者指南

### 2026-09-03 内置媒体工具自动发现

- 冻结工作台除系统 `PATH`、EXE 同级 `ffmpeg/bin` 和 EXE 上一级 `ffmpeg/bin` 外，
  也会自动发现 `asr_runtime/ffmpeg/bin` 中随便携 ASR 一同交付的 FFmpeg/FFprobe。
- H3 新片段下载校验、片头声音清理、BGM 响度检测和浏览器预览共用该解析结果；直接运行
  `JianyingRenderServer.exe` 不再依赖启动终端临时设置 `PATH`。

### 2026-09-03 H3 历史批次新版片段回收

- 已成功但 `local_preview_is_current=false`，或本地下载仍为排队、下载、校验、失败状态的分段，
  会让其所属历史批次继续进入状态同步；即使后来又创建了新批次，也不会只刷新最新批次而让旧行永久等待。
- 云端成功但当前版本尚未落盘时，片段检查只提供“不收费”的继续/重新下载入口，并禁用付费
  “重试这段”；只有 `local_preview_is_current=true` 才允许打包原始片段或再次主动重生成。

### 2026-09-03 封面标题独立展示

- 工作台按 `title_analysis_status` 和 `settings.postprocess.title/cover_title` 独立展示两行封面标题，
  不再依赖字幕分支、FunASR 校准或 4B 预览成功。
- 统一分析部分成功时明确展示标题分支状态和错误；字幕失败不得清空已成功标题。

### 2026-09-01 独立 Agent 实际接入（当前，开发中）

- `device_agent_routes.py` 安装中央挑战、注册/心跳/领取、启动和原结果回报接口；`device_agent_operations.py` 在数据库事务中核对原账号/设备/任务/执行编号。共用接入密码仍用于接入中央，但不能替代设备证明，冻结 EXE 不走源码空信任根兼容路径。
- `device_agent_transport.py` 每次业务请求取得新挑战和云端单次许可；禁止重定向，不自动重发不明业务请求。`device_agent_runtime.py` 在实际执行机建立自己的本地核心授权；`device_agent_journal.py` 在固定用户数据目录持久保存执行和结果回执，不存密码/令牌/私钥。
- Agent CLI/GUI 通过 `device_command_authorization.account_authorization` 复用原账号与原密钥，不初始化或重新登记。GUI 先核对可信网站，再登录；本次密码用一次性线程交接，网站配置仅保存地址与用户名。停止/关闭等待当前执行单元安全收尾。
- 领取/启动响应丢失可续接原执行编号；完成响应丢失只补报同一结果。中央同一已验证密钥最多一个运行任务，相同结果幂等、迟到失败不覆盖成功。设备撤销后可凭原账号/原密钥补报原结果，不能借此领取新任务。
- `executing` 回执表示执行结果不明，禁止自动重做；受控人工核实恢复工具仍待开发，不建议删回执或改 SQL。租约过期、切换运行模式及旧状态导入不把已启动工作重新排队。
- 真实代码跨端/HTTP/运行合同 `66 passed`；网站完整集 `839 passed`；工作台选定相关回归 `341 passed`，最后 GUI/网络/回执模块 `18 passed`。报告在 RH `tests/.runtime/device-agent-*.xml`，具体快照和范围见 [主文档第 23 节](../../../数字人/runninghub_mvp/工作台设备授权与免重复激活开发文档.md#23-独立-agent-接入与持久执行回执2026-09-01)。集合重叠，不是工作台全量或真实剪映/硬件/GUI 验收。
- 其他私有/付费入口、人工核实恢复、实机与多 Windows 用户、发布公钥和整包保护仍未完成，不发包。以下小节保留历史进度，不能把其中“Agent 尚未接通”当作当前状态。

### 2026-09-01 命令行受控执行（历史阶段，开发中）

- 新增 `device_command_authorization.py`，只从编入信任根对应的网站登录/验证账号；禁止账号接口重定向，严格解析并限制响应，错误不回显令牌或原始服务端正文。
- `JianyingRenderServer.exe --render-job`、`tools/jobs/run_render_job.py` 及 probe 的建草稿操作使用专属账号/设备会话。支持 `--device-user 用户名` 后隐藏输入密码，或显式 `--device-token-stdin` 从管道读取一行已有网站令牌；不接受密码参数，不保存密码/令牌。非交互环境不能回退到密码回显。
- 只读 `MachineDeviceIdentity` 原密钥，不自动 register、初始化/UAC 或换钥；命令结束/异常关闭会话及句柄，不删除设备身份。核心仍按实际草稿/导出范围验证；源码无信任根的开发兼容不适用于冻结 EXE。登录与重新激活分开。
- 工作台相关回归 `346 passed`，补齐成功执行和最小权限后的命令行/本地核心/启动器专项 `110 passed`，真实两端合同 `9 passed`；集合重叠。使用模拟密钥/渲染及隔离数据库，不代表真实 EXE 更新/跨机验收。
- 独立 Agent 仍仅有共用接入密码，合法持钥交接与按原任务账号筛选尚未实现；保护模式下原暂时拒绝领取保持不变，不以拒绝一切代替完成。其余私有脚本、发布公钥/整包及实际设备验收仍待继续，不发包。最新合同见 [主开发文档第 21 节](../../../数字人/runninghub_mvp/工作台设备授权与免重复激活开发文档.md#21-命令行受控执行与独立-agent-审计2026-09-01)；下列均为历史阶段记录。

### 2026-09-01 软件初始化与稳定身份定位（历史阶段，开发中）

- 新增 `device_identity_store.py`：实际交互适配器/辅助入口使用固定机器级定位记录，保存提供程序和公钥摘要，不保存授权或私钥。正常读取、升级不写记录；原钥匙缺失、记录损坏、双提供程序冲突或无法确认状态时不创建第二身份。显式初始化/原钥匙访问修复通过机器级互斥锁串行，写记录失败保留已创建钥匙。
- 云端新增软件初始化专用签名许可，工作台经显式 `apply-software`、双重确认和 `device_initialization_channel.py` 的受限单向本机管道交给辅助程序。辅助程序核对原进程/用户、编译公钥及许可用途/时间，取得机器锁后再次检查有效期；初始化后仍需登记和管理员批准，不直接获得业务权利。
- 请求许可前先找原钥匙；已有软件设备不因更新变回 TPM，TPM 故障不自动降级。普通启动、状态查询、登录和后台刷新不会申请软件初始化。
- 专项/管道 `86 passed`、软件两端实际代码专项 `57 passed`、工作台授权/启动器/前端/H3 相关回归 `291 passed`。包含真实 Windows 临时管道传输测试 JSON 和浏览器模拟交互/桌面截图；没有真实 CNG 密钥、注册表写入、UAC 或生产操作，不是实机激活/跨机升级验收。
- 真实 TPM/无 TPM、不同 Windows 用户、独立 Agent/CLI、其他私有入口、发布公钥/完整包保护仍待完成。信任根仍为空，不打包分发。完整合同见 [设备授权开发文档第 20 节](../../../数字人/runninghub_mvp/工作台设备授权与免重复激活开发文档.md#20-受控软件初始化与稳定原密钥定位2026-09-01)；下列为历史进度。

### 2026-09-01 设备授权后续（开发中）

- H3 历史批次支持原账号分页查看、明确确认后补授权，不创建生成任务或重发远程请求。`device_h3_recovery_routes.py` 和页面脚本接通原持钥通道。`device_background_refresh.py` 随服务运行，只刷新既有账号会话，不初始化密钥或恢复任务。
- `device_identity_setup.py` 将首次 TPM 初始化交给同一正式 EXE 的固定提权辅助入口；`processor_windows.main()` 在配置/ASR/网站/任务启动前分派该入口，正常启动无初始化副作用。原密钥可用时直接复用，源码测试不自动创建机器密钥。
- `device_identity_setup_windows.py` 通过原 PID/创建时间、存活状态、同 EXE/交互会话及 TokenUser 核对真正操作用户；不从网页接受 SID 或任意命令。UAC 取消不重试，超时保留原辅助进程句柄，不把观察失败当成进程结束。
- `device_identity_acl.py` 在明确修复时为原密钥合并一个操作用户的读/签名权限，保留其他条目；不创建或删除密钥。`repair-key-access` 接口要求同源和严格确认；修复成功后重新打开原钥并联网校验，不调用 register，不批准设备或自动继续任务。
- 本阶段模拟专项 `54 passed`，工作台初始化/授权/后台/本地核心/启动器/前端相关 `200 passed`，两端合同 `57 passed`。先前 H3 恢复阶段网站完整回归 `707 passed`，本轮未重跑网站全量（无服务端业务代码变化）。集合重叠不相加。浏览器模拟交互和请求证据通过，截图未获取，不算实机 TPM/跨机验收。
- 软件保护的受控初始化与原软件密钥恢复、真实 UAC/ACL、多机/连续 EXE 更新、其他私有入口/独立 Agent/CLI、发布公钥与完整包保护仍未完成，暂不要打包分发。详细合同以 [开发文档第 17、18 节](../../../数字人/runninghub_mvp/工作台设备授权与免重复激活开发文档.md) 为准；以下为较早阶段记录。

### 2026-08-31 设备授权、H3 持钥请求与激活页面（开发中）

- 固定产品设备密钥由 `device_identity_windows.py` 管理。普通启动/恢复只打开已有密钥，明确申请才创建；错误不自动换钥匙，软件保护不静默回退。不把程序版本、安装路径、IP 或账号名作为设备身份。
- `device_auth_protocol.py` 校验 ES256 凭据并创建 DPoP 证明；`device_trust_roots.py` 为编译进程序的发布公钥，当前为空，不读取用户可编辑配置作为信任根。依赖新增 `PyJWT[crypto]>=2.10.1,<3`。
- `device_authorization.py` 按账号隔离会话，刷新复用原密钥；ProgramData 独立缓存仅保存签名本地凭据，不存登录/云端令牌。进程重启后必须联网取得新会话锚点，不重新登记；网络异常只可使用尚未过期的原凭据，不延长租期。已接入本地建草稿/导出核心及内嵌队列，其他私有入口尚未全部覆盖。
- `device_authorization_routes.py` 注册状态/申请/刷新接口，复用 `current_project_user`；POST 要求同源和专用请求头，申请显式确认，不开放任意代签或浏览器指定设备身份。退出只关闭会话句柄，不删除持久密钥。
- 工作台相关回归 `63 passed`；服务器新增 5 项真实两端代码合同测试，配原授权/迁移合计 `29 passed`。均使用临时模拟密钥，未运行真实 TPM/跨机/连续 EXE 更新验收。
- `device_business_transport.py` 与 `AuthCenterClient` 接通 H3 POST/GET，以及声音生成/重试、声音创建/激活、画面合成/重试和增强补做等已审计付费合同。已配置发布信任根时只向匹配源地址发送设备证明；绑定请求移除旧正文令牌、不修改输入及业务幂等键。没有可用设备凭据时可在发送前采用一次账号请求读取结果或接收云端强制拒绝，不是本地放行；发送后的拒绝不降级重发。下载证明禁止跟随重定向，也不发给 RunningHub 直达地址。
- `AuthCenterDeviceError` 保留设备错误码，H3 代理响应带 `device_authorization_required` 与 `X-Workbench-Device-Error`；设备层 401 对业务页面转为 409，不退出网站账号。真正登录失败仍为 401。页面从账号菜单进入 `/app/new/device-authorization`，只在用户明确勾选后申请，其他状态不自动登记。
- 页面可见时待审/待刷新状态每 15 秒查询，有效状态每 5 分钟校验并刷新；查询到批准不等于获准执行，必须取得签名凭据。页面关闭后的独立后台刷新尚待实施，业务调用继续按需刷新。网络异常仅展示会话已有且未过期的短期状态；到期、撤销、密钥故障和账号退出分别提示。
- H3/激活页面阶段工作台回归 `126 passed`，两端合同/云端队列 `35 passed`。后续本地执行阶段广泛回归 `258 passed`，最后队列/UI/文件锁专项 `61 passed`；网站完整回归 `663 passed`，两端客户端/本地策略合同 `36 passed`，均无失败，集合重叠不可相加。模拟 Edge 页面验证显式恢复、拒绝保留、成功移除及 390px 布局，无脚本错误；没有真实授权、渲染或付费调用。
- `device_local_policy.py` 验证云端最长 300 秒的账号/nonce 绑定签名模式，只信编译公钥；策略只在会话内存，不接受普通 JSON/环境变量关闭授权。有效 OFF 兼容旧业务；OBSERVE 尝试检查；ENFORCE 必须有效租约及本机持钥。网络失败不解释为 OFF，也不延长租约。
- `device_local_execution.py` 在核心函数而非只在 UI 检查权限。`run_render_job`、建草稿工厂、内容替换、实际导出已接入；真正行为决定 draft/render 权限，同一决策锁定凭据修订。已获准执行单元可安全收尾，下个单元重新检查。冻结 EXE 始终启用，空信任根时拒绝；空信任根源码开发兼容路径不是发布开关。
- `device_local_web.py` 从当前网站账号建立内部上下文；`device_local_queue.py` 在内嵌队列真正执行前重验。任务状态只保存非秘密账号/设备关联，不把载荷当许可；授权失效等待、不新增 ID/自动重试。数据库状态为权威，文件锁不导致队列失败；用户在授权页明确继续原任务，重新登录本身不自动恢复。
- 待完成 UAC/ACL、软件模式身份恢复、独立后台刷新、其他私有 API/CLI/FFmpeg 与独立 Agent 合法授权通路、无归属历史队列恢复和打包公钥/排敏。当前受保护环境临时拒绝旧 Agent 仅凭接入密码领取新任务，即使签名 OFF 也拒绝；这是过渡封口，不是完整可用 Agent。发布信任根仍为空，暂不要打包分发；未修改生成算法或启用生产强制保护。完整范围见 [设备授权开发文档](../../../数字人/runninghub_mvp/工作台设备授权与免重复激活开发文档.md#167-本地执行与内嵌队列合同)。

### 2026-08-31 H3 费用预览恢复

- `h3_quote_recovery.py` 定义 `jyd.h3-quote-recovery.v1`。前端提交稳定 `item_id`（UI 字段 `id`），不混用 `rowKey` 和 `row_key`。后台读取项目批次登记及行级旧关联，查询云端后判断是否可恢复。
- 创建预览时将行 ID、显示行号、脚本、MiniMax 音频版本及真实文件内容、人物图、参考视频和生效参数绑定为 SHA-256 凭据；素材路径不参与身份。恢复和确认都重新核对。凭据保存在 `settings.h3.batches[].quote_binding`，不存脚本明文或素材路径。旧版无凭据的预览不能自动当作当前输入确认。
- 选择范围完全一致且输入未变化才恢复原费用确认；范围部分重叠或输入改变时列出旧批次所有行和段数，明确确认后撤销整个未提交预览，再只为本次选中行计算。新预览仍需用户另行确认费用。
- 待确认的 soft_chain 段不视为已运行任务；即使当前素材已缺失，底部生成按钮仍可进入旧预览处理。单行/勾选生成入口也先处理旧预览，再校验新任务素材，避免无法撤销的死锁。
- 本地使用按用户/项目分组的进程内锁串行化预览、确认和撤销；云端在数据库中原子仲裁确认/撤销，防止多客户端竞态。云端已创建任务、已确认或任一分段离开未提交状态时禁止按预览撤销；soft_chain 非首段在报价时的 `WAITING_DEPENDENCY` 属合法未提交状态。此入口与付费分段取消/重试不同。
- 撤销请求失败不清理关联；配置改变仍保留批次登记供查询/撤销；延迟的待确认快照不得覆盖已确认或已撤销状态。恢复查询不覆盖进行中的声音生成，也不影响其他行批次和原本的缺文件下载恢复。
- 日志事件为 `h3.quote_checked/resumed/created/confirmed/cancelled/confirmation_blocked/sync_failed`。诊断包增加本修复协议版本、实际前端 SHA-256、批次状态及绑定摘要，不包含取消凭据、脚本或素材。
- 先更新云端再更新工作台；旧云端不返回安全撤销能力时保留旧预览并提示升级，禁止本地强行清锁。本功能无新增数据库迁移，不改变费用规则、余额不足换账号逻辑或 H3 Prompt。
- 无费用回归：`tests/test_h3_quote_recovery.py` 执行真实前端恢复函数的 Node 测试及本地协调器测试；`tests/test_project_h3_api.py` 覆盖接口冲突；云端 `tests/test_h3_quote_lifecycle.py` 覆盖权限、撤销/确认竞争及重复确认。

### 2026-08-31 H3 短路径与失败状态修复

- 新 H3 工作目录仍属于原 `projects/<owner>/<project>/<item>/h3`，不改变账号隔离、
  `storage://` 迁移或删除项目的目录边界。其下使用平级 `s-<24字符>/v-<24字符>.mp4`
  （分段下载）、`c-<24字符>/clean.wav|preview.mp4|report.json`（片头清理）和
  `m-<24字符>/...`（合成）；版本文件与指针同层，不再创建 `versions/<64位摘要>`。
  目录/文件标识是小写 Base32 的 120-bit 短标识；完整 SHA-256 只保存在 JSON/数据库中并在
  复用前核验，不再作为新目录名或文件名。
- 不可变原片放在同一行 `h3/f/f-<24字符>/segment.mp4`，不再嵌套在每个合成版本目录下；
  相同内容可复用，`identity.json` 保留完整原片 SHA-256，素材绑定继续核对完整合成签名、
  远端批次/行/片段、文件内容和真实时长。
- 旧 `segment-cache/<64位 key>/current.mp4`、`s-<52字符>/raw.mp4` 以及首版
  `s-<52字符>/versions/<64位版本>/video.mp4` 继续只读兼容；新下载和派生物一律写入 24 字符布局。
  新结果写入短目录，旧文件不改名、不删除。旧有效清理结果由本地后台校验并复制到短目录，
  无需再做 ASR/编码；复制失败保留旧文件并明确返回本地错误。无有效缓存时只从原片重建本地派生物。
- 新布局不继承旧超长目录中的失败预算，使路径修复后的旧批次可以继续本地清理。新布局仍最多
  自动尝试三次、间隔 60 秒；失败先保存进程内状态，再尝试原子落盘。创建目录、写错误文件或
  发布错误文件本身失败时，预算不会在下一次轮询丢失，并记入普通日志；只有错误记录成功落盘
  才能跨重启保留预算。磁盘完全不可写时，进程内仍可显示失败，重启后可能重新进行有限尝试。
- 工作线程无法提交、失败记录损坏均显示明确失败；人工“重试本地清理”才重置预算，不请求云端
  重新生成。声音清理算法、权威音轨、字幕时钟及剪映草稿合同不变。
- `test_h3_short_cache.py` 覆盖 250/188 以及
  `G:/新建文件夹/PublicVideo0903_v2/digital-human` 完整路径（包括下载断点、临时文件）
  小于 240 UTF-16 单位，并禁止 H3 新路径组件出现 52/64 字符摘要；
  旧缓存兼容、版本/账号隔离、真实线程中的错误记录写入失败和重试预算。不依赖修改系统长路径开关；
  任意更深的自定义安装目录仍需单独检查，不能认为所有第三方工具都支持无限长路径。

### 2026-08-31 H3 本地片头声音清理

新版工作台 H3 接口默认启用 `jyd.h3-head-silence.v2`。复用现有
`JYD_ASR_BASE_URL`（默认 `http://127.0.0.1:18084`）的 Paraformer 字词时间戳，
不会修改云端 H3 输出合同或恢复旧的 300ms 裁剪。声音条件仍是 H3 实际输出，不换回 MiniMax。

- 原片内容和下载摘要不变，旧 `segment-cache/<id>/current.mp4` 兼容，新目录见上节。逐段独立解码，ASR 用 16k 单声道；
  清理用原采样率/声道的 16-bit PCM，避免立体声反相杂音被分析下混抵消。
- ASR 只提供“已经识别到正常人声”及实际字词时间戳，不再把脚本开头三个 token 作为硬匹配
  条件；同音字、漏字、错字和标点差异不会阻塞整行。首个有效 token 超过 5 秒保护范围、没有
  有效 token 或没有稳定人声能量时均保留原音并返回 `READY` 警告，不进入付费重生成或本地失败。
- 以 10ms RMS 窗、5ms 步长搜索至少 80ms 的稳定人声能量，活动窗比例至少 60%，阈值相对
  ASR 人声参考电平低 18dB。瞬时脉冲不会作为开口；检测到的开口前保留 180ms 原音保护区，
  清理区末尾做 10ms 半余弦淡入。保护区之后 PCM 完全不变，总样本数不变；连续音乐或过早
  开口会安全保留原音。参数是当前口播样本的保守方案，不是适用于所有音频的保证。
- 清理缓存按原片 SHA256、完整分段台词摘要和全部算法配置寻址。产物为独立 `clean.wav`、
  `preview.mp4`、`report.json`，报告最后原子发布；不会累积处理已经清理的文件。
- 共享后台线程池最多同时处理两段，最多排队 16 段，不在状态请求中等待 ASR。
  失败落盘，间隔 60 秒最多自动尝试三次，之后用片段检查的本地重试按钮恢复。
  后台仅写派生文件，状态轮询负责版本回填；重启可恢复未完成清理。
- 单段预览用清理版，原始素材下载显式用原片；清理 PCM 按实际视频边界及原音视频起点差
  组合为最终权威 WAV，再封装母版 AAC。不能从原 AAC 拼接母版重新抽声音覆盖清理结果。
  MP4 中音频会重编码，正文样本不变的约束指权威 PCM，不宣称 AAC 字节级不变。
- 合成缓存和素材 metadata 包含清理版本及逐段 key；旧本地结果状态同步可重新准备派生素材，
  v1 失败预算不会阻塞 v2 重建；不重做付费 H3、不覆盖已经打开或导出的用户草稿。清理未完成前
  不自动启动该行 4B。
- 本轮不改独立视频片段建轨、接缝视觉叠化、全局降噪或段尾脉冲处理。

回归：`test_h3_audio_cleanup.py`、`test_h3_audio_cleanup_coordinator.py`、
`test_project_h3.py`、`test_project_h3_media.py`、`test_project_h3_api.py`、
`test_caption_alignment.py`、`test_new_frontend.py`。

### 2026-09-01 正式启动默认文件夹语义图库

冻结 EXE 和 `start_processor.ps1` 默认设置 `JYD_SEMANTIC_VISUAL_SOURCE_MODE=folders`，
并在首次启动建立 `data/libraries/semantic_visual_library/素材`。配置文件可通过
`semantic_visual_source_mode=json` 显式回退；启动切换不删除或自动迁移旧 JSON/素材，
也不改写历史冻结配方。文件夹增删约 5 秒刷新，页面不再提示必须重启。

### 2026-08-31 文件夹语义图库（历史测试阶段）

本地测试启动设置 `JYD_SEMANTIC_VISUAL_SOURCE_MODE=folders` 和独立的
`JYD_SEMANTIC_VISUAL_LIBRARY_ROOT`；默认 JSON 模式兼容不变。`semantic_visual_folders.py`
负责显式旧库复制整理、SQLite 增量扫描和不可变兼容缓存。运行时不读取旧 JSON。
统一分析与旧分析/接缝分析均传入行级选材种子、已有 recipe；跨目录按内容摘要去重，
重新映射保留已有选择。文件夹模式不会在启动时批量刷新旧项目，也不按当前目录覆盖冻结
配方的资源与裁切参数。详细边界和运维命令见 `SEMANTIC_VISUAL_LIBRARY.md`。

### 2026-08-31 H3 回填隔离

本地回填错误通过 `settings.h3.materialization_error` 保存，并使用
`H3_REVIEW_REQUIRED` 行状态；不要把远端已完成的任务重新提交。脚本不一致在编码前失败，
其他行继续回填；页面必须展示逐行提示并继续成功行后处理。改稿/新音频会使旧 H3 绑定失效。
声音源脚本或音色/非语速参数变化时创建新的远端声音任务，不能走只更新速度的旧任务 retry。
回归覆盖在 `test_project_audio_binding.py`、`test_project_h3.py` 和 `test_project_h3_media.py`。

本文面向需要继续开发、调试和发布“影变批剪工作台”的维护者。用户安装和日常操作请阅读根目录 `START_HERE.md`；具体素材格式、接口字段和部署方式请按本文末尾的专题文档索引继续阅读。

> 2026-08-10：数字人云端的每个分段现已在数字人成功后进入固定 48G 的 SeedVR2。
> 本地工作台不调用放大流，只把 `VIDEO_ENHANCING` 视为活动状态，并在就绪后下载
> `quality_variant=seedvr2_upscaled` 的清晰片段。数字人源片段仍保存在云端。

> 2026-08-12：新版工作台新增逐任务站姿 / 坐姿画面规范及勾选批量设置。
> 两套字幕、人名板、固定文字和语义图片参数见 `LAYOUT_PROFILES.md`。

## 1. 项目定位与边界

本项目通过读写剪映草稿 JSON 和 Windows UI 自动化完成批量视频生产，主要能力包括：

- 读取本机剪映草稿，必要时通过 `jy-draftc` 解密高版本草稿。
- 从 MP4 创建基础草稿，或从已导入的剪辑母版生成副本。
- 替换或新增 BGM、视频特效、字幕字体、贴纸、花字和文字模板。
- 应用镜像、裁剪、背景填色、人物定位和封面等画面变化。
- 生成单个或批量任务，并调用剪映顺序导出 MP4。
- 管理公共素材、个人素材、母版、任务、输出和回收站。
- 以单机嵌入模式运行，或由中央服务把任务交给一台或多台 Windows Agent。

必须明确的技术边界：

- 真正的剪映导出只能运行在 Windows 桌面会话中，目标电脑必须安装兼容版本的剪映。
- UI 自动化会占用剪映窗口，不适合在同一桌面会话中并行操作多个剪映实例。
- Web 服务可以集中部署，但实际执行导出的 Agent 仍然必须是可交互的 Windows 电脑。
- 草稿中的本地绝对路径必须在执行任务的电脑上可访问，或在导入、采集阶段被复制和重定位。

## 2. 总体架构

```text
浏览器
  |
  v
Processor Web/API (FastAPI, :8000)
  |-- 用户页面、批量编辑器、素材管理、任务结果
  |-- SQLite 控制库和任务状态
  |-- embedded: 进程内顺序执行 Render Job
  `-- agent: Agent 领取任务、回传状态和结果
          |
          v
      Windows Render Agent
          |
          v
      render_job.py
          |-- 草稿创建/复制/解密
          |-- JSON 修改和资源应用
          `-- 剪映 UI 自动导出 MP4

Local Collector (:8765)
  |-- 扫描本机 JianyingPro Drafts
  |-- 分析、解密、采集素材和字体
  |-- 选择本机视频及输出目录
  `-- 向 Processor 上传母版或素材包
```

### 2.1 三个主要应用

| 应用 | 源码入口 | 默认地址 | 职责 |
| --- | --- | --- | --- |
| Processor | `apps/processor/run_web_api.py` | `127.0.0.1:8000` | 网站、API、账户、素材、任务和嵌入式执行 |
| Collector | `apps/collector/run_local_collector.py` | `127.0.0.1:8765` | 本机草稿扫描、采集、文件选择和上传 |
| Agent | `apps/agent/run_agent.py` | 主动连接 Processor | 领取任务并控制本机剪映导出 |

`apps/auth_center` 是独立账户中心，用于多工作台统一登录。它不是剪映渲染链路的一部分，单机开发不需要启动。

### 2.2 两种执行模式

- `embedded`：Processor 自己执行任务。适合本机开发、单机安装包和大部分功能调试。
- `agent`：Processor 只调度任务，Windows Agent 主动领取并执行。适合中央网站连接多台剪映处理机。

切换模式不会改变 Render Job 的业务结构，只改变任务由哪个进程执行。

## 3. 目录结构

```text
apps/                         可运行、可打包的应用入口和前端
  processor/frontend/         主工作台、批量编辑器、素材页、登录页
    new/                      `/app/new` 新版工作台静态页面
  collector/frontend/         独立采集器调试页面
  auth_center/                可选的统一账户服务
src/jyd_probe/                核心 Python 代码
data/
  libraries/                  随正式安装包发布的公共素材
  personal_libraries/         当前安装实例采集的个人素材
  template_library/           已导入的剪辑母版
  web_storage/                数据库、任务、上传、输出和会话数据
docs/                         开发、接口、部署及素材专题文档
examples/                     Render Job JSON 示例
runtime/                      解密副本、测试环境和临时运行数据
scripts/                      开发环境及 Windows 打包脚本
tests/                        自动化测试
tools/                        草稿诊断、素材提取和任务调试工具
vendor/jy-draftc/             高版本剪映草稿解密程序
release/                      最终交付 ZIP
```

新版统一项目数据由 `src/jyd_probe/project_store.py` 管理。它与渲染队列共用
`control.db`，但只创建 `project_*` 表和独立的 `project_schema_meta`，不会修改既有
`schema_meta`、`batches`、`jobs` 或 `agents`。`Project` 包含多条 `ProjectItem`；
音频、原始片段、画面合成视频、上传视频和变体都按不可覆盖的素材版本保存。
模块 2 把 `project_schema_meta` 升级到版本 2：为脚本行增加当前输入图片指针，并增加
`project_input_images` 项目图片池。模块 3 升级到版本 3，增加按数字人账号保存的默认
音色和语音参数；逐行音色、音频素材版本、MiniMax 时间戳、数字人批次关联和异步操作
继续复用现有项目表。模块 4A 升级到版本 4，增加当前基础视频指针；基础视频与最终
`composition_video` 分离，云端有序分段继续按不可覆盖版本保存；自 2026-08-10 起默认
为 SeedVR2 清晰结果。模块 4B 升级到
版本 5，增加浏览器预览配方、按需导出和字幕渲染状态绑定；旧版
`POSTPROCESS_RUNNING` 剪映任务仍可同步完成。升级只执行
`CREATE TABLE IF NOT EXISTS` 和缺失列
`ALTER TABLE ADD COLUMN`，不会重建或清空既有项目及剪映任务表。

智能内容分析模块 5 将项目 schema 升级到版本 7，为 `project_items` 增加
`content_analysis_json`。快照按当前脚本 SHA-256 绑定，分别保存音乐、字幕分支状态和
结果；脚本变化只重置该行快照，音色、音频、字体或宽度变化不删除语义分析。工作台通过
`project_content_analysis.py` 把一个项目拆成逐行请求，单批并发最多 10；每行失败独立
落盘并继续其余行。内容分析状态不参与原有音频、4A、4B 或变体状态机，不得借分析失败
清空 MiniMax `raw_cues`、当前音视频指针或历史素材。

智能内容分析模块 6 将项目 schema 升级到版本 8，但不新增数据库列。字幕 JSON 增加
`semantic_mapping`；`semantic_subtitles.py` 负责严格原文复核和 MiniMax cue 锚点内的确定性
字符时间映射，`project_postprocess.py` 负责语义组真实字宽排版和失败降级。新音频素材的
metadata 保存脚本 SHA-256/长度；只有脚本、分析、音频和 raw cues 绑定四方一致时使用
`subtitle_units`，否则继续使用既有 raw cues 排版。任何路径都不得覆盖 `raw_cues`。

精确字幕时间校准由 `caption_alignment.py` 完成。FunASR 仅产生候选字词时间，随后必须与
原脚本 token 做顺序精确匹配；全局命中率至少 90%，每个 MiniMax raw cue 也必须通过局部
质量门。`project_postprocess.py` 先完成语义断句和真实字宽排版，再把最终 `render_cues`
重新绑定到 ASR 时间，并始终用 raw cue 作为硬边界。成功结果保存在
`subtitles.asr_alignment`，缓存键由脚本 SHA-256、音频素材 ID 和版本组成；不得把 ASR
识别文本作为字幕落盘，也不得覆盖 `raw_cues`。默认工作台要求精确对齐，服务故障或质量门
失败时标记 `REVIEW_REQUIRED`；只有测试或显式关闭配置允许旧插值路径。
完整请求仅在明确缺少字词时间戳时启用分块回退：先规范为 16k 单声道 PCM，再用 20 秒核心区
加前后 1 秒上下文识别；合并时按 token 中点归属非重叠核心区并恢复绝对时间。其他 HTTP、结构、
脚本命中率或 raw cue 错误不触发该回退。单行失败保存 `REVIEW_REQUIRED` 后继续同批其他行。

日志第一阶段将项目 schema 升级到版本 9，为 `project_operations` 增加独立
`correlation_id`。项目操作、云端声音批次、4A 画面生成和本地渲染都应传递该字段；
`idempotency_key` 只负责防重复提交，不得兼作关联号。历史操作以原 `operation_id` 回填。

Processor 日志位于 `data/logs/workbench.log`，本地渲染位于 `data/logs/render.log`，内嵌
Collector 位于 `data/logs/collector.log`，`server.log` 只保留启动和致命错误。独立 Collector
使用其状态目录下的 `logs/collector.log`；独立 Agent 使用
`%LOCALAPPDATA%/JianyingRenderAgent/logs/agent.log`。本地日志默认单文件 10 MB、保留 14 天，
写入前统一脱敏，不得记录访问令牌、API Key、完整脚本或完整请求体。

AuthCenterError 必须保留云端返回的业务正文，并用稳定错误码区分失败类型：
DIGITAL_HUMAN_REQUEST_REJECTED 表示 4xx 业务拒绝，不能伪装成断网；
DIGITAL_HUMAN_AUTH_EXPIRED / DIGITAL_HUMAN_FORBIDDEN 表示账号问题；
DIGITAL_HUMAN_CONNECTION_FAILED 和 DIGITAL_HUMAN_SERVER_UNAVAILABLE 才允许按
服务器暂时不可用处理。4A 状态轮询结束后，前端显示最近一次失败操作的真实正文；只有连接
失败或 5xx 使用“数字人服务器暂时不可用”标题。

`GET /api/new/projects/{project_id}/diagnostics` 仅允许项目所有者下载临时 ZIP。摘要不得包含
脚本文本、素材路径、操作 `payload/result` 或错误正文；日志仅从 14 天内的 `workbench.log`、
`render.log`、`collector.log` 及其轮转文件中选取与当前 `project_id`、`operation_id` 或
`correlation_id` 精确匹配的行，并在打包前再次脱敏。独立 Agent 的 `agent.log` 不在本机包内。

不要把以下数据混为一类：

- `data/libraries`：公共、长期保留、可随完整安装包分发。
- `data/personal_libraries`：某个运行实例采集的个人素材，更新包默认不会覆盖；需要迁移时复制整个目录。
- `data/web_storage`：运行状态，不应从开发机直接覆盖生产机。
- `runtime`：临时数据，通常不参与正式发布。

### 声音提交安全边界（2026-08-31 修复）

`ProjectAudioCoordinator.retry()` 统一调用现有声音批次创建接口，不再调用缺少幂等键、且拒绝
H3 已审核 `SUCCESS` 的旧云端 retry。即使仅改变语速也建立独立任务，保留旧远端任务与素材。
本地请求键摘要包含项目、操作幂等键和音色，同一操作再次请求只读取状态。
中断恢复新增云端只读 `/api/workbench/audio-batches/lookup` 接口，需先部署服务器再更新工作台；无数据库迁移。

新操作 payload 使用 `submission_contract=jyd.audio-submission.v1`。本地先原子检查行状态、脚本与旧音频版本，
登记 `PENDING`，再按音色组整体认领 `STARTING`；这两阶段不清空原音视频、字幕或 H3 设置。
收到并校验完整云端响应后，`accept_audio_submission()` 按精确 operation ID 在单个事务中
保存批次/行关联、切换声音配置、失效旧当前关联、保存远端 ID 和 `RUNNING`。历史素材仍保留，重复接收同一回执不再次失效素材。

4xx 明确拒绝记为 `FAILED`，保留原输出与状态；超时、断线、5xx 或不完整响应记
`AUDIO_SUBMISSION_UNKNOWN`，提示先核对云端并禁止该行盲目新建付费任务。不能把网络断开当作未提交。
同一 SQLite 只运行一个中央 API 进程；各协调器共享内存中的在途请求作用域。状态同步与新提交之前，
仅收尾不在作用域内的 v1 遗留操作：`PENDING` 记为 `AUDIO_NOT_SUBMITTED`，`STARTING` 记为
`AUDIO_SUBMISSION_UNKNOWN`，恢复旧行状态。不得用超时猜测仍在执行的请求已经退出。
`audio_submission_recovery.py` 按原请求键查询云端，逐项核对来源、关联 ID、脚本 SHA-256、音色和六项
语音参数后接回原任务。查询无结果不代表未计费，404/断网/不匹配均保持待核对，不降级为创建或重试接口。
页面通过 `items[].audio_submission.status=UNKNOWN` 显示警告并每 10 秒查询，禁用该行重新生成声音。
四个声音提交入口在报错后主动读取最新状态，状态同步失败时回退读取项目；完全断网时每 5 秒只重试读取，
不把浏览器缓存当作最新状态、不自动重放 POST；切换项目后不回填上一项目的异步结果。
本轮不重放未知请求，不自动恢复不带 v1 合同的旧版记录，不保存访问令牌或覆盖用户数据库。
未提交的后续音色组记 `AUDIO_NOT_SUBMITTED`，已接收的组保持运行并继续查询/下载。

提交中的行不允许状态轮询把旧音频/旧链接当成新结果；新任务的 `SUCCESS` 仅在本地已确认接收的
batch/item 精确匹配时可收尾。下载中断保留 `RUNNING`，后续只下载同一个远端结果，不重做 MiniMax。
回归覆盖见 `tests/test_project_audio_binding.py`、`tests/test_audio_submission_recovery.py` 与页面测试；供应商调用均使用 mock。

## 4. 开发环境

### 4.1 前置条件

- Windows 10 或 Windows 11。
- Python 3.11，当前开发机也可显式指定已有 Python。
- 已安装兼容版本剪映，并能正常手工打开草稿和导出视频。
- PowerShell 5.1 或更高版本。
- `vendor/jy-draftc/jy-draftc.exe` 存在。

安装运行依赖：

```powershell
python -m pip install -r .\requirements.txt
python -m pip install pytest
```

当前主要依赖包括 `pyJianYingDraft==0.3.0`、FastAPI、Uvicorn、FontTools、OpenCV 和 NumPy。

### 4.2 启动单机开发环境

在项目根目录执行：

```powershell
.\start_processor.ps1 `
  -Python "D:\Myanaconda\python.exe" `
  -ProcessingMode standalone `
  -ExecutionMode embedded
```

该正式源码入口默认连接 `https://video.lanyingjk01.com`，并与生产对口型入口
`http://127.0.0.1:8791` 成对。需要显式联调其他数字人服务或对口型地址时，使用
`-DigitalHumanServerUrl` 和 `-LtxWorkbenchUrl` 参数覆盖，不要把正式入口写到测试端口。

访问：

```text
工作台：http://127.0.0.1:8000/app
高级页面：http://127.0.0.1:8000/app/advanced
素材管理：http://127.0.0.1:8000/app/assets
接口文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/api/health
```

如需读取本机草稿、弹出文件夹选择器或采集个人素材，再开一个 PowerShell：

```powershell
.\start_collector.ps1 `
  -Python "D:\Myanaconda\python.exe" `
  -ServerUrl "http://127.0.0.1:8000"
```

默认端口是 `8765`。主页面会通过本地接口检测 Collector 是否在线。

### 4.3 前端开发

前端主体是原生 HTML、CSS 和 JavaScript，修改后刷新浏览器即可：

- `apps/processor/frontend/product.*`：普通用户工作台和批量任务主流程。
- `apps/processor/frontend/advanced.*`：高级任务页面。
- `apps/processor/frontend/assets.*`：素材和母版管理。
- `apps/processor/frontend/app.*`：旧版/通用页面逻辑，修改前先确认路由实际加载的脚本。

`apps/processor/frontend/new/` 的 Tailwind 与 Font Awesome 必须随工作台本地提供，运行时
不得依赖 CDN，否则断网或 CDN 不可达时会导致 `hidden`、布局和弹层样式整体失效。页面新增
或修改 Tailwind class 后，在项目根目录重新生成并提交 `tailwind.generated.css`：

```powershell
npx --yes tailwindcss@3.4.17 -c apps/processor/frontend/new/tailwind.config.cjs -i apps/processor/frontend/new/tailwind.input.css -o apps/processor/frontend/new/tailwind.generated.css --minify
```

Font Awesome 的 CSS 和字体位于 `apps/processor/frontend/new/vendor/fontawesome/`；打包与迁移
不得遗漏该目录。`tests/test_new_frontend.py` 会校验四个新版页面只引用本地关键样式、静态
路由可访问，并确保 `.woff2` 以 `font/woff2` 返回。

浏览器缓存导致代码未更新时，先使用 `Ctrl+F5` 强制刷新，再检查开发者工具 Network 中返回的 JS 是否为当前文件。不要通过复制同一份逻辑到多个页面解决缓存问题。

### 4.4 隔离测试环境

测试网站使用独立端口和独立数据副本，不修改正式 `data`：

```powershell
.\start_test_processor.ps1 -Python "D:\Myanaconda\python.exe"
.\start_test_collector.ps1 -Python "D:\Myanaconda\python.exe"
```

访问 `http://127.0.0.1:8001/app`。首次创建或需要重新从正式素材初始化时：

```powershell
.\start_test_processor.ps1 -ResetData
```

测试环境位于 `runtime/test_environment`。正式环境和测试环境仍会控制同一个本机剪映，不要同时提交真实导出任务。

## 5. 核心调用链

### 5.1 从网页提交到导出

1. 前端提交 `/api/render` 或 `/api/render/batch`。
2. `src/jyd_probe/web_api.py` 校验媒体、母版和素材引用。
3. 批量请求通过维度候选展开、去重和数量限制生成子任务。
4. `src/jyd_probe/task_store.py` 持久化批次及任务状态。
5. `RenderJobQueue` 顺序执行，或等待 Agent 领取。
6. `src/jyd_probe/render_job.py` 准备视频源或母版副本。
7. 按顺序应用字幕、文字、音频、特效、贴纸、画面套装和封面。
8. 保存草稿并调用剪映 UI 自动化导出 MP4。
9. 状态和输出写回 `data/web_storage`，前端轮询展示结果。

### 5.2 Render Job

稳定结构版本为 `jyd.render_job.v1`。主要入口：

```python
from jyd_probe.render_job import run_render_job, run_render_job_file

result = run_render_job_file("job.json")
print(result.as_dict())
```

命令行调试：

```powershell
D:\Myanaconda\python.exe .\tools\jobs\run_render_job.py `
  --job .\examples\render_job_video.example.json
```

完整字段说明见 `docs/RENDER_JOB_SCHEMA.md`。修改任务结构时应同时更新：

- `render_job.py` 的解析与校验。
- `web_api.py` 的媒体和素材引用解析。
- 前端任务构造逻辑。
- `examples` 中至少一个示例。
- 对应自动化测试和 `docs/RENDER_JOB_SCHEMA.md`。

### 5.3 草稿处理顺序

`render_job.py` 是业务编排入口，底层职责分散在以下模块：

| 模块 | 主要职责 |
| --- | --- |
| `draft_crypto.py` | 高版本草稿检测和解密 |
| `draft_factory.py` | 从单个 MP4 或按顺序排列的多个原始视频创建基础草稿 |
| `draft_transfer.py` | 草稿复制、重定位和元数据处理 |
| `draft_compat.py` | 剪映版本兼容字段处理 |
| `content_replace.py` | 视频、文字、音频和特效的基础修改 |
| `subtitles.py` | 长文本切分、SRT 生成和字幕导入 |
| `text_asset_apply.py` | 花字和复合文字素材应用 |
| `sticker_apply.py` | 全屏贴纸和四角贴纸应用 |
| `visual_variant.py` | 镜像、人物定位、裁剪和背景填充 |
| `cover_apply.py` | 封面帧、矩形和文字轨道 |

新增处理步骤时，要先确定它在时间线中的顺序以及是否会改变草稿总时长。不要在多个模块中重复修改同一轨道。

## 6. 素材库与母版

### 6.1 公共素材与个人素材

所有素材类型都应通过统一的清单或 bundle 结构被读取，避免运行时依赖原电脑的剪映缓存绝对路径。

```text
data/libraries/<kind>/              公共素材
data/personal_libraries/<kind>/     本机采集素材
```

常见 `<kind>`：

- `audio_library`
- `effect_library`
- `font_library`
- `sticker_library`
- `corner_sticker_library`
- `text_effect_library`
- `text_style_library`
- `text_template_library`

四角贴纸示例结构：

```text
corner_sticker_library/
  bundles/<素材标识>/...
  manifest/sticker_manifest.json
```

迁移个人素材时复制整个 `data/personal_libraries`，不能只复制资源文件而遗漏 manifest。完整安装包目前主要自动带入 `data/libraries`；运行后采集到 `personal_libraries` 的内容需要明确决定是否随交付包分发。

### 6.2 素材管理状态

素材管理支持重命名、分类、启用/停用、软删除和恢复。软删除不会立即物理清除文件，而是在元数据中标记为回收站状态；默认保留 7 天后由生命周期清理器删除。

涉及素材删除时必须使用 `asset_admin.py` 和现有 API，不要在前端直接拼路径删除文件。

### 6.3 母版

母版位于：

```text
data/template_library/<template_id>/
  draft/
  template_meta.json
```

母版可能来自高版本加密草稿。导入阶段负责解密、分析、复制依赖和生成元数据；生成任务应引用 `template_id`，不要重新读取用户原始草稿路径。

复合文字模板通常依赖人工排版，剪辑母版默认应保持原样，不能作为普通字体、BGM 或特效一样自动参与随机变化。

## 7. 配置与环境变量

源码启动脚本会设置大部分变量。常用变量如下：

| 变量 | 作用 | 常见默认值 |
| --- | --- | --- |
| `JYD_WEB_STORAGE_ROOT` | 任务、上传和输出根目录 | `data/web_storage` |
| `JYD_RESULT_LIBRARY_ROOT` | 新版最终变体成果归档根目录 | `D:\auto` |
| `JYD_DATABASE_PATH` | SQLite 控制库 | `data/web_storage/control.db` |
| `JYD_TEMPLATE_LIBRARY_ROOT` | 母版库 | `data/template_library` |
| `JYD_PERSONAL_LIBRARY_ROOT` | 个人素材根目录 | `data/personal_libraries` |
| `JYD_WEB_DRAFT_ROOT` | 实际剪映草稿目录 | 自动检测或手工指定 |
| `JYD_DRAFTC_EXE` | `jy-draftc.exe` 路径 | `vendor/jy-draftc` 或打包资源 |
| `JYD_EXECUTION_MODE` | `embedded` 或 `agent` | `embedded` |
| `JYD_ALLOW_LOCAL_FILE_ACCESS` | 是否允许网页引用本机路径 | 源码单机启动为 `true` |
| `JYD_AUTH_SERVER_URL` | 统一账户中心地址 | 由部署配置决定 |
| `JYD_AUTH_TIMEOUT_SECONDS` | 数字人网站普通 API 请求超时 | `30` |
| `JYD_CONTENT_ANALYSIS_MAX_IN_FLIGHT` | 整机豆包分析 HTTP 硬上限（不可超过 10） | `10` |
| `JYD_CONTENT_ANALYSIS_QUEUE_MAX` | 跨项目豆包分析有界等待队列 | `1000` |
| `JYD_CONTENT_ANALYSIS_TOTAL_TIMEOUT_SECONDS` | JYD 单次分析全链路总预算 | `600` |
| `JYD_CONTENT_ANALYSIS_CONNECT_TIMEOUT_SECONDS` | 连接数字人服务器超时 | `10` |
| `JYD_CONTENT_ANALYSIS_RETRY_MAX` | 未确认准入/队列满/熔断时同操作重试上限 | `2` |
| `JYD_H3_DOWNLOAD_WORKERS` | 整机 H3 下载硬上限（不可超过 10） | `10` |
| `JYD_H3_DOWNLOAD_MIN_WORKERS` | H3 自适应并发下限 | `2` |
| `JYD_H3_DOWNLOAD_ADAPTIVE_ENABLED` | 是否按普通 API 健康度在 2～10 路间调节 | `true` |
| `JYD_H3_DOWNLOAD_QUEUE_MAX` | H3 有界等待队列 | `1000` |
| `JYD_H3_DOWNLOAD_VALIDATE_WORKERS` | H3 媒体校验并发上限 | `2` |
| `JYD_H3_DOWNLOAD_CONNECT_TIMEOUT_SECONDS` | H3 媒体连接超时 | `10` |
| `JYD_H3_DOWNLOAD_READ_IDLE_TIMEOUT_SECONDS` | H3 连续无数据超时 | `120` |
| `JYD_H3_DOWNLOAD_TOTAL_TIMEOUT_SECONDS` | H3 单片段总下载时限 | `3600` |
| `JYD_H3_DOWNLOAD_MIN_FREE_GB` | 启动/续写下载所需最小磁盘余量 | `20` |
| `JYD_H3_DOWNLOAD_BATCH_MAX_GB` | 单个 H3 批次当前版本累计下载硬上限 | `100` |
| `JYD_SHARED_PROCESSOR_URL` | 公用工作台地址 | 空 |
| `JYD_AGENT_TOKEN` | Agent 接入令牌 | 空 |
| `JYD_MAX_ACTIVE_JOBS` | 单批最大任务数 | `500` |
| `JYD_MEDIA_RETENTION_HOURS` | 上传媒体保留时间 | `24` |
| `JYD_TEMPLATE_RETENTION_HOURS` | 临时母版保留时间 | `48` |
| `JYD_DRAFT_RETENTION_HOURS` | 生成草稿保留时间 | `48` |
| `JYD_OUTPUT_RETENTION_HOURS` | 成功输出保留时间 | `72` |
| `JYD_ASSET_TRASH_RETENTION_DAYS` | 素材回收站保留时间 | `7` |

发布包优先使用 `data/processor_config.json` 和 Windows 启动器保存的配置。开发环境不要把真实令牌、管理员密码或生产地址提交到源码。

### 7.1 数字人清晰片段契约

- `ProjectCompositionCoordinator.REMOTE_COMPOSITION_ACTIVE`、`PROJECT_ITEM_STATUSES`、
  `ACTIVE_ITEM_STATUSES`、前端进度和轮询集合必须同时包含 `VIDEO_ENHANCING`。
- 云端主视频下载已经是 SeedVR2 清晰片段。本地仍登记为 `original_video_segment`，因为它
  表示进入项目的原始有序分段；必须通过 metadata 区分 `seedvr2_upscaled`。
- `source_download_url` 只表示云端保留了数字人源片段，本地 4A 不自动下载该文件。
- 4B、字幕、BGM、变体与成果库继续消费工作台已落盘的清晰分段或 `base_video`，不得再次
  调用 SeedVR2。

### 7.2 RunningHub 取消后的阶段重建

- 工作台重试时把项目当前 `settings.digital_human.resolution` 传给云端，但该值只用于数字人
  阶段取消后的新数字人命令；它不决定取消发生在哪个阶段，也不触发 SeedVR2 回退。
- 数字人阶段取消：重新创建数字人 RunningHub 任务；SeedVR2 阶段取消：复用已保存数字人 MP4，
  只重新创建 SeedVR2 48G 任务。两种情况都不能复用被取消的外部任务 ID。
- 本地必须在云端接受请求后才把操作改为 `RUNNING`。远端返回 4xx/5xx 或抛出异常时，应立即把
  刚创建的操作改为 `FAILED/COMPOSITION_FAILED`，避免页面永久显示“完整成片生成中”。

### 7.3 RunningHub 双池费用确认与本地快照

- `/api/new/runninghub-execution-accounts` 只代理云端安全摘要。`same_account_v1` 沿用一组数字人
  ID；`dual_pool_v1` 必须同时展示并提交数字人、SeedVR2 两组非空内部 ID，不得接收或落盘 Key。
- `ProjectCompositionCoordinator` 在每个 `COMPOSITION_GENERATE` 操作中冻结 `execution_mode`、
  `runninghub_execution_account_ids` 和 `seedvr2_execution_account_ids`。同一幂等键改变任一项均
  拒绝；升级前缺少模式字段的操作按 `same_account_v1` 继续恢复。
- HTTP 请求只创建持久化 `PENDING` 行并快速返回，后台线程逐行交接。云端响应的权威模式若与
  本地快照不一致，该行失败；不得静默切分支或重提。重启恢复继续使用原两组快照和行级幂等键。
- 费用确认显式显示当前“一控多/双池”。云端 `composition.execution_assignments` 的安全逐分段
  摘要在启动与每次轮询时复制到 `COMPOSITION_GENERATE.result`；表格据此显示实际账号，未预留
  阶段显示“待分配”。账号名称仅用于操作定位，Key、指纹、Base URL 和 App ID 不进入本地。
- 账号清单中的 `account.balance` 是云端 `accountStatus` 缓存的安全摘要。前端只显示
  `remain_coins` 和缓存新鲜度；缺失时显示“RH 币未知”，不得自行调用 RunningHub、推算余额，
  也不得因为摘要未知而改变本次默认勾选。

## 8. API 与状态存储

开发时以 FastAPI 自动文档 `/docs` 为当前接口事实来源，专题说明见 `docs/WEB_API.md`。

主要 API 分组：

- `/api/auth/*`：用户登录和登录接力。
- `/api/admin/*`：账户、素材和测试批次管理。
- `/api/media/*`：视频和音频上传。
- `/api/draft-imports`、`/api/templates/*`：母版导入和读取。
- `/api/assets/*`、`/api/local-assets/*`：公共及个人素材。
- `/api/render`、`/api/render/batch`：单任务和批量任务。
- `/api/jobs/*`、`/api/batches/*`：状态、结果、重试、取消和下载。
- `/api/agents/*`：处理机注册、心跳、领取和回传。
- `/api/new/projects*`：新版统一项目、脚本行、素材版本、状态和可执行操作；`POST /{id}/items`
  采用追加语义，已有行进入生成后仍可新增独立草稿行，不得退化为整项目 `PUT inputs`。
- `/api/new/script-imports/preview`：严格解析两列 `.xlsx`/`.csv` 脚本。
- `/api/new/projects/{id}/images*`、`image-mapping`：项目图片池、逐行图片版本和后端分配策略；
  文件选择器本次返回的每个文件都创建新的项目图片记录，不按文件名或 SHA-256 跳过；删除已
  分配图片时对非运行行自动改用剩余图片。
- `/api/new/projects/{id}/image-mapping-scope`：把选中脚本行保存为本次人物图换图范围，空数组
  清除范围。范围保存于既有行级 `settings_json.image_mapping_target`，不升级 schema；范围非空时
  批量映射只处理范围内行，且可用 `image_ids` 限制为刚上传的一组项目内部图片 ID。
- `/api/new/voices*`、`/api/new/voice-creations*`：当前数字人账号的官方/自定义音色、试听和声音制作。
- `/api/new/voices/{id}/activate`、`DELETE /api/new/voices/{id}`：显式激活或移除自定义音色卡。
- `/api/new/projects/{id}/voice`：原子地把已保存音色设为项目默认值并应用到全部脚本行。
- `/api/new/projects/{id}/items/{item_id}/voice`：覆盖单个脚本行的音色。
- `/api/new/projects/{id}/audio*`：项目声音生成、状态同步、单行重试、试听和下载。
- `/api/new/h3/accounts`：读取安全 H3 执行账号摘要。每次调用都由数字人云端强制刷新
  `accountStatus`；响应只带本次 RH 币、查询时间和可选状态，余额为 0、未知或读取失败均禁选。
  该代理调用使用 150 秒上限，覆盖多个账号实时查询的服务端等待时间。
- `/api/new/projects/{id}/h3/settings`：H3 默认参数；历史 `identity_image_ids` 仅兼容读取，正式前端
  不再维护第二套人物图选择。
- `/api/new/projects/{id}/items/{item_id}/h3/reference-video`：逐行参考视频素材版本。
- `/api/new/projects/{id}/items/{item_id}/h3/overrides`：逐行 H3 差异参数。
- `/api/new/projects/{id}/h3/audio-review`：保留给兼容调用的音频锁定接口；正式前端不暴露
  独立按钮，`h3/prepare` 会在“生成视频”后自动锁定所选 MiniMax 音频，且不触发 H3 费用。
- `/api/new/projects/{id}/h3/prepare|confirm|status`：所选行 H3 费用快照、确认和结果回填；
  `/h3/segments/*` 提供段级重试、主动重生成、取消和下载。
- `/api/new/projects/{id}/ltx/state|generate|refresh`：同步 JYD 权威原稿与最新 MiniMax 音频，启动或
  刷新隐藏 LTX/SeedVR2 引擎；`PUT /items/{item_id}/ltx/source-video` 版本化上传源视频并只失效
  该行画面与后期，`POST /items/{item_id}/ltx/retry` 只重试该行失败引擎阶段。
- `/api/new/projects/{id}/composition*`：4A 画面启动、真实状态同步和失败阶段重试。
- `/api/new/projects/{id}/items/{item_id}/base-video`：下载当前标准化基础视频。
- `/api/new/postprocess/options`：返回实际可读的真实字体和现有 BGM 素材。
- `/api/new/projects/{id}/postprocess*`：4B 浏览器预览配方生成与状态查询。
- `/api/new/projects/{id}/items/{item_id}/postprocess/export`：用户明确下载时按需启动一次剪映导出。
- `GET/POST /api/new/projects/{id}/items/{item_id}/current-video`：下载当前视频或上传本地视频并切换版本。
- `GET /api/new/projects/{id}/videos/download`：一次性 ZIP 下载项目所有未变体当前成片。
- `GET /api/new/projects/{id}/items/{item_id}/h3-segments/download`：从“片段检查”按当前批次顺序下载
  已落盘的 H3 原始分段；单段返回 MP4，多段返回带顺序清单的一次性 ZIP。
- `/api/new/projects/{id}/items/{item_id}/original-materials`：下载单个原始片段或包含顺序清单的多片段 ZIP。
- `POST /api/new/projects/import-h3-handoff`：新交接导入 `h3.jyd_handoff.v2`，历史读取兼容 v1。
  v2 必须声明完整 H3 原生音画母版、`separate_h3_generated_audio` 分轨策略、H3 权威音频和
  `h3_segment_windows_then_funasr` 字幕来源。交接编号检查和项目、H3 权威音频、H3 分段字幕
  窗口、静音 `base_video`、外部关联写入必须位于同一个 `BEGIN IMMEDIATE` 事务；相同账号和
  `handoff_id` 的并发请求返回同一项目，任何中途异常整体回滚。输入 MiniMax 音频/raw cues
  只保留 provenance，不能进入 v2 最终播放时间线。
- 4B Coordinator 复用 `create_app()` 启动时已校验并计算摘要的语义视觉 catalog；生成、预览和
  导出不得对整套媒体重复做 SHA-256。素材 catalog 更新后通过重启服务加载新快照。

新版浏览器把同一项目拆成两个主工作页：`/app/new` 负责脚本导入、声音生成、试听与审核，
`/app/new/generate` 负责图片、逐行参考视频、画面参数、生成状态和结果检查。两页复用同一
`index.html` 和项目 API，以路径选择显示职责，不复制前端状态或数据库记录。成果库为
`/app/new/gallery`，声音中心为 `/app/new/voices`。这些页面均受普通站点会话保护；公开的 `/app/new/login` 调用现有
`/api/auth/login`，由工作台后端向数字人账号中心验证账号并把令牌保存在 HTTP-only
Cookie 中。前端只通过 `/api/auth/session` 读取用户摘要，通过 `/api/auth/logout`
退出，不得读取或保存数字人访问令牌。

远端普通账号校验由 `AuthCenterClient.verify()` 统一治理：成功结果只在进程内缓存 5 秒，相同
token 的并发调用使用 single-flight 合并，不同 token 仍可并行；认证中间件把用户写入
`request.state.jyd_site_user`，项目接口不得在同一请求内再次远程校验。登录、退出、换号、接力、
401 和正常关闭均失效相关状态。远端校验固定使用 8 秒短超时，10 秒内 3 次传输失败后独立熔断
15 秒，半开阶段只允许一个探测；业务拒绝不计入连接故障。缓存、等待对象和日志都不得落盘或
暴露 token。中间件必须通过 `run_in_threadpool()` 执行阻塞式校验，不能在 ASGI 事件循环中直接
调用 `urlopen`；否则即使已经合并为一次请求，首次慢校验仍会冻结其他本地页面接口。

任务和批次会同时涉及 SQLite 元数据及 `data/web_storage` 下的 JSON/媒体文件。调试数据异常前先停止服务并备份整个 `data/web_storage`，不要只复制或修改 `control.db`。

新版项目 API 只允许普通数字人账号访问，技术管理员会话不能代替普通账号成为项目
所有者。项目详情中的 `allowed_actions` 是页面按钮权限的唯一业务来源；前端不得根据
显示文本或本地定时器自行推进项目状态。新版页面已经完成登录、脚本/图片输入、声音和
画面 4A/4B 模块。声音编排由 `project_audio.py` 完成：工作台只把脚本、音色和语音参数提交
给数字人后端 MiniMax 批次能力，强制停在 `AWAITING_REVIEW`，下载音频和原始时间戳后
创建本地不可覆盖素材版本；声音阶段不上传图片。`project_composition.py` 只有在用户再次
确认费用后才上传该行当前图片，调用数字人后端把图片与已审核音频绑定并放行既有任务，
保存全部成功原始分段及标准化 `base_video`，并按真实后端状态驱动页面。
它不添加字幕/BGM、不创建最终 `composition_video`，也不生成变体。音频完成后到 4A
启动前，图片仍可替换；4A 上传的永远是提交时的当前图片。

H3 画面链由 `project_h3.py` 单独编排，入口位于 `/app/new/generate`。它只消费调用时显式
选择的 `item_ids`：读取每行最新 MiniMax 历史音频（即使当前播放音频已经是上一版 H3 权威
音频），在 `h3/prepare` 内自动把 `AWAITING_REVIEW` 锁定为本次输入；原稿使用当前音频元数据
哈希所绑定的 raw cues 文本，不再拿可后改的表格标点做远端严格比较。每行人物图直接读取
`inputs.image`，相同图片只上传一次，云端 row 合同只为该行提交一个
`reference_image_asset_ids`；图片的逐行循环或一图多行完全沿用现有 `image_mapping`。然后上传
该行冻结参考视频，把批次默认参数及 `settings.h3.overrides` 交给云端。正式前端只
保留声音预览和“生成视频”，不展示第二个审核操作；`h3/confirm` 仍只确认 H3 费用，不改写
声音版本。云端成功后，`project_h3_media.py` 保留并
合并每段 H3 原生音画、归零时间戳、拆出静音基础视频和 H3 权威音频，并以实际分段窗口调用
FunASR；回填只更新原 `ProjectItem`。未选行不继承批次状态，前端自动后期也只提交当前
`remote_batch_id` 对应且已回填的行。换人物图/批次参数使项目 H3 画面失效，换行级覆盖或
参考视频只使该行失效；待确认、排队或运行期间一律禁止修改输入或用新幂等键重复准备。

H3 权威音频和静音基础视频的 metadata 必须同时保存冻结原稿的 `script_sha256` 与
`script_length`。4B 只有在当前音频、raw cues、内容分析和原稿版本一致时才使用语义字幕单元；
缺少该绑定会退回粗粒度 H3 分段窗口，可能把“第一…、第二…”等相邻枚举项排进同一字幕。
历史 H3 项目在同步同一 `h3_segment_signature` 且远端分段能重建当前冻结原稿时，可原子补齐
这两个字段；修复只解除旧的派生成片引用并清空旧 `render_cues`，保留 H3 音视频、旧成片文件
和素材历史，随后重新生成本地 4B 预览，不得重新发起付费 H3 任务。

自 2026-08-25 起，`main` 的 `/app/new` 只展示“多参考”入口，新项目固定写入
`settings.generation_mode=minimax_h3_ref2va`；前端不再提供普通数字人和视频对口型切换控件，
面向用户的文案也不显示内部模型简称。三路前端完整快照保存在
`archive/three-generation-modes-20260825`。后端仍兼容读取历史项目中的
`runninghub_digital_human`、`minimax_h3_ref2va` 和 `ltx_lip_sync`，但只有多参考是 `main`
的正式入口。

历史视频对口型链仍由 `project_ltx.py` 读取当前原稿、最新 READY MiniMax 历史音频引用和每行源视频，并交给
本机回环 LTX 引擎；该引擎按 20 秒以内分段执行 LTX，再固定逐段执行 SeedVR2 48G。完成的基础
视频回填为 `source_type=ltx`，之后继续走与另外两条路线完全相同的字幕、BGM、语义视觉、剪映
模板、完整预览、变体和成果链。普通数字人的服务商临时 2 秒静音不能进入 LTX：LTX 始终使用
MiniMax 原音；从 H3 切回普通数字人或 LTX 时，`ProjectStore.set_generation_mode` 恢复最新
MiniMax 音频及其保存的 raw cues。替换 LTX 源视频只清除该行当前基础视频和后期结果；LTX 或
SeedVR2 运行期间，隐藏引擎拒绝原稿、声音版本和源视频变化，避免已计费任务与当前输入脱节。
源码联调必须从 `ltx_lip_sync_workbench/START-LOCAL.cmd` 统一启动；该入口生成一次性管理令牌并
同时传给 `8010` 与 `8791`。分别手工启动而没有共享令牌时，JYD 不创建内部引擎客户端，也不会
接受视频上传。
新配置默认 `continuity_mode=loop_anchor`、`generation_tail_seconds=0.1`。`loop_anchor` 要求目标行
已有图片分配；该图由云端固定映射为 `<Picture 1>` 并同时描述为每段首帧和尾帧，不得沿用普通
多图模式把参考视频抽帧插到第一槽。`fast` 与 `soft_chain` 仍是合法行级覆盖。
项目分辨率变更使既有基础视频失效时，`project_composition.py` 检测
`DIGITAL_HUMAN_RESOLUTION_CHANGED`。已有云端数字人源片段的行只调用
`AuthCenterClient.backfill_workbench_video_enhancement()`，不上传图片、不调用数字人启动接口；
云端对整行补建或重试 SeedVR2 48G 阶段。本地继续轮询同一 `remote_item_id`，下载清晰片段和
新基础视频后由 `ProjectStore` 清除失效原因。补跑操作的 `scope` 固定为
`seedvr2_backfill_only`，便于日志和费用审计。
若该行在数字人阶段被 RunningHub 手动取消、因而没有任何已下载源片段，则不能误走 SeedVR2
补跑：重新生成改为上传当前图片，并通过原声音关联调用画面启动接口；云端保留已审核音频，
按当前分辨率创建全新的数字人命令。失败行即使同时具备 start/retry 能力，前端批量分组也只
进入 retry 一次，防止同一行重复提交和重复计费。
`project_audio.py` 不提交本地硬编码的 RunningHub 提示词；行级未显式设置时由数字人网站
配置的默认提示词接管，避免工作台旧值截断服务器配置。

管理员首次 4A 启动前，前端使用统一账号会话的 `is_admin` 决定是否读取
`/api/new/runninghub-execution-accounts`。管理员每次费用弹窗按服务端默认列表重新全选，至少
选择一项，只把内部 ID放入 `runninghub_execution_account_ids`；普通用户请求不含该字段。
已有流水线的 retry/backfill 继续用云端锁定账号，不允许前端重新选择。

批量 4A 不得在请求线程逐行上传。`ProjectCompositionCoordinator.start()` 只校验并创建逐行
`PENDING` 操作；`ProjectCompositionStartDispatcher` 使用最多 4 个线程调用
`start_pending_operation()`。`ProjectStore.claim_pending_operation()` 以 SQLite 条件更新原子
认领为 `STARTING`，云端接受幂等请求后才转 `RUNNING`。重复轮询还受内存 scheduled set 去重，
但正确性不能只依赖内存。进程初始化调用 `recover_interrupted_composition_starts()`，只把
`STARTING` 恢复为 `PENDING`；登录令牌只作为内存参数，严禁写入 payload、结果或日志。
后台按 payload 的图片资产 ID读取历史版本并复核 SHA-256，不能改用行当前图片。云端 5xx
保留 PENDING 供原幂等键恢复，明确/本地错误只失败当前行。实际 RunningHub 容量仍由云端
Worker 控制，本地 4 线程不是账号并发配额。

当前批次的 4A 状态仍按 3 秒轮询。为了避免用户切换批次后旧项目永久保留本地 `RUNNING`，
新版页面使用同一已登录会话每 60 秒重新读取项目列表，并顺序调用其他活动批次既有的
`composition/status`。页面首次打开时立即执行一次补同步；关闭浏览器后不持久化访问令牌，
下次登录再恢复。该补同步只驱动既有幂等操作、查询云端终态和下载结果，不创建新的费用确认，
单个旧项目同步失败也不得打断当前项目的编辑与轮询。

`project_postprocess.py` 负责 4B：保存 MiniMax 原始 cues 不变，使用所选真实字体文件的
glyph advance 测量宽度，把过长文本在原 cue 时间内派生为连续的单行 render cues。
语义排版先修复过短逗号前缀，再把剩余软/硬标点边界视为不可跨越的分句边界；局部字宽
切分统一保护数字与量词表达式，并按词性硬保护动词后的结果/趋向补语（如“排/出”、
“拿/出来”“做/完”“改/掉”），避免出现语义未完成的字幕断裂。
普通 4B 先把 `base_video`、render cues、字体和 BGM 登记为浏览器预览配方，再向
`RenderJobQueue` 提交 `skip_export=true` 的草稿生成任务；只有草稿目录和
`draft_content.json` 均存在时才进入 `COMPOSITION_READY`。此阶段不编码 MP4。固定参数为居中、
画面宽度 `0.8`、`transform_y=-850/1920`
（剪映 1080×1920 参考位置 Y=-850）、`DouyinSansBold` 14 号、默认白字、黑色 `0.06` 描边。
BGM 不使用固定音量：`bgm_loudness.py` 先构造与剪映相同的末尾对齐、反向循环、交叉衔接和
渐入时间线，再通过 FFmpeg `loudnorm/ebur128` 测量实际使用节目，而不是整首曲目。普通音乐
目标低于人声 11 dB、强人声音乐低于人声 15 dB；增益范围为 `-30..+6 dB`，并受节目真峰值
`-6 dBTP`、短时响度差普通 7 dB/强人声 10 dB 约束。失败分别回退 `-10/-14 dB`
（线性 `0.3162/0.1995`）。结果以 `speech-relative-program-lufs.v2` 冻结到
`postprocess.bgm_volume` / `bgm_loudness`，浏览器预览、普通导出和变体共用；不接受前端人工音量参数。
4B 与变体的 BGM 任务固定 `align_to_end=true`、`crossfade_us=200000`。渲染器从正文视频结尾
向前规划源音乐：音乐更长时裁取尾部等长区间；音乐更短时最后一轮必须完整播放 `0..end`，
前面的轮次再从后向前补足，最早一轮允许只取音乐尾部。相邻轮次放到两条交替音轨并使用
0.2 秒淡入淡出重叠，最后一轮不淡出，确保停在素材自身自然结尾。浏览器动态预览必须镜像
同一反向计划，不能恢复为从 0 开始的 `% duration` 循环。
项目成片的 BGM 渐入按正文时长的 10% 计算、最长 1.5 秒，并把同一 `fade_in_us` 写入响度
快照和 `audios[]`；`VIDEO_FADE_OUT_US` 当前为 0。普通 4B、变体和浏览器预览共用这些值，
后续调整时不得在草稿 JSON 或前端另设硬编码。浏览器使用 Web Audio `GainNode` 读取最大 2.0
的冻结线性增益，并以压缩器只做超过安全峰值的兜底；不能再用 HTML `audio.volume` 把大于
1.0 的合法增益静默截断。
浏览器直接读取同一冻结样式，不得为溢出字幕临时缩字；
无法可靠排版时状态为 `REVIEW_REQUIRED`，不会静默显示溢出字幕。只有用户明确下载普通
成片时才调用 `postprocess/export`，并使用 `existing_draft` 对已冻结草稿执行 MP4 编码。正常路径不
重建字幕、BGM、封面和视觉时间线；升级前没有草稿结果的旧预览先提交独立 `skip_export=true`
草稿准备任务，准备成功后由客户端再次调用同一导出接口。唯一恢复例外是：剪映首页连续 5 次
返回 `DraftNotFound` 时，导出任务使用提交时一并冻结的完整重建配方创建一个新名称草稿，保留且
不覆盖旧草稿，再尝试识别 5 次；第二轮仍失败才停止。已知 UIA `COMError` 可重建控制器重试，
但不得误判成草稿丢失并触发时间线重建。后续变体必须把基础/上传视频与已
冻结的字幕、BGM 配方合并到同一个变体任务中一次导出，不能依赖一个预先导出的普通成片。
若该按需导出失败但冻结草稿、`base_video` 和 `PREVIEW_READY` 配方仍在，行级失败重试必须直接以新的
幂等键再次调用 `postprocess/export`；不得把全项目行重新提交给 `postprocess/generate`。
若 4A 返回多个 RunningHub 原始片段，浏览器预览使用已按音频时长标准化的 `base_video`；
4B 按需导出和模块 6 使用按 `video_index` 排序的 `video_sequence`，让剪映草稿保留真实分段。
每段目标时长来自原分段计划：素材过长裁尾，素材略短则对该段画面轻微放慢到目标时长；
所有片段原声静音，并从 0 写入一条完整、已审核的 MiniMax 音频。字幕仍直接使用 MiniMax
绝对时间戳，因此供应商 MP4 容器时长误差不会在后续片段中累计。相邻片段继续使用 250000
微秒剪映原生叠化，画面、权威语音、字幕、BGM 和封面共享同一绝对时间轴。

项目封面属于 4B 后处理冻结配方，不属于模块 6。`postprocess.cover_title` 保存两行、每行最多
5 字的文案；普通导出与所有变体统一调用 `build_project_cover()`。存在基础视频时按其冻结的
`input_image_sha256` 从当前图和 `asset_history.input_image` 回溯原图作为底图，
匹配原图缺失时拒绝生成可能错配的封面；没有冻结哈希的旧数据才使用当前上传人物图。
固定 3 帧、思源粗宋和受控视觉参数。变体请求不能自定义封面。标题为空时不生成占位封面。
`normalize_cover_title()` 是 AI 标题、人工保存、历史数据、浏览器预览、普通导出和变体共用的
输出安全门。结构或长度不合法仍按原契约报错；低风险体重管理词做自然中性改写，硬风险整组
回退为“生活提醒/理性看待”。不得用谐音字、近形字、emoji、拼音或符号实现审核规避。
浏览器动态预览在时间轴开头显示同一人物图、两行标题和固定视觉参数；“刷新动态预览”只
重算浏览器配方，不伪装成 MP4 导出。标题或后处理设置使旧成片指针失效时，页面明确显示
“旧成片已过期”，并提供“重新导出带封面 MP4”入口调用 `postprocess/export`。旧素材版本保留。
参数和后续统一内容分析返回契约见 [AI_TITLE_AND_COVER_20260810.md](AI_TITLE_AND_COVER_20260810.md)。
正文视频顶部与封面标题解耦：`build_top_title_texts()` 固定生成一行“世界冠军带你自律”，字号
19、Y=1535、红字白描边；历史 `top_title` 只保留接口兼容，不再影响浏览器预览或剪映导出。

建草稿前必须用真实画面时长裁剪所有定时视觉和来源文字。时长优先读取
`base_video.metadata.duration_us`，旧行回退原始分段结束时间，再回退当前音频或其绑定 raw cues；
起点已在画面外的项丢弃，跨越片尾的项裁短。不能用脚本文字估算时长直接写入草稿。
4A 基础视频下载完成后会用与剪映建草稿相同的媒体探测器覆盖 `duration_us`，并把云端分段计划值
保存在 `planned_duration_us` 供诊断。历史数据或容器帧取整仍可能与草稿相差不足一帧；仅新增文字
允许在 30fps 一帧（33334 微秒）内裁到实际片尾，更大的越界继续作为错误绑定失败。

`ProjectPostprocessCoordinator.sync()` 必须扫描全部仍为 `PENDING/RUNNING` 的 4B 操作，
不能只检查每行最新一条。更新操作时通过 `operation_id` 精确定位；被新尝试取代的旧操作只
回收自身终态，不覆盖当前行状态、字幕或成片指针。
同一 API 进程内，4B 生成、按需导出和状态同步按“数据库路径 + 用户 + 项目”共用可重入锁，
避免多个不同幂等键在任务号回写前同时越过行状态检查。同步发现仍为 `PENDING/RUNNING`、但
从未取得剪映 `job_id` 的中断操作时，以 `POSTPROCESS_SUBMISSION_INTERRUPTED` 收口；若该行
已有结构完整的历史冻结草稿则恢复 `COMPOSITION_READY`，否则进入可重试的
`COMPOSITION_FAILED`。部署仍只支持一个中央 API 进程共同管理该 SQLite，不能把进程锁解释为
多 API 进程写同库支持。

新版页面把字幕效果卡直接放在表格“字幕样式”列，点击效果卡才打开字体和颜色配置；BGM
继续在相邻列直接选择。修改任一设置只把对应脚本行退回 `BASE_VIDEO_READY` 并保留
`base_video`、付费任务和历史成片。前端用同一个 `POST /postprocess/generate` 仅提交该行
`item_id`，即可重新派生字幕、刷新浏览器 BGM 预览并重建该行剪映草稿；服务端只处理请求中明确列出的脚本行。
批量工具栏的“刷新预览”复用同一契约：有勾选时使用选中行，否则使用当前批次全部
`base_video` 已存在且不在运行中的行。前端先逐行以 `force_retry=true` 失效旧 4B 配方，再用
一个 `/postprocess/generate` 请求提交明确的 `item_id` 列表，因此字幕断句、ASR 时间绑定、
自动 BGM 选择和封面会按当前代码重算，并重建可编辑剪映草稿，但不会调用 MiniMax、RunningHub
或编码 MP4。
同一工具栏的“下载视频”把目标行 ID 编码为 `GET /videos/download?item_ids=id1,id2`。后端校验
所有 ID 都属于当前项目并按项目行顺序打包；省略参数继续打包项目全部当前普通成片。
姿态或字幕样式保存提交 `preserve_auto_bgm=true`。当新旧模式都是 `auto` 时，Store 保留当前
`bgm_identity`、`music_selection`、`bgm_volume` 与 `bgm_loudness`，但仍使旧成片失效；批量刷新
预览不提交该标志，因此会按当前算法重新选择和测量音乐。
字幕效果卡固定显示“这是字幕预览”，不绑定脚本或 render cue。BGM 下拉框隐藏内部 `auto`
哨兵：自动 Top1 成功时直接显示解析后的具体曲目，尚无解析结果时显示“无音乐”；提交时仍
保留既有 `bgm_selection_mode=auto`。单行分析按钮在请求开始后立即切换为“AI 分析中”，成功
后直接保存并展示 Top1；手动曲目或手动无音乐不被覆盖。
每条表格任务在任务 ID 下提供 `DELETE /api/new/projects/{project_id}/items/{item_id}` 入口。
后端拒绝删除运行中或内容分析中的任务；其他状态删除时级联清理该行素材版本、操作、外部
关联和未被其他行引用的本地生成文件，再重新排列 `position`。任务可删到 0 行并通过“添加
分段”重新创建。共享图片池及其他任务不删除，前端必须先提示本地记录删除和第三方费用不可撤销。
从音频已就绪点击“生成完整成片”时，只对 RunningHub 费用确认一次，4A 完成后自动执行
4B 并进入视频预览，不再弹出字幕/BGM 二次确认。

模块 5 直接复用 `ProjectStore` 的素材版本和用户归属校验。上传视频以原始请求体写入当前
用户的项目目录，限制为 MP4/MOV/AVI/MKV/WebM 和 `JYD_MAX_VIDEO_UPLOAD_BYTES`；新增
`source_type=user_upload` 的 `composition_video` 并设为当前版本。`ProjectStore` 会保留
旧成片和 RunningHub 原始片段，同时解绑并失效原 MiniMax 字幕。原始素材下载按
`external_ref.video_index` 排序；单片段直接返回文件，多片段使用一次性 ZIP 并附加
`片段顺序清单.json`，响应结束后删除临时 ZIP。
底部“一键下载未变体视频”按用户选中的真实 `item_id` 集合工作，不以点击瞬间 DOM 的 ready
子集重新取样。前端先复用已有 MP4，等待选中行正在执行的草稿任务；旧预览则通过第一次
`POST /postprocess/export` 补建冻结草稿，完成后第二次调用只编码 MP4。每条目标必须进入成功
或失败清单，不能静默跳过。最终只把已有或本轮成功的普通成片通过项目级
`GET /videos/download` 打包；variant 素材不参与，临时 ZIP 在响应结束后删除，全部失败时不发空包。

`project_content_analysis.py` 负责新增智能内容分析模块 5。Excel/CSV 导入、添加分段和编辑
脚本只把相应快照置为 `NOT_REQUESTED`，不发起分析。用户点击“生成声音预览和脚本分析”时，前端在
提交声音任务的同时，对本批声音目标中 `NOT_REQUESTED` 的行调用
`POST /api/new/projects/{project_id}/content-analysis`；协调器为每个需要分析的

`ProjectItem` 单独调用数字人后端 `/api/workbench/content-analysis`，不会把多条脚本
拼成一个模型输入。脚本哈希未变化时，声音重生成不会重做文本分析；普通调用跳过已有
`PENDING`/`SUCCESS`/`PARTIAL`/`FAILED` 尝试，单行显式重试使用 `force_refresh=true`。
网页接口先持久化逐行 `PENDING` 并立即返回，再由最多 4 个后台批次执行器发起远端请求；浏览器
沿用 5 秒状态轮询，因此最长 600 秒的单次远端等待不再同步占用网页请求连接。
所有后台批次共享应用级 `DoubaoRequestManager`：内容分析与兼容视觉分析合计最多 10 路，
按项目轮询且队列有界，不会形成 4×10 的远端突发。同一次操作透传稳定
`analysis_operation_id` 与剩余预算头；只有连接结果未确认、服务器明确队列满或熔断时，才在
总预算内复用原 ID 重试。`GET /api/health` 的 `doubao_requests` 返回活动数、等待数、项目
分布和队列等待 p95，不保存脚本或令牌。
协调器在同一次请求中加入本地生成的 `visual_context`，只包含 catalog 版本、概念描述和
原文字符锚点，不含素材路径或时间。服务端响应在工作台再次核对脚本哈希、长度、三个分支
状态、字幕完整覆盖以及视觉 anchor/concept 后才落盘。刷新重试时，新失败不得覆盖同一脚本
此前已经成功的内容分支。项目批量调用最多并发 10 行，失败按行保存并继续。模块 5 不进行字符到时间轴映射或字体
排版；音乐分支成功后会调用 `ProjectMusicSelector.resolve_for_analysis` 产生不依赖音频时长的
初步 Top1，并通过 `save_item_auto_music_selection` 保存，但不会覆盖显式 manual 设置。

新版工作台把既有多项目能力暴露为批次选择器。`GET /api/new/projects?limit=100` 只用于
列出当前账号自己的项目，切换时再读取目标项目；“新建批次”只清空浏览器当前视图，原项目
及素材仍保留。`POST /api/new/projects/{project_id}/items/batch` 在一个事务内校验容量、已有
任务 ID 和批内重复项，再统一追加 `DRAFT` 行并沿用当前图片映射策略；任何一行失败时全部
回滚。追加表格不执行模型、MiniMax、RunningHub 或剪映操作。

配置表的文章类型筛选直接读取 `settings.source_metadata.article_type`，不复制分类字段；切换
筛选会清空旧勾选，表头全选、序号快速选择、刷新预览和下载视频都只作用于当前可见类型。
`DELETE /api/new/projects/{project_id}` 允许删除没有运行中操作的草稿、失败或完成批次，事务内
级联删除项目记录，并返回不再被其他项目引用的受管文件和成果目录候选。Web 层再次校验文件
必须位于工作台存储根目录，成果目录必须严格位于“成果根/日期/数字批次号”，才执行物理删除；
云端数字人任务和既有第三方费用不受影响。

表格的选择状态只保存在当前浏览器内存，并使用不可见的 `item_id` 调用现有子集接口；界面
可按显示序号、原 `row_key` 或数字范围快速建立选择。选中统一分析使用 `force_refresh=true`；
选中声音通过 audio `item_ids`；选中画面通过 composition `item_ids`，已有 `base_video` 的行
直接进入选中 4B 参数列表。图片、音频或执行条件不足的选中行会在提交付费请求前整体提示。
表格选择还可把所选行锁定为本次人物图换图范围，例如将第 11-30 行设为目标后，前 10 行不再
参与本批分配。人物图上传按当前表格选择分支：未勾选任何行时清除残留换图范围，继续按原有
全项目图片池规则分配给全部可编辑行；勾选行时则先把当前所选行保存为精确换图范围，再为文件
选择器返回的每个本地文件创建新图片，并只把这些新 `image_ids` 交给该范围的批量映射。后端从
目标范围第 1 行重新计数并保存本批图片 ID，刷新或修改 count/loop 时不会混入此前图片池。

`semantic_subtitles.py` 负责智能内容分析模块 6。工作台再次拒绝带大模型时间字段、未连续
覆盖原文或语义属性非法的 `subtitle_units`；MiniMax cue 文本允许省略原文空格/换行，但
所有非空白字符必须精确一致，`~` 不作通配符。每条 cue 的真实 `start_us/end_us` 是唯一
时间锚点，cue 内字符时间只做确定性比例派生。Prompt v19 及更早的普通断点进入排版时仍是软偏好；
本地只把高置信的“类别/问题/评价 → 答案”和较长编号项提升为强语义边界，允许它们在整句
未超宽时增加一条字幕。Prompt v20+ 的字幕已经过云端原文、长度和安全词边界硬校验；v23
默认仍使用最少断点，但三个以上同构并列项允许多一个结构断点。其 `prefer` 断点全部作为
不可跨越边界，本地只能在单个语义段实际超宽时继续细分。旧模型偏好不能仅为节奏增加字幕数量，避免旧分析产生
“第一｜脂肪”或“世界冠军｜张雒”一类短碎片。`project_postprocess.py` 先按每条 raw cue、
段落和除顿号外的显式标点建立不可跨越子句，
再用 `jieba==0.42.1` 的确定性词典分词（`HMM=False`）、词性、数字单位、结构助词和真实字体
宽度对每个子句做全局排版。脚本、分析、当前音频脚本摘要或 raw cues 音频绑定不一致，以及
映射/排版失败时，4B 记录
`semantic_mapping.status=FALLBACK` 并调用原有 `layout_one_line_captions`；raw cues 永久保留。
本模块不执行音乐 Top1。

站姿字幕 `clip_scale` 从 `1.351709192276617` 降为 `1.32`，保持 80% 画面安全宽度，
使当前生产字体的一行容量由约 9.7 个全宽汉字提升到稳定 10 个。Prompt v19 及更早模型返回的
多余断点在不超宽子句内仍可删除，超宽子句只遍历通用
分词允许的字符位置，并以模型断点作为小权重偏好；结构助词不得位于行首/行尾，动词与
结果/趋向补语之间属于硬禁切边界，量词、连接词
和名词组合使用通用语法罚分；完整名词主语后接“已经/正在”等副词引导的谓语时，优先在
主谓之间断开，并禁止把副词单独留在上一字幕末尾。短标点片段不得跨普通逗号或句号强制吞并后文，任何重新分配的
时间都必须留在当前子句和 raw cue 范围内。不能为了行宽均衡拆成“情｜绪”“弯｜路”
“四十｜多”“破罐子｜破摔”或让一条字幕同时包含相邻 raw cues。

`project_music.py` 负责智能内容分析模块 7。内容分析完成时先从当前行已校验的
`music_intent` 和本地 `music_profiles.v1.json` 返回可见的初步唯一 Top1；同一项目批量处理时
按脚本行顺序传递 `recent_identity_counts`，在语义评分之后施加确定性的已使用次数惩罚，
让分数接近的合格曲目适度轮换。4B 自动模式按相同项目计数加入当前 MiniMax 音频真实时长
复核并保存最终 `jyd.project-music-selection.v1` 快照，不保存候选列表或 Top3。声音版本变化
保留已选 identity 并标记 `STALE`，避免界面退回“无音乐”，4B
会按新音频时长刷新绑定。音乐分支失败按项目默认音乐或无 BGM 降级；手动曲目及手动无 BGM
始终优先。变体只冻结继承 4B 最终 BGM。

智能内容分析模块 8 的跨项目验收位于数字人项目
`tests/test_content_analysis_workbench_integration.py`。它直接把数字人服务端
`analyze_content` 的实际响应传入本项目 `_validated_remote_result`、
`map_subtitle_units_to_raw_cues` 和 `MusicProfileMatcher`，覆盖双成功、两种部分成功、安全
索引重算、空格、换行和 `~`。新增测试 `3 passed`；最终完整 mock 回归为数字人
`216 passed`、本项目 `260 passed`。本轮没有真实第三方请求或生产变更。

新版 `/app/new` 不再提供模块 6 的变体生成入口；原表格三列与底部按钮改为 H3 原始分段人工
检查入口。弹层使用响应式换行网格，桌面端每行五张、窄屏依次降为四/三/二/一张，只允许
纵向滚动；视频使用本地已下载的 H3 原始音画且 `preload=metadata`。成功但主观不合格的分段
复用 H3 主动重生成，失败分段复用失败重试，均沿用现有费用确认与历史 attempt 保护。
`ProjectH3Coordinator.sync()` 在保存云端快照前按成功分段增量下载，单次最多三路并发；缓存键绑定
批次、远端 item 和 `segment_id`。`video_delivery.mode=runninghub_direct` 时直接从 RunningHub HTTPS
地址下载，不转发账号中心令牌，以服务端 `result_signature` 换版并记录本机文件 SHA-256；历史
`auth_center` 模式继续绑定云端标准化视频 SHA-256 与完成时间。状态响应中的
`local_preview_ready` / `local_preview_is_current` 只描述本机缓存，不能替代云端任务状态。重生成期间
稳定的 `current.json` 指针保留上一版本，新版短文件校验后原子切换；只有全部当前版本缓存齐全才调用
`prepare_h3_media()` 合并和登记 `base_video`，不得在最终阶段重复下载整行。
`project_variants.py` 和既有 API 暂时作为历史项目兼容能力保留，不删除历史 `variant_video`。

历史 `project_variants.py` 模块推荐设置启用视频特效、全屏贴纸和画面变化套装，组合
选择使用确定性的加权 maximin，而不是随机抽样：裁剪比例、视频特效、全屏贴纸和四角贴纸
的权重大于背景色，并把已有成功签名作为补充生成的距离参照。每行冻结基础视频（用户上传
视频则冻结上传版本）、模块 4B 的 render cues/字体/BGM、项目固定封面和素材身份；项目级生成
可合并为一次 `submit_batch`，行级生成则只提交指定 `item_id`，不会先导出普通
`composition_video`。封面固定 3 帧，封面
视频片段并入主视频轨道首段，临时视频轨道随后删除；底层统一后移所有正文轨道。操作类型为
`VARIANT_GENERATE`、`VARIANT_SUPPLEMENT` 和
`VARIANT_RETRY`；成功文件保存为不可覆盖的 `variant_video`，失败项可原样重试。

`project_results.py` 负责模块 7 的物理归档和成果查询。`project_script_sources` 保存用户原始
XLSX/CSV 的版本与校验信息；`project_result_batches` 使用 SQLite 当日计数器原子分配
`D:\auto\月.日\批次号`。脚本文件先复制到批次目录，模块 6 的 MP4 随后直接输出到该目录。
成果页不把目录扫描结果当作用户归属，而是按 `owner_user_id` 查询项目/素材/剪映批次索引，
再检查 `managed_path` 是否真实存在。这样手工移动或删除文件会显示为缺失，但不会跨账号泄露。

新版表格采用版本化修改而不是完成后永久锁定。非运行中脚本行可以随时修改：脚本或音色
清空当前音频/基础视频/成片指针并回到 `DRAFT`；图片只清空基础视频和成片指针并保留当前
音频；BGM 或字幕设置只清空当前成片并保留基础视频。历史资产、操作和外部链接不删除。
声音总按钮在存在待生成行时只处理待生成行；全部行均已有音频时再次点击会为全部行创建
新的声音批次和音频素材版本。同一秒创建的多批外部链接按数据库插入顺序选择最新版本。

核心工作台只能选择数字人账号中已经保存的音色。项目默认音色由后端统一写入全部脚本
行，前端逐行下拉框只负责展示和提交单行覆盖。声音中心的克隆/融合是两阶段流程：先生成
可试听结果，用户试听确认后再保存。保存后的自定义音色仍是 `READY`，必须由用户二次
确认激活，后端执行第一次正式 TTS 并切换到 `ACTIVE` 后才能进入核心工作台。删除音色卡
只从可用音色库移除，不破坏历史任务和历史音频；当前项目仍引用时拒绝删除。

生成语速保存在 `project_user_preferences.voice_settings_json.speed`，范围为 `0.5–2.0`，
默认 `1.0`，前端滑杆步长为 `0.01`。核心工作台默认声音区负责读写该偏好；批量、选中、单行新生成和单行重新生成
都必须提交同一份 `voice_settings`。调整语速不使已有素材失效，只有明确发起下一次付费
MiniMax 生成时才生效；切换默认音色不重置语速。

## 9. 自动化测试

### H3 独立片段建轨（2026-08-31，本地源码）

- `h3_video_segments.py` 将可替换的分段缓存冻结到 `f/f-<24字符>/segment.mp4`，完整
  SHA-256 写入同目录 `identity.json` 并按文件内容复核，再登记
  `original_video_segment/source_type=h3`。重生成更换引用，不改历史文件。
- 基础视频冻结 `jyd.h3-video-sequence.v1`、段数、段 ID 和有序素材 ID。建轨逐项复核
  当前批次、行、签名、顺序、文件和总时长；缺段不得回退为合并视频。
- `outputs.original_video_segments` 对 H3 只返回当前绑定集合，全部版本留在
  `asset_history.original_video_segment`，防止原始素材下载混入历史段。
- 4B/变体按 H3 实际视频时长逐段建轨，原片全部静音，继续铺一次清理后的 H3 权威音轨。
  不按 MiniMax 输入时长裁尾，不改变现有 0.5 秒保时长视觉转场配置。
- 已清理声音的旧结果通过状态同步补清单并创建基础视频元数据新版本；音频文件和已有
  ASR 绑定不变，不重跑识别或付费生成。重新生成后期草稿才会看到分段，既有草稿不覆盖；
  进行中的后期/变体和手工上传的成片不会被该升级替换。
- 模板通过 `main_video_sequence` / `video_sequence_apply.py` 替换主视频槽，或在无主视频
  模板中新增底层轨道；只处理输出副本，其他字幕、贴纸和模板内容沿用原规则。
- 长路径兼容：`content_replace.py` 在所有 JSON 级素材写入后统一调用
  `draft_media_paths.localize_long_media_paths`，将超过 240 个 UTF-16 单位的本地视频/图片与
  音频复制到输出草稿 `jyd_media/m-<24字符>.<扩展名>`，完整 SHA-256 仍按源文件与副本
  内容计算校验。副本校验后原子发布，仅改素材
  `path`；同名和重生成版本按内容隔离，原片和已有草稿不变。目录过长、缺失/空素材、复制或
  校验失败必须中止建草稿。不能只用 Python/FFmpeg 可读性判断剪映是否支持该路径。
- 专项测试为 `tests/test_h3_video_sequence.py`，覆盖乱序、旧结果恢复、历史隔离、缺段、
  模板参数、真实独立片段草稿和唯一权威音轨，并覆盖普通/模板/无占位模板的长路径输入；
  `tests/test_draft_media_paths.py` 覆盖副本校验、幂等、内容隔离、嵌套草稿和失败保护。
  未调用付费服务或部署生产。


运行全部不依赖真实剪映导出的测试：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest -q
```

运行单个测试文件：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest -q .\tests\test_visual_variant.py
```

建议按修改范围选择测试：

- Render Job 或草稿结构：`test_mother_draft_rendering.py`、`test_draft_*`。
- 批量组合：`test_batch_dimensions.py`、`test_web_batch_naming.py`。
- 画面、贴纸、封面：`test_visual_variant.py`、`test_sticker_library.py`、`test_cover_apply.py`。
- 素材管理：`test_asset_admin.py`、`test_personal_asset_management.py`。
- 多处理机：`test_multi_processor_api.py`。
- 前端批量流程：`test_batch_editor_frontend.py`、`test_batch_result_center.py`。

自动化测试不能代替真实剪映回归。涉及 UI 导出、剪映版本兼容、缓存资源或字体渲染的修改，最终必须在目标剪映版本上完成一次真实 MP4 闭环。

## 10. Windows 打包与发布

### 10.1 初始化构建环境

```powershell
.\scripts\setup_build_environment.ps1 `
  -Python "D:\Myanaconda\python.exe"
```

构建缓存位于项目同级 `.jyd-build-cache`，不属于源码。

### 10.2 常用构建命令

```powershell
# 本机完整工作台、采集器和 Agent
.\build_release.ps1

# 当前单机交付所需包
.\build_deployment.ps1

# 只构建公用处理机
.\build_shared_processor.ps1

# 完整可迁移源码包，可选同时重建发布包
.\build_portable_project.ps1 -BuildReleases
```

底层单独构建 Processor：

```powershell
.\scripts\build\build_processor.ps1 -CompressionLevel Fastest
.\scripts\build\build_processor.ps1 -DeploymentMode shared -CompressionLevel Fastest
.\scripts\build\build_processor.ps1 -UpdateOnly -CompressionLevel Fastest
```

`UpdateOnly` 是纯程序更新包，只携带重新构建的 Processor、内嵌前端、工具和更新说明；
构建脚本会清除复用 dist 中残留的 `data` 并在压缩前做硬断言。它不会携带或删除目标机的
语义素材、音乐、字体、模板、账户、任务、配置、数据库、个人素材库或 ASR 运行时。
公共素材首次交付使用完整包；素材增量应使用独立、可审核的素材包。

完整 Processor 构建会复制 `data/libraries` 中受支持的公共素材和 `data/template_library`。运行实例后来采集的 `data/personal_libraries` 默认属于实例数据，交付前如需预装，必须显式复制并验证 manifest 和 bundle 都存在。

### 10.3 发布前检查

1. 运行相关自动化测试。
2. 启动全新的测试数据目录，确认页面和 API 能打开。
3. 检查 ZIP 根目录包含 EXE、`_internal`、`tools`、说明文件和预期的 `data`。
4. 检查 `jy-draftc.exe` 已进入 `tools`。
5. 检查公共素材、个人素材和母版是否符合本次发布范围。
6. 在非开发电脑上解压运行，验证不依赖开发机 Python。
7. 最后执行一次真实草稿生成和 MP4 导出。

## 11. 常见扩展方法

### 11.1 新增一种素材类型

1. 定义素材目录和 manifest/bundle 格式。
2. 编写或扩展 `tools/library` 下的采集工具。
3. 在 Web API 的素材列表、引用校验和个人素材导入中注册类型。
4. 在 `asset_admin.py` 注册管理类型，确保启停、软删除和恢复一致。
5. 在 Render Job 中实现应用逻辑。
6. 增加前端选择和批量维度构造。
7. 更新打包脚本的素材复制列表。
8. 增加提取、API、应用和打包覆盖测试。

遗漏第 4 或第 7 步通常会导致“网页可以采集，但管理接口报不支持”或“开发机可用，安装包缺素材”。

### 11.2 新增一个可排列组合元素

组合维度由 `web_api.py` 的批量展开逻辑处理。候选项应包含稳定 `id`、简短 `label`，以及用于覆盖任务的 `patch` 或追加数组的 `append`。

修改时需要保证：

- 在生成草稿前完成筛选，不能先生成大量无用草稿再删除。
- 同一批内组合不重复。
- 任务数不超过服务端上限。
- 固定、参与组合、不使用三种模式语义一致。
- 组合名称简短但任务 ID 保持唯一。
- 批量失败不阻断已成功结果的预览和下载。

### 11.3 新增一个画面处理步骤

先决定处理对象是视频素材、轨道片段还是整个画布，再确定与镜像、裁剪、贴纸、字幕和封面的执行顺序。时间轴切段会影响后续片段索引，优先让一个模块统一完成切段并返回稳定结果。

## 12. 调试与故障定位

### 后端返回 500

先看启动 Processor 的控制台 traceback，再根据请求路径定位 `web_api.py` 对应路由。不要只根据前端的 `Internal Server Error` 修改 UI。

### 网页显示旧版本

确认启动的是源码目录还是旧发布包；使用 `Ctrl+F5`，并在 Network 中检查脚本响应。发布包必须重新构建，修改源码不会自动改变已解压的 EXE。

### 本地采集器已连接但处理机离线

Collector 和 Render Agent 是两个不同角色。Collector 在线只表示网页可以读取本机文件；是否能执行任务取决于 Processor 使用 `embedded`，或 `agent` 模式下是否有 Agent 注册并持续心跳。

### 开发环境有素材，发布包没有

依次检查：

1. 素材位于 `data/libraries` 还是运行实例的 `data/personal_libraries`。
2. 构建是否使用了 `UpdateOnly`。
3. manifest 和 bundles 是否一起复制。
4. 页面当前连接的是本机工作台还是另一台公用处理机。

### 剪映导出失败

确认剪映已安装、桌面未锁屏、没有遮挡导出对话框、草稿目录正确、素材路径有效。自动化找到
草稿但单击后没有进入编辑页时，会重新创建控制器、聚焦剪映并重试点击；最终错误明确报告
“点击草稿后未进入编辑页”，不再误报为普通的“找不到导出按钮”。保留失败任务的 job JSON、
草稿副本、Processor 日志和剪映版本号，这四项是定位兼容问题的最低信息集合。

## 13. 开发约定

- 先读现有模块和测试，再扩展已有模式，避免重新创建平行实现。
- 草稿 JSON 使用结构化读写，不使用大段字符串替换。
- 公共路径通过 `runtime_paths.py` 和环境变量解析，不在核心模块硬编码开发机盘符。
- 临时文件必须进入受管理目录，并明确到期清理规则。
- 永久素材和一次性视频必须分开存储。
- 修改 API、任务 schema、素材格式或部署步骤时同步更新文档和测试。
- 不覆盖用户已有的 `data`，程序更新优先使用 UpdateOnly 包。
- 涉及用户本地文件的接口只在明确允许本地访问的单机模式启用。

## 14. 专题文档索引

| 主题 | 文档 |
| --- | --- |
| 项目目录 | `docs/PROJECT_LAYOUT.md` |
| 当前状态 | `docs/PROJECT_STATUS.md` |
| Web API | `docs/WEB_API.md` |
| Render Job | `docs/RENDER_JOB_SCHEMA.md` |
| 本地采集器 | `docs/LOCAL_COLLECTOR.md` |
| 多处理机 | `docs/MULTI_PROCESSOR.md` |
| 处理机部署 | `docs/PROCESSOR_DEPLOYMENT.md` |
| 公用机快速部署 | `docs/SHARED_PROCESSOR_QUICK_START.md` |
| 程序更新 | `docs/PROCESSOR_UPDATE.md` |
| 快速打包 | `docs/FAST_BUILD.md` |
| 母版导入分析 | `docs/DRAFT_IMPORT_ANALYZER.md` |
| 音乐库 | `docs/AUDIO_LIBRARY.md` |
| 特效库 | `docs/EFFECT_LIBRARY.md` |
| 字体库 | `docs/FONT_LIBRARY.md` |
| 贴纸库 | `docs/STICKER_LIBRARY.md` |
| 花字库 | `docs/FLOWER_TEXT_LIBRARY.md` |
| 复合文字模板 | `docs/TEXT_TEMPLATE_LIBRARY.md` |
| 语音标点停顿配方（跨项目、待开发） | `D:\工作内容\轻盈健\数字人\语音标点停顿配方开发文档.md` |

遇到文档与代码不一致时，以当前测试、FastAPI `/docs` 和实际入口代码为准，并在修复代码的同一个改动中更新文档。

## 15. 新版工作台 2026-08-05 细节修正

- 4A 通过数字人工作台接口启动时使用 `exact_timestamps` 内部模式。云端把口播分段限制为
  32.8 秒，并仅在 RunningHub 临时上传音频中为每段追加 2 秒静音；工作台同步的已审核音频、
  raw cues 和字幕时间轴不变。原始分段元数据携带 `speech_duration_seconds` 与
  `generation_tail_seconds`：剪映主轨裁掉中间段生成尾，只在最后一段保留生成尾供 2 秒渐隐。
- `/api/new/postprocess/options` 返回 `default_font_identity`；当前默认是
  `resource_id:7244518590332801592`（`DouyinSansBold`）。前端新配置以此初始化，历史行的
  `settings.postprocess.font_identity` 优先级更高。
- 成果库首页只渲染批次缩略卡，批次弹层才渲染全部视频卡；选择状态使用真实变体
  `asset_id`，支持当前查询结果的总全选、单批次全选、ZIP 下载和删除选中。删除接口先对
  整批 ID 做账号归属校验，再原子删除数据库记录和对应受管导出文件。
- 核心工作台脚本列采用固定表格布局和 `overflow-wrap:anywhere`，编辑区最大高度内纵向
  滚动，避免长文本改变其他列宽度。
- 核心工作台左侧输入区可通过表格标题栏按钮收起；状态保存在本机
  `localStorage`，收起时右侧表格跨满工作区。表头类 `table-header-input` 使用低饱和深色
  底配靛蓝标线和圆点表示输入/操作列，`table-header-output` 使用深青色底配青绿标线和
  圆点表示三个预览输出列；标题栏显示对应图例，只改变表头，不改变正文单元格状态配色。

## 16. 语义视觉图片与视频（2026-08-10）

- `semantic_visuals.py` 负责受控目录校验、内容哈希版本、最长别名召回、复合词排除、稳定字符
  候选、FunASR 优先/MiniMax 回退时间映射、素材选择和密度规则；本地路径从不发送到云端。
- `project_content_analysis.py` 通过既有 `/api/workbench/content-analysis` 一次取得音乐、字幕
  和 selected-only `visual_plan`；`unified_visual_plan.py` 只把合法 anchor 映射回本地候选。
  项目 Web 主流程不再调用 `/api/workbench/visual-analysis`，旧客户端方法和独立协调器仅用于
  兼容测试及迁移期读取。
- 每行 `visual_analysis` 保存原始三字段计划、兼容决策、映射状态和最终 `recipe`。用户保存后条目标记
  `selection_mode=manual`；重新分析只能保留并尊重锁定人工项。
- MiniMax raw cues 尚未产生时允许先保存语义计划并将 mapping 标为失败；时间轴到达或变化后，
  `project_audio.py` 只重新执行本地字符时间映射和冻结配方，不再次调用 Ark。连续空格或换行
  被 MiniMax 省略时，每个原文字符仍保留；同一空白间隙内的后续字符压为零时长锚点，保证
  时间单调。服务启动后及运行中每分钟检查一次内容/视觉分析状态，`PENDING` 超过 15 分钟
  标记为中断并恢复显式重试权限。
- 启动时使用当前 catalog 扫描已有成功视觉计划。旧 anchor/concept 仍属于新候选集合时，
  `unified_visual_plan.py` 直接用新 catalog 重选素材、重绑 raw cues 并冻结配方；不兼容时清空
  自动计划并标记 `VISUAL_CATALOG_CHANGED`，等待用户显式重试。两条路径都不得请求 Ark。
- 浏览器播放预览和 `project_postprocess.py` / `project_variants.py` 的 4B 冻结任务读取同一
  `mixed` 配方。`image_apply.py` 写入真实 photo 轨道，`video_overlay_apply.py` 写入原生 video
  material/segment，支持源片截取、静音、cover/contain；单项失败按 optional 跳过。语义视频
  始终只播放一次，源片不足目标区间时按剩余可用时长提前结束。
- 自动贴图先把命中关键词扩展到它所在的标点分句（逗号、句号、问号、感叹号、分号、冒号
  或换行），再优先使用当前音频绑定的 FunASR 字词时间取得该分句的真实开始和结束；未完成
  ASR 时使用 MiniMax raw cue 字符插值回退。最终单行 `render_cues` 生成后，自动明确语义贴图
  的开始时间再吸附到包含关键词的最终字幕起点，结束时间仍不早于原句段结尾。手工锁定项、
  泛氛围 `seam_broll` 和列举速切不参与吸附；成片尾部仍会裁切超出的显示区间。
  同句至少两个入选语义且相邻项目由顿号连接时，整个句段按关键词语音中心点顺序速切，单项
  不做 2 秒保底。相邻分句只要求时间不重叠；每 60 秒全部自动视觉最多 24 条，同 concept 按
  `semantic_overlay/full_screen_broll` 展示角色分别保留 20 秒密度冷却，同一 `asset_id` 仍为
  整条成片最多自动使用一次。边缘重叠不超过 0.5 秒时裁短或顺延新项，超过后仍整项跳过。后处理得到精确
  ASR 后会只在本地重绑
  未锁定自动配方，不再次调用 Ark。未人工锁定的自动项在预览和渲染时
  刷新素材库当前默认资源、位置、缩放和透明度，人工/锁定项保持冻结值。
- `semantic_visual_library/fixed/nameplate_standing` 和 `nameplate_seated` 是每条视频自动携带的
  两套固定人名板。渲染任务通过 `fixed_overlays` 写入剪映原生贴纸轨道并覆盖完整正文时长；
  站姿/坐姿的原始贴纸缩放、旋转、位置及三层文字参数由 `layout_profiles.py` 分别冻结，避免
  透明方形 PNG 按照片缩放造成底板与文字错位。
- 项目独立 MiniMax 语音统一带 `fit_to_video=true`；渲染入口按源草稿主视频时长同时裁切语音
  和 `duration_us=0` 的固定贴层，不能再以音频文件的原生编码时长反向延长成片。
  字幕仍为最高层。`layer_order` 统一保证
  `下方图片/小窗视频 < 固定人名牌 < 全屏 B-roll < 字幕`；全屏 B-roll 自然覆盖人名牌，不生成
  隐藏和恢复状态。浏览器使用同一层级和鉴权视频内容接口。
- 新版表格把“语义视觉”保持在 BGM、字幕的配置区域，并将“单条生成”移到最右侧；审核
  弹窗的“移除本行”只修改当前行配方，不删除素材库文件。全局图库新增、停用和物理删除
  保护规则见 `docs/SEMANTIC_VISUAL_LIBRARY.md`。
- catalog v3 严格按用途选材：普通句只接受 `semantic_overlay/action_demo/knowledge_card`，
  顿号速切只接受 `list_quick_cut`，通用空镜只接受 `full_screen_broll`；拼接点只接受明确带
  `seam_broll` 用途的连接处素材，不得把仅有 `full_screen_broll/enrichment` 的普通空镜并入候选。
  同一素材同时带 `seam_broll` 和其他用途时仍可用于拼接点。v2 继续兼容
  `空镜/相关素材/b-roll/enrichment` tags。v3 的
  `semantic_roles.related` 是非自动关系，不能作为空镜开关。锚点输入显式携带
  `usage=enrichment/seam_broll` 和所在短语上下文；自动空镜必须是脚本直接召回的同一具体对象、
  动作或明确场景并返回 priority 2。priority 1、编辑型氛围及分类宽回退只供审核。通用空镜由
  `VISUAL_BROLL_TARGET_INTERVAL_SECONDS=10` 控制约每 10 秒一次的目标尝试；
  本地在目标点附近只提交确有获准素材支撑的相关短句，普通空镜之间仍至少留 6 秒空窗；接缝
  空镜不重置这个间隔。该值是
  尝试间隔而非配额，匹配不到即保留数字人口播。普通全屏空镜先于显式小窗占位；本地按精确
  动作、对象或明确场景的直接概念选材，不再自动进入编辑型空镜池或宽分类回退。
  首轮显式语义和通用空镜仍在统一内容分析的一次模型调用内完成；数字人真实分段尚未生成，
  因此接缝候选不能在首轮可靠产生。
- `project_video_source.py` 从当前 `source_task_ids` 绑定的最新原始数字人分段读取下一段脚本，并用
  与剪映建草稿相同的媒体探测器读取每个实际 MP4 时长，按使用顺序累计真实边界；下载新分段时
  同时冻结 `actual_duration_us`，历史分段在使用时现场探测。`POST .../postprocess/generate` 在 4B
  冻结配方前自动调用一次轻量视觉接口，只提交新增的
  `seam_broll` 候选，不重跑音乐、标题、字幕或普通空镜，也不覆盖首轮视觉方案。候选集合摘要
  成功落盘后重复 4B 不再请求；旧多段项目重刷 4B 会自动补齐。候选上下文固定为上一段末句加
  下一段首句，不得向下一段后续句子扩张；云端只允许 `direct_concept_ids` 中同一具体对象、动作
  或明确场景的强匹配。本地同时拒绝编辑型原因码、低于 0.90 的置信度和非直接概念；没有通过时
  不再生成任何本地氛围兜底。4B 在 ASR/raw cues
  已就绪后的本地重映射阶段把边界传给统一配方。接缝有对应未用视频时生成覆盖真实边界前后各
  0.5 秒的 `seam_broll`，否则不新增 overlay；底层 `video_sequence` 和 250ms 溶解始终
  保留。补分析失败或没有达到语义门槛时继续 4B 并保留原溶解。配方先登记手工项，再按接缝、
  通用全屏空镜、显式语义的顺序占位和更新
  `used_asset_ids`。普通语义画面和普通空镜均直接使用对应说话短句的真实时间，不再补足到 2 秒；
  与接缝碰撞时也只能在原句段的前后剩余区间内裁短，不能移到无关台词。原句段没有空间才跳过。
  视频源短于冻结目标区间时，浏览器预览和渲染器都会让该 overlay 提前结束，
  不循环也不定格补足；该规则同时覆盖自动、人工锁定和历史冻结配方，旧
  `loop_to_target=true` 在 API 保存、配方消费及渲染任务三层都会被强制关闭。
- 工作台加载器同时支持严格 catalog v2 和完整 catalog v3。v3 强制
  `concept_ids == auto_trigger_concept_ids`，自动关系只能来自互斥的 depicts/expresses，且每项
  必须给出 `trigger_basis`；`auto_eligible=false` 的概念不会进入模型候选或本地选材。未知或
  受限授权的素材不得自动全屏。迁移使用 `semantic_visual_migration.py` 校验源库、备份和候选
  SHA-256，并提供哈希保护的原子 apply/rollback；manifest 默认 `approval.status=pending`，只有
  人工填写批准人、批准时间并改为 `approved` 后才能 apply。
- 默认库现有 191 张图片和 19 条视频。首批人工审片素材按图片像素指纹和视频 SHA-256 去重；
  原有胯下击掌与 42.766341 秒腹部核心源片只合并概念/标签，没有重复复制。腹部核心源片仍
  通过 `source_start_us=12000000` 截取 5 秒全屏 B-roll，且未导入 `爆款动作.mp4`。
- 完整候选池逐条审核并完成视频分层后的本地 catalog 现为 1378 个资产、921 个概念；新增审核
  资产包含 432 条视频和 737 张图片。451 条视频保存 `video_taxonomy`，927 张图片不含该字段。
- 以 `SEMANTIC_VISUAL_LIBRARY.md` 为权威合同：视频标签分 L1 领域、L2 类别、L3 精确，
  并另存动作、场景事实。图片只能 L3 精确触发；L1 永不自动触发；视频先走 L3，缺少精确
  视频时，普通空镜和接缝空镜才可使用人工批准的 L2、动作或场景回退。
- L2 回退必须由显式白名单关系声明，禁止根据 concept ID 前缀或任意父概念自动扩散；
  `nutrition.protein` 之类抽象营养概念不得回退成鱼、肉、鸡蛋等具体素材。没有合格视频时
  保留数字人口播或原接缝。食物、菜品、饮品的 L2 仅用于视频归档，不做同类自动替换。本地
  catalog、选择器与回归已更新，生产环境尚未部署。
- 人工验收后的口播小窗统一使用 `bottom_center`：语义图片默认宽度 56%，动作视频默认宽度
  61.5%，水平中心为画面中轴。高素材最多显示下方约 37% 并允许底边裁出；全屏 B-roll 规则不变。
- 本机需要自动操作剪映界面时，固定使用桌面“剪映专业版6.01破”对应的 6.0.1 独立程序，
  不使用普通“剪映专业版”入口指向的 8.9 版本；用户正在操作电脑时不得抢占界面。

## 17. 语音标点停顿配方（方案已确认，尚未实施）

- 权威方案位于 `D:\工作内容\轻盈健\数字人\语音标点停顿配方开发文档.md`。它是独立的
  本地确定性语音配方，不复用内容分析或语义配图的大模型结果。
- 工作台负责解析人工控制语法、保存原始脚本和紧凑覆盖、显示生成前预检；数字人服务端
  负责按同一规则版本复核并编译 MiniMax 专用标记。
- 普通空格不代表停顿；真实换行参与规则，页面自动折行不参与。字幕、字数、内容分析和
  语义配图始终读取不含控制标记的原始脚本。
- 当前 `project_audio.py` 仍提交原始 `script_text`。在项目 schema、API 契约、幂等摘要和
  跨项目测试完成前，不得把本节写成已经上线的能力。
