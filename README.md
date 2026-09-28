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
  发个人邮件/Slack/Discord 通知（不涉及操作账号，纯提醒，风险低）
- 多村庄支持：目前脚本假设 `dorf2.php` 只显示当前选中村庄，
  如果你有多个村庄，需要针对每个村庄 ID 分别构造 URL 再各抓一次

---

## 七、自動升級資源田（新增）

新增了 `auto_build.py`，會在每次排程時：讀取 dorf1 → 用純規則決定該升哪塊田
→ 抓 `build.php?id=N` 找出綠色「擴建」按鈕的網址 → 送出 → 檢查資源/佇列是否真的變化
→ 記到 Sheet 的 `Actions` 分頁。不使用瀏覽器，純 HTTP 請求，跟現有的 `scrape_and_log.py`
共用同一份 Cookie。

### Secrets
沿用原本四個即可，不需要新的。


### 在 Sheet 裡加一張「Config」分頁（選填，沒有就用預設值）

| A | B |
|---|---|
| enabled | TRUE |
| target_level | 2 |
| queue_slots | 2 |
| max_builds | 2 |
| target_building_level | 0 |

- `enabled` 改成 `FALSE` 是緊急停止開關，不用改 workflow 或 Secret。
- `queue_slots`：Plus 有效時是 2，到期後（`sample_dorf2.html` 顯示的到期時間附近）記得改成 1。
- `target_building_level`：倉庫/糧倉自動升級到的目標等級。`debug_village_buildings.py`
  已驗證這兩者的 build.php 頁面解析方式（跟資源田不同，見程式內註解），但**預設是 0（停用）**，
  因為目前只驗證過解析邏輯、還沒有實際跑過升級。想啟用的話改成 >0 的數字即可；
  資源田跟倉庫/糧倉會放在同一個候選池裡，一律挑「最便宜、最快」的先升，沒有另外排優先序，
  如果想要「資源田優先、倉庫吃剩下的」之類的邏輯，需要再另外調整 `travian_agent.plan()`。
- 跑完後 Sheet 會多一張「Actions」分頁，記錄每次嘗試升級的結果。

### ⚠️ 自動點擊的風險比純讀取更高

`README.md` 最上面「使用前必读」那段對唯讀抓取的警告，在這裡加倍適用——這已經是
自動操作帳號，不只是讀取。務必：

1. **先用 `DRY_RUN=1` 跑幾輪**（`.github/workflows/auto_build.yml` 裡已經預設是 `1`），
   在 Actions 的執行紀錄和 Sheet 的 Actions 分頁裡確認每次的決定合理，
   沒有升到不該升的田、沒有誤判來襲。
2. 確認沒問題後，把 workflow 裡的 `DRY_RUN: "1"` 改成 `"0"`，才會真的送出升級請求。
3. 前期建議用小號測試，不要直接上主力帳號。
4. 目前只有農場等三種資源田的解析和決策經過真實頁面驗證；建築（非資源田）尚未支援。
5. 這支腳本只點擊「擴建」的綠色按鈕，不會用金幣購買加速（紫色按鈕），
   避免非預期消耗金幣。

---

## 八、建城順序（build_order）

在 Sheet 的 `Config` 分頁加一列 `build_order`，程式就會照這個順序建城：
每次都挑「順序裡第一個還沒達成的目標」來做，前面的目標還沒做完（例如在等資源或施工），
後面的就不動。**沒有這一列（或留空）就跟原本完全一樣**（資源田 `target_level` + 倉庫/糧倉 `target_building_level`）。

| A | B |
|---|---|
| build_order | res:2,10:3,11:3,15:5,17:1 |

格式：用逗號、空白或換行分隔，每項是 `目標:等級`。

- `res:N`：所有資源田都升到 N 級。
- `1:N`～`4:N`：只有木／磚／鐵／糧其中一種的所有田升到 N 級。
- `gid:N`：該建築升到 N 級；村莊裡還沒有就自動找空地蓋一棟。

已在頁面上看過的 gid：15 村莊大樓、10 倉庫、11 糧倉、16 集結點、17 市場、18 大使館、
20 馬廄、22 研究院、23 山洞、24 城鎮廳、25 行宮、26 皇宮、27 寶物庫、28 交易所、
34 石匠鋪、37 英雄宅、45 供水系統。

