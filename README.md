# Email Management

一个本地运行的多邮箱管理工具，面向自己持有或获得授权的邮箱账号。项目提供 Web 界面，用于批量导入、分组、验活、Token 刷新、邮件读取和数据导出。

## 主要功能

- Outlook / Hotmail OAuth 账号管理，支持 Microsoft Graph 和 OAuth-IMAP 收件链路
- Gmail、QQ、163、126、Yahoo、阿里邮箱及自定义 IMAP 账号
- 批量导入 `邮箱----密码----client_id----refresh_token`
- 自动识别 `client_id` 与 `refresh_token` 末两列反向的导入内容
- 批量 Token 刷新、过期提醒、刷新结果和错误记录
- 批量验活：检查 OAuth、Graph 收件和可选的 OAuth-IMAP 收件
- 按 Graph 有效、IMAP 有效、邮箱有效或邮箱失效筛选账号
- 邮箱分组、标签、搜索、分页、批量移动、批量导出和单邮箱查看
- 邮件列表与邮件详情弹窗、附件下载、原始邮件查看
- 可选的临时邮箱、邮件分享、转发、代理和定时刷新功能
- Chrome / Edge 浏览器扩展

所有账号数据默认保存在本机 SQLite 中。项目不会把邮箱密码、Refresh Token、Client ID、数据库、日志或密钥提交到 Git 仓库。

## 目录结构

```text
Email Management/
├─ email_management.py          # Web 应用入口
├─ email_management_web/        # 应用运行时、路由分段和桌面托盘
├─ mail_reader.py               # 邮件读取辅助模块
├─ static/                      # CSS、JavaScript 和前端资源
├─ templates/                   # Flask 模板
├─ browser-extension/           # Chrome / Edge 扩展
├─ docs/                        # 部署、API、安全和故障排除文档
├─ scripts/                     # 密码重置、打包等脚本
├─ tests/                       # 自动化测试
├─ runtime/                     # 本机运行数据，已被 Git 忽略
├─ .env.example                # 环境变量模板
└─ requirements.txt             # Python 依赖清单
```

## Windows 本地运行

当前工作区已经配置了本地 Python 虚拟环境，启动脚本会优先使用根目录的 `.venv`，不会自动下载依赖。

### 推荐：使用桌面版 exe

如果已经拿到发布包，直接双击 `EmailManagement.exe` 即可。它会自动启动本地服务、打开浏览器，并在 Windows 系统托盘中保留“打开界面”和“退出”菜单；数据默认保存到 `%APPDATA%\Email Management`。

如果需要在当前源码目录生成 exe，首次运行下面的构建脚本即可：

```powershell
.\scripts\build-windows-exe.bat
```

构建完成后双击项目根目录的 `EmailManagement.exe`。构建脚本会在根目录保留一个不含密钥的 `.env`，让本地 exe 继续使用当前项目的 `runtime` 数据；以后日常使用不需要再打开 PowerShell 或运行启动脚本。若要让打包版使用自定义端口或其他配置，直接编辑 exe 同目录的 `.env` 文件；也可以设置 `EMAIL_MANAGEMENT_ENV_FILE` 指向配置文件。

```powershell
Copy-Item .env.example .env
.\start-email-management.bat
```

启动后访问 `http://127.0.0.1:5000`。终端窗口保持打开时服务运行，按 `Ctrl+C` 停止服务。

首次启动会在 `runtime/` 下生成本地密钥和管理员密码；密码会打印在终端，也会保存到 `runtime/admin_password.txt`。首次登录后请在设置中修改密码。

如果是另一台机器，需准备 Python 3.11 或更高版本，并按需安装依赖：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.env` 只能保存配置，不能替代 Python 依赖。为了保证仓库跨平台、可审计，虚拟环境不会上传 GitHub；本机现有 `.venv` 可直接复用。

## 环境配置

先复制模板：

```powershell
Copy-Item .env.example .env
```

重点配置：

```dotenv
HOST=127.0.0.1
PORT=5000
FLASK_ENV=production
DATABASE_PATH=runtime/data/outlook_accounts.db
LOGIN_PASSWORD=首次启动管理员密码
SECRET_KEY=随机且长期不变的密钥
REPOSITORY_OWNER=你的GitHub用户名
REPOSITORY_NAME=Email-Management
```

不要把填入真实密码、Token 或 Client ID 的 `.env` 上传到公开仓库。生产环境必须使用固定且随机的 `SECRET_KEY`，并限制服务监听在可信网络中。

## Docker

```powershell
Copy-Item .env.example .env.local
docker compose -f docker-compose.build.yml up -d --build
```

Docker 数据目录为 `./data`，容器内数据库路径应设置为 `/app/data/outlook_accounts.db`。生产部署时请替换默认登录密码和密钥，并按实际 GitHub 仓库填写 `REPOSITORY_OWNER` 与 `REPOSITORY_NAME`。

## 导入格式

每行一个邮箱：

```text
user@outlook.com----x----client_id----refresh_token
user2@hotmail.com----密码----refresh_token----client_id
```

密码字段允许使用 `x` 表示无密码。导入时会自动识别末两列，规范化后按 `client_id`、`refresh_token` 存储。Refresh Token 属于高敏感凭据，只应导入自己有权管理的账号。

## 验活说明

批量验活会按账号配置执行 OAuth Token 检查，并对 Outlook 账号继续探测 Graph 收件；启用 IMAP 探测时，Graph 失败会尝试 OAuth-IMAP。Graph 有效不代表 IMAP 一定有效，IMAP 有效也不代表 Graph 一定有效，界面会分别显示通道状态。

## 数据与备份

本地源码启动时的运行数据位于：

```text
runtime/data/outlook_accounts.db
runtime/secret_key.txt
runtime/admin_password.txt
runtime/logs/
```

数据库和密钥必须一起备份。数据库包含加密后的邮箱凭据，密钥丢失后无法解密已有凭据。不要把 `runtime/`、`data/`、`.env` 或日志发送给他人。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q email_management.py email_management_web scripts tests
```

前端 JavaScript 可用 Node.js 进行语法检查：

```powershell
Get-ChildItem static -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

## 来源与改进说明

本项目是一个本地整合和改进版本，主要来源如下：

1. [assast/outlookEmail](https://github.com/assast/outlookEmail)：主 Web 应用、Graph / IMAP 邮件读取、账号管理、分组、Token 刷新、前端界面和运行框架的基础来源。
2. [fangxiaobaiqaq1/outlook-mail-helper](https://github.com/fangxiaobaiqaq1/outlook-mail-helper)：批量验活、并发任务、收件探测和导入格式处理思路的参考来源；相关能力已适配到本项目现有 SQLite 和 Web 工作流中，不再使用它的独立 PHP 数据库。
3. [CN-Root/OutlookPanel](https://github.com/CN-Root/OutlookPanel)：辅助项目上游的 MIT 项目，作为间接来源保留归属说明。

上游项目的许可证和第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本仓库的整合改动不改变上游代码应遵守的许可证义务。

## 安全与免责声明

本工具只应处理你自己持有或明确获授权的邮箱。不要用于撞库、盗取账号、未授权访问、批量注册或干扰 Microsoft、邮箱服务商及代理服务。使用者需要自行遵守当地法律、服务条款和数据保护要求。
