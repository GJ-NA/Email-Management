# Email Management

一个本地运行的多邮箱管理工具，面向自己持有或获得授权的邮箱账号。项目提供 Web 控制台、Windows 桌面版和 Chrome / Edge 浏览器扩展，用于批量导入、分组、验活、Token 刷新、邮件读取和数据导出。

- 当前版本：`3.0.4`
- GitHub 仓库：[GJ-NA/Email-Management](https://github.com/GJ-NA/Email-Management)
- 数据存储：本地 SQLite；不同部署方式使用不同的数据目录

## 主要功能

- Outlook / Hotmail OAuth 账号管理，支持 Microsoft Graph 和 OAuth-IMAP 收件链路
- Gmail、QQ、163、126、Yahoo、阿里邮箱及自定义 IMAP 账号；163 邮箱额外支持 POP3 和客户端授权码
- 从文本框或 `.txt` 文件批量导入邮箱账号，支持 UTF-8、UTF-16 和 GB18030
- 支持 `邮箱----密码----client_id----refresh_token`，并自动识别 OAuth 字段反序格式
- 批量刷新 Token、保存刷新结果和错误记录；支持按天数或 Cron 定时刷新
- 批量验活：分别检查 OAuth、Graph 收件和可选的 OAuth-IMAP / 普通 IMAP 收件
- Graph、IMAP、邮箱和账号状态分开显示，可按状态筛选
- 多级分组、标签、搜索、分页、批量移动、批量导出和单邮箱查看
- 邮件列表、详情、附件下载、原始邮件查看、已读状态和删除操作；163 POP3 仅支持收件箱，不能读取其他文件夹或标记已读
- Outlook 重新授权、Outlook 上传账号暂存和批量自动授权队列
- Cloudflare、GPTMail、DuckMail 临时邮箱管理
- SMTP、Telegram、企业微信邮件转发，支持账号级和全局转发开关、日志与定时检查
- 邮件分享链接，支持限时有效或永不过期
- 系统皮肤、代理、刷新策略和浏览器扩展
- Windows 托盘桌面版：自动启动本地服务、打开浏览器、托盘菜单退出

所有账号数据默认保存在本机 SQLite 中。项目不会把邮箱密码、Refresh Token、Client ID、数据库、日志或密钥提交到 Git 仓库。

## 目录结构

```text
Email Management/
├─ EmailManagement.exe          # 已构建的 Windows 桌面版
├─ assets/                      # EXE 和托盘使用的透明图标
├─ email_management.py          # Web / 桌面应用入口
├─ email_management_web/        # 运行时、路由分段、验活和托盘模块
├─ mail_reader.py               # 邮件读取辅助模块
├─ static/                      # CSS、JavaScript 和前端资源
├─ templates/                   # Flask 模板
├─ browser-extension/           # Chrome / Edge 扩展
├─ scripts/                     # 密码重置、Windows / macOS 打包脚本
├─ tests/                       # 自动化测试
├─ docs/                        # API、部署、安全、升级和故障排除文档
├─ runtime/                     # 源码启动时的本机数据，已被 Git 忽略
├─ data/                        # Docker 部署时的持久化数据，已被 Git 忽略
├─ .env.example                 # 环境变量模板
├─ VERSION                      # 当前版本号
├─ requirements.txt             # 运行依赖
└─ requirements-dev.txt         # 测试和打包依赖
```

## Windows 使用

### 使用仓库中的 Windows 版本

当前仓库还没有创建正式的 GitHub Release。可以直接下载仓库代码压缩包，解压后在根目录找到已构建的 `EmailManagement.exe` 并双击运行。GitHub 页面中的 `Packages` 软件包与 Windows EXE 是不同的发布渠道，不能替代这个桌面程序。

Windows 版本默认使用：

```text
%APPDATA%\Email Management\
```

其中保存数据库、密钥和启动错误日志。首次启动前建议在 `EmailManagement.exe` 同目录创建 `.env`，至少设置一个强密码：

```dotenv
LOGIN_PASSWORD=replace-with-a-strong-admin-password
SECRET_KEY=replace-with-a-long-random-secret
```

`LOGIN_PASSWORD` 只在数据库尚未初始化登录密码时生效；实例启动并写库后，修改环境变量不会覆盖当前密码。登录后也可以在设置中修改密码。

### 从源码运行

准备 Python 3.11 或更高版本，并在项目根目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\start-email-management.bat
```

也可以直接运行：

```powershell
.\start-local.ps1
```

启动脚本会优先使用根目录 `.venv`，不会自动下载依赖。源码启动默认访问 `http://127.0.0.1:5000`，按 `Ctrl+C` 停止服务。首次启动时，脚本会在 `runtime/` 下生成需要的本地密钥和管理员密码文件。

源码启动的运行文件包括：

```text
runtime/data/outlook_accounts.db
runtime/secret_key.txt
runtime/admin_password.txt
runtime/logs/
```

忘记登录密码时，可在主机上运行：

```powershell
.venv\Scripts\python.exe scripts\reset_login_password.py
```

### 构建 Windows EXE

当前仓库根目录已经包含 `EmailManagement.exe`。需要重新构建时，运行：

```powershell
.\scripts\build-windows-exe.bat
```

或者：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows-exe.ps1 -InstallIfMissing
```

脚本使用 `email_management.spec` 和 `assets/email-management-icon.ico`，输出到项目根目录。源码构建时，如果根目录没有 `.env`，脚本会创建一个不含密钥的本地配置，并让 EXE 使用项目的 `runtime/` 目录；发布包不包含这个配置，因此使用 `%APPDATA%\Email Management`。如需指定其他配置文件，可为打包版设置 `EMAIL_MANAGEMENT_ENV_FILE`。

### macOS 打包

在 macOS 上准备 Python、项目依赖和 PyInstaller 后执行：

```bash
bash scripts/build-macos-dmg.sh
```

脚本会生成 `EmailManagement.app` 和对应的 DMG 文件，具体产物名称见 [RELEASE.md](RELEASE.md)。

## 环境配置

先复制模板：

```powershell
Copy-Item .env.example .env
```

常用配置如下：

```dotenv
HOST=127.0.0.1
PORT=5000
FLASK_ENV=production
LOGIN_PASSWORD=replace-with-a-strong-admin-password
SECRET_KEY=replace-with-a-long-random-secret
EMAIL_MANAGEMENT_HOME=runtime
DATABASE_PATH=runtime/data/outlook_accounts.db
LOG_LEVEL=WARNING
REPOSITORY_OWNER=GJ-NA
REPOSITORY_NAME=Email-Management
```

| 变量 | 作用 |
| --- | --- |
| `HOST` / `PORT` | 服务监听地址和端口 |
| `LOGIN_PASSWORD` | 首次初始化时写入的 Web 登录密码 |
| `SECRET_KEY` | Session 和敏感数据加密密钥，生产环境必须固定 |
| `EMAIL_MANAGEMENT_HOME` | 本机运行数据根目录；相对路径以项目根目录或 EXE 所在目录为基准 |
| `DATABASE_PATH` | SQLite 数据库路径 |
| `EMAIL_MANAGEMENT_ENV_FILE` | 打包版使用的外部 `.env` 文件路径 |
| `LOG_LEVEL` | 日志级别，生产环境可使用 `WARNING` 降低输出 |
| `REFRESH_CONCURRENCY` / `VERIFY_CONCURRENCY` | Token 刷新和批量验活并发数 |
| `REPOSITORY_OWNER` / `REPOSITORY_NAME` | 版本检查和更新链接，默认指向本仓库 |

不要把带有真实密码、Token、Client ID、API Key 或 Webhook 的 `.env` 上传到 GitHub。数据库和 `SECRET_KEY` 必须一起备份，否则无法解密已有敏感数据。

## Docker

### 使用 GHCR 镜像

仓库提供 `docker-compose.yml`，使用 GitHub Container Registry 镜像：

```bash
# 先修改 docker-compose.yml 中的 LOGIN_PASSWORD 和 SECRET_KEY
docker compose up -d
docker compose logs -f
docker compose down
```

Docker 数据持久化到当前目录的 `./data`，容器内数据库路径为 `/app/data/outlook_accounts.db`。这个 Compose 文件包含 Docker Socket 和自动更新配置；只有在你明确需要在线更新功能并信任该部署环境时才建议直接使用。

### 本地构建镜像

```powershell
Copy-Item .env.example .env.local
docker compose -f docker-compose.build.yml up -d --build
```

构建 Compose 使用本地 `Dockerfile`，并通过 `.env.local` 读取配置。对外暴露服务前必须设置强密码、固定 `SECRET_KEY`，并按实际情况配置 OAuth 与临时邮箱服务。

Docker、Compose 和生产部署都应保持单 worker。刷新任务、验活任务和 SSE 进度使用进程内短期状态，增加 worker 可能导致任务状态无法在请求之间共享。详细部署说明见 [docs/deployment.md](docs/deployment.md) 和 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 导入格式

每行一个邮箱账号：

```text
user@outlook.com----x----client_id----refresh_token
user2@hotmail.com----密码----refresh_token----client_id
user@qq.com----邮箱密码
custom@example.com----邮箱密码----imap.example.com----993
user@163.com----客户端授权码----pop3
```

- `x` 表示该账号没有密码，常用于 Outlook OAuth 账号。
- Outlook OAuth 支持 `client_id` / `refresh_token` 两种末列顺序，导入时会自动识别。
- 普通 IMAP 使用邮箱、密码；自定义 IMAP 还可以提供服务器地址和端口。
- 163 两段格式 `邮箱----客户端授权码` 会先按 IMAP 尝试，认证失败时自动使用同一授权码尝试 POP3；也支持显式格式 `邮箱----授权码----pop3`，以及手机或第三方客户端常见的 `邮箱----密码----授权码` 格式。POP3 服务器默认使用 `pop.163.com:995`。
- POP3 授权码和 IMAP 密码一样保存到账号的 `imap_password` 字段，并在本地加密保存。
- 网页导入弹窗支持直接选择 `.txt` 文件，也可以继续手动粘贴文本。

## 验活、刷新与收件

批量验活会按账号类型执行不同检查：

- Outlook OAuth：先检查 Token，再探测 Graph 收件；需要时继续尝试 OAuth-IMAP。
- 普通 IMAP：使用 IMAP 服务器、端口和密码进行轻量收件探测。
- 163 POP3：使用 `pop.163.com:995` 和客户端授权码进行收件探测。
- 界面分别显示 Graph、IMAP 和账号总体状态；某个通道有效不代表其他通道一定有效。

Token 管理支持单个刷新、选中刷新、全部刷新、失败记录和定时刷新。定时策略可以按天数执行，也可以使用 Cron；刷新成功后会保存服务端返回的新 Refresh Token。项目当前没有独立的 Token 剩余寿命通知中心，失效账号主要通过定时刷新结果、验活状态和错误记录发现。

## 数据、备份与安全

不同运行方式的数据位置不同：

| 运行方式 | 默认数据位置 |
| --- | --- |
| 源码启动 / 源码构建 EXE | `runtime/`（由 `EMAIL_MANAGEMENT_HOME=runtime` 控制） |
| 发布版 EXE | `%APPDATA%\Email Management\` |
| Docker / Docker Compose | `./data/`，容器内为 `/app/data/` |

备份时至少保留数据库和密钥文件。不要把 `runtime/`、`data/`、`.env`、日志或导出的账号凭据发送给他人。

本工具只应处理你自己持有或明确获授权的邮箱。不要用于撞库、盗取账号、未授权访问、批量注册或干扰 Microsoft、邮箱服务商及代理服务。详细安全说明见 [docs/security.md](docs/security.md)。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q email_management.py email_management_web mail_reader.py scripts tests
```

检查全部前端 JavaScript：

```powershell
Get-ChildItem static,browser-extension -Recurse -File -Filter *.js |
    ForEach-Object { node --check $_.FullName }
```

当前测试还覆盖 Windows EXE 打包配置、托盘透明图标、运行时路径、前端契约、Graph / IMAP 验活和主要 API 行为。

## 相关文档

- [DEPLOYMENT.md](DEPLOYMENT.md)：本地快速部署和运行数据说明
- [docs/deployment.md](docs/deployment.md)：Windows、Docker、Compose 和生产部署
- [docs/api.md](docs/api.md)：HTTP API 与浏览器扩展接口
- [docs/security.md](docs/security.md)：密码、Session、CSRF 和敏感数据安全
- [docs/troubleshooting.md](docs/troubleshooting.md)：常见错误和密码重置
- [docs/upgrade.md](docs/upgrade.md)：升级与数据迁移
- [RELEASE.md](RELEASE.md)：版本、EXE、DMG、Docker 镜像和 GitHub Actions 发版流程
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)：上游项目和许可证归属

## 来源与改进说明

本项目是基于以下项目的本地整合和改进版本：

1. [assast/outlookEmail](https://github.com/assast/outlookEmail)：主 Web 应用、Graph / IMAP 邮件读取、账号管理、分组、Token 刷新、前端界面和运行框架的基础来源。
2. [fangxiaobaiqaq1/outlook-mail-helper](https://github.com/fangxiaobaiqaq1/outlook-mail-helper)：批量验活、并发任务、收件探测和导入格式处理思路的参考来源；其独立 PHP 应用和数据库没有直接嵌入本仓库。
3. [CN-Root/OutlookPanel](https://github.com/CN-Root/OutlookPanel)：辅助项目上游的 MIT 项目，作为间接来源保留归属说明。

上游项目的许可证和第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本仓库的整合改动不改变上游代码应遵守的许可证义务。

## 安全与免责声明

本工具只应处理你自己持有或明确获授权的邮箱。不要用于撞库、盗取账号、未授权访问、批量注册或干扰 Microsoft、邮箱服务商及代理服务。使用者需要自行遵守当地法律、服务条款和数据保护要求。
