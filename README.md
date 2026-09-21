# Travian 村庄数据自动记录（GitHub Actions + Google Sheets）

定时抓取自己的 Travian 村庄页面，解析出人口/资源/英雄等数据，
写入一个 Google Sheet，方便长期看趋势、画图。

架构：**GitHub Actions（定时执行）→ 抓取并解析 HTML → 写入 Google Sheets（存储+可视化）**

---

## ⚠️ 使用前必读

- 本工具通过 Cookie 模拟你已登录的浏览器去请求页面，属于**自动化访问游戏服务器**。
  多数 Travian 官服的服务条款不允许自动化操作账号（哪怕只读）。
  请自行确认你所在服务器的规则是否允许，且建议：
  - 抓取频率不要太高（比如 30~60 分钟一次足够看趋势了，不需要分钟级）
  - 仅用于查看自己的数据，不做任何自动点击/自动出兵等操作
  - 如果条款明确禁止，请不要使用本工具的"定时自动抓取"部分，
    退回到手动保存 HTML 再解析的方式

---

## 一、准备 Google Sheets

1. 新建一个 Google Sheet，记下网址中的表格 ID：
   ```
   https://docs.google.com/spreadsheets/d/【这一串就是 ID】/edit
   ```

2. 去 [Google Cloud Console](https://console.cloud.google.com/) 建一个项目（或用现成的）

3. 左侧菜单「APIs & Services」→「Library」，搜索 **Google Sheets API**，点启用

4. 「APIs & Services」→「Credentials」→「Create Credentials」→
   「Service account」，随便起个名字创建

5. 创建完成后点进这个服务账号，「Keys」标签 → 「Add Key」→
   「Create new key」→ 选 **JSON** → 下载。
   打开这个 JSON 文件，里面有个 `client_email` 字段，形如：
   ```
   xxx-yyy@your-project.iam.gserviceaccount.com
   ```

6. 回到第 1 步建的 Google Sheet，点右上角「共享」，
   把上面这个 `client_email` 添加为**编辑者**（这步不做的话写入会失败）

---

## 二、准备 Travian 的登录 Cookie

1. 浏览器登录你的 Travian 账号
2. 按 F12 打开开发者工具 → Network（网络）标签
3. 刷新一下页面，随便点一个请求（比如 `dorf2.php`）
4. 在右侧 Headers → Request Headers 里找到 `Cookie:` 那一整行，全部复制
5. 同时记下你的服务器网址，例如 `https://ts11.x1.international.travian.com`

⚠️ 注意：Cookie 是有**有效期**的（通常几天到几周，取决于服务器设置），
过期后脚本会抓到登录页而失败，届时需要重新登录、重新复制 Cookie、
重新更新下面第三步里的 Secret。

---

## 三、在 GitHub 仓库里配置

1. 新建一个 **Private（私有）** 仓库（不要用公开仓库，避免账号信息泄露）
2. 把本项目所有文件（`travian_parser.py`、`sheets_writer.py`、
   `scrape_and_log.py`、`requirements.txt`、`.github/workflows/scrape.yml`）
   上传进去
3. 仓库页面 → Settings → Secrets and variables → Actions →
   New repository secret，依次添加以下 4 个：

   | Secret 名称 | 内容 |
   |---|---|
   | `TRAVIAN_BASE_URL` | 你的服务器网址，如 `https://ts11.x1.international.travian.com` |
   | `TRAVIAN_COOKIE` | 上面复制的整串 Cookie |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | 下载的服务账号 JSON 文件的**全部内容**（直接打开粘贴进去）|
   | `GOOGLE_SHEET_ID` | 第一步记下的表格 ID |

4. 仓库页面 → Actions 标签，应该能看到 "Travian 村庄数据定时抓取" 这个 workflow。
   点进去，右侧「Run workflow」可以手动先跑一次测试
5. 跑完看 Google Sheet 里是否多了一行数据；也可以点开 Actions 的运行日志看输出

---

## 四、本地测试（强烈建议先在本地跑通再上传 GitHub）

```bash
pip install -r requirements.txt

# 方式 A：用手动保存的 HTML 测试解析逻辑，不涉及网络/凭据
python scrape_and_log.py --html sample_dorf2.html --dry-run

# 方式 B：真实抓取，但先只打印不写入 Sheets
export TRAVIAN_BASE_URL="https://xxx.travian.com"
export TRAVIAN_COOKIE="粘贴你的cookie"
python scrape_and_log.py --dry-run

# 方式 C：连 Sheets 一起测试（需要先配好 Google 那部分）
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
export GOOGLE_SHEET_ID="你的表格ID"
python scrape_and_log.py
```

---

## 五、调整抓取频率

编辑 `.github/workflows/scrape.yml` 里的 cron 表达式（这是 UTC 时间）：

```yaml
- cron: "5 * * * *"     # 每小时第5分钟跑一次
- cron: "*/30 * * * *"  # 每30分钟一次
- cron: "0 */2 * * *"   # 每2小时一次
```

GitHub Actions 的定时任务在负载高时可能有几分钟延迟，属于正常现象。

---

## 六、后续可以加的功能

- 在 Google Sheets 里用「插入 → 图表」直接对存量/产量列画折线图
- 加一个「资源即将溢出提醒」的逻辑，超过阈值时用 GitHub Actions
  发个人 Slack/Discord/Telegram 通知（不涉及操作账号，纯提醒，风险低）
- 多村庄支持：目前脚本假设 `dorf2.php` 只显示当前选中村庄，
  如果你有多个村庄，需要针对每个村庄 ID 分别构造 URL 再各抓一次
