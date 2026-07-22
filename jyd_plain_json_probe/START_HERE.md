# 从这里开始

## 你平时只需要认这几个文件

| 文件 | 用途 |
|---|---|
| `start_processor.ps1` | 启动中央网站/API |
| `start_collector.ps1` | 启动本机草稿读取和上传工具（后台运行即可） |
| `start_agent.ps1` | 启动本机剪映处理机 Agent |
| `start_test_processor.ps1` | 启动隔离测试网站 `http://127.0.0.1:8001/app` |
| `start_test_collector.ps1` | 启动隔离测试采集器 `http://127.0.0.1:8766` |
| `build_release.ps1` | 一次生成中央服务、采集器和 Agent 三个交付包 |
| `build_deployment.ps1` | 快速生成当前部署需要的服务器和采集器两个包 |
| `build_portable_project.ps1` | 把完整项目打成可迁移 ZIP |
| `README.md` | 安装、迁移和常用命令 |

其余文件都已按用途收进目录，不需要在根目录里逐个辨认。

## 本机独立模式（当前默认）

每台员工电脑分别启动处理端和采集器：

```powershell
.\start_processor.ps1 -ProcessingMode standalone
.\start_collector.ps1
```

网页只监听 `127.0.0.1`。视频由采集器弹出 Windows 选择框后直接读取，不上传、不复制；生成结果直接写入用户选择的文件夹。现有 `data/libraries` 是公共素材基线，个人采集结果写入空的 `data/personal_libraries`，页面会合并展示。

需要恢复原来的局域网公用处理机时使用：

```powershell
.\start_processor.ps1 -ProcessingMode shared
```

也可以直接使用专用公用机包：

```text
release\JianyingRenderServer-shared-windows-x64.zip
```

它保持老版本单公用机方式：网页上传任务，公用机控制自己的一个剪映顺序导出；多 Agent 分配和处理机选择留到后续阶段。

公用机 `192.168.11.28:8000` 同时作为临时统一账号中心。普通账号只在它的 `/admin` 管理，员工本机处理端不再各自保存可用账号。已有公用机远程升级优先使用不含 `data` 的更新包，保留原账号和业务数据。

员工本机登录一次后，点击“公用处理机”卡片会使用短时一次性登录接力，不会重复要求密码，也不再显示额外的进入按钮。公用机页面保留同一组切换卡片，点击“本机处理”即可返回员工电脑。

发布包也可在 `data\processor_config.json` 中把 `deployment_mode` 改为 `shared`、`host` 改为 `0.0.0.0`。

## 三个正式交付包

```text
release\JianyingDraftCollector-windows-x64.zip
release\JianyingRenderServer-windows-x64.zip
release\JianyingRenderAgent-windows-x64.zip
```

- 中央电脑运行 `JianyingRenderServer`，提供统一网页、保存母版和素材库并分发任务。
- 需要读取草稿的电脑运行 `JianyingDraftCollector`；它只在后台提供本机能力，不需要再打开独立采集页面。
- 剪映处理机运行 `JianyingRenderAgent`，生成草稿并控制剪映导出 MP4。
- 日常操作只打开中央服务的 `/app` 统一工作台页面。

管理员账号：`admin`  
管理员密码：`admin123`

全新安装第一次启动后，管理员先打开 `http://127.0.0.1:8000/admin`，进入“内测账号管理”新增普通用户。停用、删除或重置密码会立即让该用户原会话失效。内测账号保存在处理端本机 `data\web_storage\users.json`，密码为加盐哈希，不保存明文。

完整项目迁移包为：

```text
release\JianyingAutomationProject-portable.zip
```

日常快速生成服务器和采集器：

```powershell
.\build_deployment.ps1
```

首次使用先运行一次 `scripts\setup_build_environment.ps1`，详细说明见 `docs\FAST_BUILD.md`。

生成最新完整项目迁移包：

```powershell
.\build_portable_project.ps1 -BuildReleases
```

部署细节见 `docs\PROCESSOR_DEPLOYMENT.md`，目录细节见 `docs\PROJECT_LAYOUT.md`。