**缺前置條件時會自動先補**：例如順序寫了 `25:1`（行宮），但村莊大樓只有 3 級（要 5 級），
程式會先升村莊大樓。被劃掉的條件（例如蓋行宮前不能有皇宮）補不了，
會在 log 印出「建城計畫卡住了」。

### 注意

1. 格式寫錯（例如 `abc`）本輪整個不動作並寫進 log，不會亂猜。
2. 新建築蓋在編號最小的空地（19～38；39 是集結點、40 是城牆，不會動）。**蓋下去不能退**，
   請先用 `DRY_RUN=1` 看 log 裡選的位置和建築對不對，再切成 `0`。
3. 「建築是否施工中」是看 dorf2 的 `underConstruction` class，這點還沒用真實的施工中頁面驗證過。
   萬一認不出來，最壞的情況是多排一次同一棟的下一級，或 log 出現「找不到按鈕」。
4. 嚴格照順序的代價：前面的目標在等資源時，後面就算買得起也不會先做。

### 倉庫/糧倉容量不夠時（只在有設 build_order 時）

目標的成本超過倉庫/糧倉容量時，會自動先處理儲存建築，而不是通知後就卡住：
木/磚/鐵超過 → 先升倉庫（gid 10）；只有穀物超過 → 先升糧倉（gid 11）。
每次升一級，下一輪容量變大後再重新評估。村莊裡還沒有就先蓋一棟；已經 20 級，
或補倉庫本身的成本就超過容量時，會標成「計畫卡住了」。沒設 build_order 時維持舊行為（只寫 log）。

---

## 九、通知現況與檔案分工

### 通知（目前只有 log）

Telegram 通知已整個移除。目前所有提醒都只會印在 GitHub Actions 的執行紀錄（log）裡，
**沒有任何主動通知**，包含：

- **偵測到來襲**：只印一行「偵測到來襲 N 波」。**來襲寄信尚未實作。**
- 建城計畫卡住、沒空地可蓋、成本超過容量（舊流程）、送出後沒看到變化。
- 夜間 UTC 17～23 點（台灣 01:00～07:00）workflow 不會執行，那段時間不會偵測來襲。
- session / Cookie 失效時 run 會失敗，GitHub 會依你帳號的通知設定寄「workflow 失敗」的信，
  這是目前唯一會主動通知到你的情況。

之後想做來襲寄信的方案（尚未實作）：用 SMTP 寄信（標準函式庫 `smtplib`，不需要新套件），
需要 `SMTP_HOST`、`SMTP_USER`、`SMTP_PASS`、`MAIL_TO` 四個 Secret（Gmail 的 `SMTP_PASS`
要用「應用程式密碼」）；波數增加才寄、波數沒變時隔 12 小時再提醒、來襲解除就清掉紀錄；
去重狀態存成 `notify_state.json`，跟 `travian_state.json` 一起放進 actions/cache。
來襲的「抵達時間」目前沒辦法解析：需要遇到來襲時存一份 dorf1（或集結點）頁面當樣本才能寫。

### 檔案分工

| 檔案 | 負責 |
|---|---|
| `travian_agent.py` | 純解析 + 決策（看懂頁面、決定升哪個、建城順序），不含網路和 Sheet |
| `runner.py` | 共用主流程：Config / Actions 分頁、決策、送出升級、驗證、記錄 |
| `auto_build.py` | 純 HTTP 版：只負責用 requests 抓頁面、送出網址 |
| `travian_ci_run.py` | Playwright 版：session（cache / 種子 Cookie）、抓頁面、送出網址 |
| `debug_village_buildings.py` | 唯讀診斷：存下村莊中心頁面供人工檢查 |

**新增了 `runner.py`，更新時請跟其他檔案一起上傳到 repo。**

升級網址只接受 `/dorf1.php` 或 `/dorf2.php?id=…&gid=…&action=build&checksum=…` 這種格式，
多任何參數（例如金幣的 `buildmaster`、看廣告的 `as=`）都不會點，避免不小心花金幣。
