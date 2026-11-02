# 多村開發檔（精簡版）：目標架構＋契約＋工作包

**本版：v0.36（2026-11-01）｜A2a-1 程式交付（待 Actions 驗收）：`parsers/player.py`、`parsers/village_list.py`、`parsed.py` v0.2（PlayerInfo 定案）、舊服樣本 S1a／S1b 與 golden；ps-02、ps-04 依賴欄加 cm-11；§0／§4.2／§9／§10／§11.2 同步，`arch_manifest` 須重新轉出；契約仍 C-v0.5。v0.35 內容：A2a 拆成 A2a-1（ps-02、ps-04）與 A2a-2（ps-01、ps-03）：§7、§4.2 卡片 WP 欄、§9、§0、§10 同步，`arch_manifest` 須重新轉出；無程式變動，契約仍 C-v0.5。v0.34 內容：主檔同步（無新決定）：§0 的舊檔版本 `travian_pages` 改 v2.38、進度與 §7 A2a 處置（純搬→沿用＋修改）、§9 狀態列、§10 待決新增 D-28、風險新增 A-10；無程式變動，契約仍 C-v0.5。v0.33 內容：修正 v0.31 的 Plus 處理：Plus 沿用舊設計（人工在遊戲內開關，有開就用、沒開就不用，系統不購買），`plus_s` 不再「不搬」；無程式變動，契約仍 C-v0.5。v0.32 內容：A2a 前置決定補充：收到舊服 S10／S11 頁面（空地建築頁兩份、兵營 2 份、研究院 2 份），實跑舊碼後新增：`afford_in_s` 可由庫存與產量驗算、`exchange_disabled` 累計 6／6 吻合、建築名稱可能帶序號前綴、樣本須為原始 HTML 而非瀏覽器 DOM、建築 checksum 疑為每村各一；無程式變動，契約仍 C-v0.5。v0.31 內容：A2a 前置決定：依舊服脫敏樣本（dorf1／dorf2 共四份、空地建築頁一份）與舊 `travian_pages.py` 實跑結果，記錄 ps-01／03／04 的邊界與修改（城牆重複建築位、冒險移動列、建築頁 `exceeds_storage`→`exchange_disabled` 與新增 `afford_in_s`、等級改取數字以去中文字面、`plus_s` 不搬（v0.33 已修正）、ps-04 輸入頁面）；新增樣本 S10／S11；`scrub_sample.py` 升 v0.2；無程式變動，契約仍 C-v0.5（cm-09 仍為草案）。v0.30 內容：D-18 修正：執行期不再檢查「首個 `karte.php?d=` 連結」（該連結只在集結點概覽、dorf1／dorf2 沒有，無部隊時可能不存在），PageFacts 改帶各村座標，新增硬性檢查「各村座標 |x|、|y| ≤ `map_half`」，`d=` 公式只用於 A0b 一次性交叉驗算與 `geo` 測試；S6 樣本要求有部隊與無部隊各一份；無程式變動，契約仍 C-v0.5。v0.29 內容：A1b 完成並回填（本機與 Actions 皆通過）：§4.2 卡片 cm-05／06／07／08／12 依實作更新（依賴：cm-05＝cm-10＋cm-13、cm-06＝cm-11、cm-08＝cm-01／04／06／10／11／12／13；cm-05 取消 `in_quiet_hours`；cm-07 持續時間函式改名；cm-12 加 `speed_rules`）、ap-01 舊源註記安靜時段不保留；§6.4 Config 鍵補齊；§0／§9／§10 回填；定案 D-24～D-27（取消安靜時段、舊鍵遷移、卡片依賴、伺服器＝1 倍速常規服）；契約仍 C-v0.5。v0.28 內容：`tools/make_slice.py` v0.2：切片自動附上 §9 最新 WP 的交接區塊與後續事項，舊 WP 留下的事項只附點名本 WP 的列（§8.4），不需手動刪除；設計與契約不變。v0.27 內容：A1a-3 完成並回填：§0 進度／架構／程式三列、§9 狀態表／交接紀錄／交接區塊與後續事項、§4.1 補 `check_arch`／`check_contracts` 規則名稱與 exit code、§4.2 `check_arch` 列補 exit 2；主檔案無修改，契約仍 C-v0.5；定案種族字串清單（補 spartan、viking）與範例檔以契約名命名（§4.1 規則 6、§4.2、§10）。v0.26 內容：依國際 11 的 dorf1 樣本回填：§6.x 穀物欄位（`l4`＝淨產量、`l5`＝可用穀物）、`queue_slots` 與 Plus 不一致、新增待決 D-23（穀物赤字／可用穀物不足時建築被擋）；契約不變。v0.25 內容：A1a-2 完成並回填：§0 進度、§9 狀態／交接紀錄／交接區塊與後續事項、§10 新增 DEFAULT_TARGET_BUILDING_LEVEL 決策；§4.2 cm-01 卡片補上 C7、C12（依 A1a-2 交接事項）；cm-03 舊源欄的預設去處同步；契約仍 C-v0.5。v0.24 內容：A1a-1 完成並回填：§9 狀態與交接、§10 新增決策 新-1～新-9、§6.4 Config 鍵更正（舊鍵 `hero_guard_mode`／`fill_in_mode`；新增 `guard_exposure`）、§6.7 回填舊 Actions／state 格式（取自 `runner.py` v2.36，只記錄、A4b 才改格式）、cm-04／cm-10／cm-11／ap-14 卡片註記；契約仍 C-v0.5。v0.23 內容：A1a 拆成 A1a-1／2／3（§7）；新增 §8.4 切片機制與 `tools/make_slice.py`（主檔仍是唯一真相來源）；卡片簽名與契約不變。v0.22 內容：讀完 `travian_const.py`／`travian_models.py`／`auto_build.yml`：cm-01、cm-03、cm-06、cm-09、cm-12 的「舊源」欄修正（簽名與依賴不變）；A-8 修正為 `effective_mode` 不讀環境變數；D-22 測試方式定為「手動在分支跑」；§6.7 回填 session 快取檔名；`check_arch` 加「不得 import 根目錄舊模組」。契約不變（C-v0.5）。v0.21 內容：D-22 定案：舊服可當新程式的測試場（僅 dry／唯讀、不 live）；規則 12、D-14、A-7、A-8 同步修訂；設計與契約不變。v0.20 內容：D-1／D-8 提前到 G0 定案、D-3／D-4 等樣本再定；寫入類 stage 執行前再核對 `assert_active`（落在 `village_cycle`，不在 actions）；多村動態跳過規則歸 B3；新增待決 D-22（舊服當測試場）；設計與契約不變。v0.19 內容：D-10 定案（套件放 repo 根目錄、`python -m` 執行）；A-7 改為「Apps Script 觸發器維持開著（GitHub schedule 會漏跑）、新服用新名稱的 Secrets」；記錄 repo 檔案清單、`requirements.txt`、`travian_const.py`、`travian_models.py` 的事實；設計與契約不變。v0.18 內容：v0.17 加上 D-10 的現況事實（你貼的 `auto_build.yml`、`triggerTravian`）與建議、新增風險 A-7／A-8，A0b 設 Secrets 前加關觸發器步驟；設計與契約不變。v0.17 內容：只改進度管理：A0 拆成 A0a（開服前可做）與 A0b（開服後做）、定義「欠債測試」、記錄「先做後面、開服後給設定檔就開始玩」的決定；契約仍 C-v0.5（D-21 待同意才升）｜取代 `multi-village-dev-v0_23.md`｜對應主筆記：`project-notes-v3_00_精簡.md`**
（`architecture-v0_1.md`、`multi-village-plan-v0_4.md` 已被取代，不要再附給 AI）

**一句話**：把舊 Travian bot 搬進新架構（`travian_bot/`，73 個模組），**新伺服器第 0 天、種族固定高盧、新程式直接開局（舊程式不上線）**，先做單村（Phase A→關卡 GA），再多村（B）、市場（C）、運兵（D）。Gemini 現階段只產生 `build_order`，Python 只讀＋驗證，驗證不過＝hold。

**標記**：✓ 已驗證／已讀碼｜△ 依筆記描述（沒讀）｜✗ 未驗證。本檔不放程式碼。

---

## 0. 目前狀態（接續用，先看這裡）

| 項目 | 狀態 |
|---|---|
| 進度 | **A1a-1、A1a-2、A1a-3 已完成（2026-10-28）、A1b 完成（2026-10-30；Actions 328 個測試 OK），見 §9**；**A2a-1 程式已交付（2026-11-01），待 Actions 驗收**，其餘 WP 尚未開始；下一步 **驗收 A2a-1，再做 A2a-2**（前置資料：舊服 S10／S11 頁面已收到、待存檔脫敏，A2a-2 才需要；見 §10 v0.31～v0.36）。**A0b 等新伺服器開服再做**。A0 逐項清單見 **§11.6** |
| 架構 | 73 個模組卡片已定（§4.2）；v0.10 新增的 `dm-12`、`if-12` 已在 v0.11 轉換時用卡片資料檢查過依賴方向（通過）；`arch_manifest`（73 張）已由 §4.2 轉出，`check_arch` 對 A1a-1／2 的 8 個檔案通過（違規 0、警告 0，含 `--strict`）；v0.29 A1b 卡片變動後已重新轉出，對 A1a-1／2／A1b 的 13 個檔案通過（本機與 Actions，見 §9） |
| 程式 | bot 執行路徑無程式變動；新增 `tools/` 檢查工具（`arch_manifest`、`check_arch`、`check_contracts` 皆 v0.1），不在 bot 執行路徑上；舊檔版本：`travian_ci_run` v2.10、`runner` v2.36、`dispatch` v1.8、`oasis_store` v0.3、`hide_observe` v0.4、`sheets_writer` v2.36、`travian_pages` v2.38（依你上傳的檔案；v2.38＝成本只讀 `upgradeBuilding` 區塊，避開研究院頁的各兵種研究成本；四檔 v2.10／v1.8／v0.4／v0.3 已核對相容 ✓） |
| 契約 | C-v0.5（C1～C12；v0.12 只在 C11 加 `locale`），全部 ✗ 草案，待 B1／B6 用真實樣本修正 |
| 最先要你定 | **D-16**（伺服器參數；欄位與取得方式見 §11.6；**v0.29 已定：1 倍速常規服**，其餘待 A0b）；（D-10 已於 v0.19 定案：套件放 repo 根目錄、`python -m` 執行）其次 **D-21**（C11 `wuid`、C4 單位鍵）、D-1（五村角色）、D-8（首都放哪） |
| 開始任何 WP 前 | 不需重跑舊測試（風險 A-6，v0.17 定案）：舊功能全部靠直接跑驗證，舊 `test_*.py` 不可信；golden 以脫敏樣本＋你確認的舊函式輸出為準，各 WP 搬入模組時新寫測試 |
| 開服當天（A0b） | 你只要提供：新服主機、S8（`/js/Variables.js`、`/js/Constants.js`）、S9（登入後 dorf1 原始碼，脫敏）、開服時間、新手保護天數、第 1 村名稱與座標、種族是否確為高盧；AI 產出 Config 初值（`server_*`、`server_locale=zh-TW`、`tribe=gaul`、`schema_version=1`、所有 mode 鍵 `off`）。**Cookie、帳密、Sheet 憑證一律不貼**（只回報「已設好」）。GA 前不跑 bot，手動玩 |

---

## 1. 給接手 AI 的規則（每次新對話先讀）

1. 只做**一個工作包**（§7），不順手改別的 WP 範圍。
2. 不主動寫程式、改 Config、改規則檔；先提方案與影響，使用者明確同意才做。
3. **交付以 §4.2 卡片為準**（檔名、公開函式、依賴）。舊程式能套用就套用，不能就重新規劃（§5.1）；不悄悄改檔名、依賴方向或簽名。舊大檔（`runner.py`、`travian_ci_run.py`）是**唯讀搬遷來源**：不改、不掛鉤、不留 shim、不整檔重印。
4. 改契約欄位＝升契約版本、§10 追加決策、交接區塊註明。
5. 每個 py 檔頭寫：版本、用途、依賴、部署狀態；測試跟著交付；寫入動作有 `off／dry／live`，預設 dry 或 off。
6. 結束輸出「交接區塊」（§8.2），使用者貼回 §9。
7. 證據不足標 ✗，不猜；憑證與 Cookie 不出現在任何輸出。
8. 每個 WP 結束前跑 `tools/check_arch.py`、`tools/check_contracts.py`（A1a 後存在）；涉及 domain 另跑種族煙霧測試。
9. **全新伺服器、第 0 天**：不引用舊伺服器的村、文化點、Config 值、Oases、英雄；只沿用程式現況與本檔設計。伺服器參數來自 `ServerProfile`（C11），不寫死。
10. **種族固定高盧但不得寫死**：種族資料只經 `common/tribe_data`；程式碼不得用種族名稱字串判斷。
11. **格式只有一種**：格式化只用 `common/serialize`，驗證只用 `common/schema`（§6）。
12. **新程式直接開局**：舊程式不在新伺服器上線（連 dry 也不跑）；**（v0.21，D-22）舊服可當新程式的測試場，但只限 dry／唯讀：`DRY_RUN=1`、所有寫入類 mode 為 off 或 dry、Config 的 `server_*` 填舊服值、用新名稱 Secrets；新程式在舊服不得 live（live 只在新服通過 GA 後）**、不寫 shim、不留回退入口、不加舊入口掛鉤；舊檔只用於讀碼與離線 golden 比對；GA 通過前 bot 不 live。若看到舊文字仍寫 shim／回退／掛鉤，以本條為準並回報。
13. **Gemini 邊界**：Gemini／Apps Script 只經 Sheet 與 Python 溝通；現階段只有 `build_order`。Python 對它的輸出一律先過 `domain/plan_validate`；被拒＝**hold**（本輪建城不動作、不寫入遊戲、不套預設順序、不快取舊版）。資源調度、躲兵的 Gemini 介入不在本版範圍，之後沿用「Sheet 讀入→驗證→hold」並另開決策。

---

## 2. 目標、範圍與關卡

**目標**：五個村各自依自己的 `build_order` 升級；資源在村與村之間自動調度；兵力可在村與村之間調動。同一份程式 1 村到 5 村，加村＝加設定；每功能可獨立開關（off／dry／live）；一處壞掉不拖垮其他；每模組小到一次對話做完。

| 項目 | 範圍 |
|---|---|
| 各村建城、庫存守衛、躲兵、綠洲掃描 | ✓ 逐村執行 |
| 市場運資源 | ✓ Phase C（先只讀→dry→live） |
| 運兵 | ✓ Phase D（用途待 D-3） |
| 英雄冒險、道具庫轉資源、產量加成 | 帳號級，先只服務英雄所在村（P2 後做多村策略） |
| 開新村、訓練兵、研發、攻擊他人、NPC 商人 | ✗ 不做（bot 只偵測新村並請你設定） |

**起點**：全新伺服器第 0 天；`tribe=gaul`；1 個村（預設即首都）、文化點 0、無英雄道具；Config／Sheet／Oases／state 全從空白建立；伺服器參數記在 `ServerProfile`（D-16）。五村角色未定（D-1）。

**限制**：GitHub Actions＋Playwright（單一 session、逾時有限）；設定與紀錄放 Google Sheet；Apps Script＋Gemini 在 Sheet 內。

| 關卡 | 條件 | 做什麼 | 不做 |
|---|---|---|---|
| **G0（1 村）** | 只有第 1 村 | A0、D-16、D-8；A1a～A6b 搬進新架構（`village_lock` 隨 A3c／A6b）→ **關卡 GA** | 市場、運兵、多村 |
| **G2（2 村）** | 第 2 村已建好、能手動切村 | SAMP；B1～B6 → **關卡 GB** | 市場 live、運兵 |
| **G3（3 村以上或失衡）** | 有實際需求 | C1～C4 市場 | 運兵 |
| **G4（4～5 村）** | 軍事／防守需求 | D1／D2（D-3 定案後）、E1／E2 | — |

新伺服器開局前幾天升級很慢，GA 前先手動玩，剛好拿來完成 A 系列。第 2 村的樣本（兩村 dorf1、切村）現在抓不到，B1 天然排在 G2。

---

## 3. 多村障礙與估算（✓ 讀碼）

**好消息**：`run_build_cycle` 每次開頭重設 `T.*`（`runner.py` 549–551）→ 逐村依序呼叫，全域變數不互相污染；`dispatch.configure(home=…)` 換家會清空 `OASES`／`BLOCKED`；`parse_active_village` 可當「目前是不是我要的村」檢查（單村 ✓、多村 ✗）；決策／執行分離、IO 注入、dry／live、送出後重讀驗證都沿用。

| # | 障礙 | 影響 |
|---|---|---|
| B1 | 所有請求不帶村 id（`get_html`、`submit`、`hero_focus`、`transfer_io`） | 切村是伺服器端狀態（`newdid` △）；bot 與你共用 session 時手動切村會切走 bot 的村（✗，S2 驗證） |
| B2 | Sheet 無村維度：`state` 整份覆蓋、`Actions` 9 欄、`Sheet1` 24 欄、Config 只有一份 | 五村互相覆蓋 |
| B3 | `Oases` 只存一中心、`save` 先 `ws.clear()`（107 行） | 輪流存取互洗、每輪重掃約 25 次請求×5 |
| B4 | session 失效 `disable()` 關整個帳號 | 村級解析失敗不該關全部 |
| B5 | 逾時 8 分、動作間隨機等 2～8 秒 | 五村估 3.5～6 分鐘，可能逾時（△） |
| B6 | 英雄功能綁單一村 | 只服務英雄所在村（英雄在哪 ✗） |
| B7 | Gemini／Apps Script／規則檔單村設計 | 每村要各自 `build_order` |
| B8 | 來襲數是帳號級或村級 ✗ | 可能得逐村開集結點才知道哪村被打 |
| B9 | 市場、運兵完全沒基礎 | 需先抓樣本 |

**官方指南修正（✓ 引用、✗ 未經 bot 驗證）**：第 2 村多半是未來首都（15／9／7 田穀倉型）→ `is_capital` 逐村設定、第 1 村可能不是首都（D-8）；換首都＝目標村蓋皇宮並設為首都（已有皇宮先拆）；兩村同時發展；離線避免囤資源；NPC 商人不納入 bot；商人載重／速度、市場規則、文化點細節指南沒講（§11.3 補）。

**時間估算（△，要實測）**：單村一輪約 40～70 秒。緩解：逾時改 15～20 分、佇列忙且資源不足時只讀不抓 dorf2、沒來襲的村縮短等待、資源村輪替。Sheets API 每分鐘每使用者 60 次寫入 → 批次寫入（`gsheets.batch_write`）。

---

## 4. 目標架構

### 4.1 分層與依賴規則（`tools/check_arch.py` 自動檢查，違反退回重做）

```
app/      編排：每村流程、帳號級階段、時間預算、入口（用 stage 串接 domain 與 actions）
actions/  改變遊戲狀態的動作       可依賴 infra、parsers、common；不可依賴 domain
domain/   純決策    parsers/ 純解析    infra/ 有 IO（session、gateway、store、notify）   ← 三者互相獨立，只依賴 common
common/   純資料與工具（不做任何 IO）
```

| 層 | 可 import | 不可 import |
|---|---|---|
| common | 只有 common 內部（不循環） | 網路、Playwright、gspread、環境變數、其他層 |
| parsers | common | 其他 parsers、domain、infra、actions、app |
| domain | common | 其他 domain、parsers、infra、actions、app |
| infra | common；`infra/store/*` 內部可互依 | parsers、domain、actions、app |
| actions | common、parsers、infra | domain、其他 actions、app |
| app | 全部 | — |

補充規則：
1. domain 回傳決策物件（`common/decisions`），actions 吃決策回 `ExecResult`，由 `app/stages/*` 接起來。
2. 全域可變狀態（`T.*`、`dispatch.HOME/OASES/BLOCKED`、`UNIT_*`）改成參數物件（`BuildSettings`、`HideContext`，C9），搬入時直接改，不留 shim／後門。
3. 寫入遊戲只能放 `actions/`：預設 dry、送出前核對、送出後重讀驗證、不可逆者失敗不重送。
4. 帳號級資料放 `RunContext`，村級放 `VillageContext`。
5. 新增功能＝新 stage 檔＋`app/registry.py` 登記一行，不改 orchestrator 迴圈。
6. **種族彈性**：種族資料只經 `tribe_data.TribeSpec`、以 `ServerProfile.tribe` 為鍵；程式碼不得出現 `gaul`／`roman`／`teuton`／`egyptian`／`hun`／`spartan`／`viking`（目前 Travian: Legends 全部可玩種族）等字串做判斷（只有 `tribe_data`、`config_schema`／`schema` 預設與範例、測試可以）。換族＝補表＋種族煙霧測試＋遊戲內實測。
7. **格式單一出口**：`strftime`／`isoformat`／`json.dumps` 只在 `serialize`；`gspread` 只在 `infra/store/gsheets`；只有 `*_repo` 讀寫 Sheet；只有 `infra/session` 讀寫 session 檔。
8. 倍速、地圖大小、時區、網址一律來自 `ServerProfile`。
9. **檢查工具規則名稱（A1a-3）**：`check_arch`——`MANIFEST`、`UNREGISTERED`、`MISSING_FILE`、`LAYER_DEP`、`CYCLE`、`PURE_LAYER_IO`、`ENV_IN_COMMON`、`OLD_ROOT_IMPORT`、`TRIBE_STRING`、`FORMAT_EXIT`、`GSPREAD_EXIT`、`UNDECLARED_DEP`；`check_contracts`——`NO_CLASS`、`NO_SPEC`、`SPEC_FIELDS`、`SPEC_NULLABLE`、`SPEC_KIND`、`EXAMPLE_COVERAGE`、`VALID_REJECTED`、`INVALID_PASSED`、`ROUNDTRIP_DICT`、`INVALID_BUILT`、`ROUNDTRIP_ROW`、`FILE_MISSING`、`FILE_STALE`、`FILE_EXTRA`。輸出行格式 `VIOLATION｜規則｜路徑｜細節`，exit 0／1／2＝通過／有違規／用法或輸入錯誤。

### 4.2 模組卡片（套件根 `travian_bot/`；每層都有 `__init__.py`）

> **本節 73 張卡片由 `tools/compress_cards.py` 從 v0.10 §4.2 自動轉換，內容規劃、舊源→處置、WP 欄逐字保留。** 只做兩件事：①「依賴」欄的路徑改成卡片 ID（`cm-`＝common、`ps-`＝parsers、`dm-`＝domain、`if-`＝infra、`ac-`＝actions、`ap-`＝app）；②拿掉「測試」欄。
> **測試路徑規則**：`tests/<檔所在目錄>/test_<檔名>.py`（例：`common/models.py`→`tests/common/test_models.py`；`app/stages/build.py`→`tests/app/stages/test_build.py`）；有額外測試要求者以 〔測試備註〕附在 WP 欄。
> **轉換時的自動檢查（v0.10 資料，全數通過）**：73 列欄數正確；所有依賴都能對到卡片 ID（0 個對不上）；所有依賴符合 §4.1 的層級規則（0 個違規，含 `dm-12`、`if-12`——補上 v0.10 未重跑的檢查）；所有測試欄都符合上述路徑規則。
> △＝舊檔沒讀過，簽名可能微調；✓＝已讀碼。


**common/（純資料與工具；最底層，不做任何 IO）**

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| cm-01 | `common/models.py` | 契約資料結構（dataclass；欄位、型別、規則完全依 §6.1）：VillageRef(C1)、VillageSnapshot(C2)、TransferPlan(C3)、TroopMovePlan(C4)、ActionRow(C5)、VillageSettingsRow(C6)、MarketConfig(C7)、VillageLock(C8)、BuildSettings／HideContext／VillageContext(C9)、StageResult(C10)、ServerProfile(C11)、PlanVerdict(C12)。每個結構有 validate()（呼叫 `schema`）；有對應 Sheet 欄位者有 to_row／from_row（只呼叫 `serialize`，自己不格式化） | cm-11、cm-10 | 無（新寫）。v0.22：`travian_models.py` 已讀，其 `Field`／`State`／`Slot` 是頁面解析結果、不屬於 C1～C12，改列為 cm-09 的來源；**新寫** | A1a-2 |
| cm-02 | `common/decisions.py` | 各 domain 決策的回傳結構：BuildTarget、BuildDecision、GuardDecision、FillInDecision、FocusDecision、ItemTransferDecision、AdventureDecision、HideCandidate、HideDecision、ExecResult（actions 的回傳）。A1a 先建名稱與欄位草案，A3a～A3c 讀現有函式回傳值後定案 | cm-01 | `travian_agent.py`、`stock_guard.py`、`fill_in.py`、`hero_focus.py`、`travian_transfer.py`、`travian_hero.py`、`hide_troops.py` 的回傳 dict（△）；**新寫（依舊回傳值定案）** | A1a-2 |
| cm-03 | `common/constants.py` | gid 表（含 36 陷阱、17 市場、16 集結點）、資源索引（木磚鐵穀）、頁面路徑常數、動作名稱常數（調度資源、運兵、村莊跳過） | — | `travian_const.py`（✓ v0.22 已讀）；**沿用並拆分**：留 `GID_NAMES`（補 29、30、36、44、48；v0.24：29、30、44、48 名稱待樣本核對，列入 `UNVERIFIED_GIDS`，新-2）、`RES_NAMES`、`BUILD_CATEGORIES`、`FREE_SLOT_RANGE`、`BIDI`、`BUILDING_GIDS`；`DEFAULT_TARGET_BUILDING_LEVEL`→`config_schema.DEFAULTS`（＝10；`BuildSettings` 不重複給預設，v0.25）；`RESOURCE_FIELD_PRODUCTION`、`MAX_NON_CAPITAL_FIELD_LEVEL`→cm-12；`TRIBE_NAMES`→cm-06；`ROMAN_TRIBE_ID` 不保留 | A1a-1 |
| cm-04 | `common/modes.py` | Mode（off／dry／live）；parse_mode(str, default)→Mode；effective_mode(mode, is_dry_flag: bool)→Mode（旗標為真時 live 降為 dry；**不讀環境變數**，由 `app/main` 讀 `DRY_RUN` 後傳入，v0.22）；v0.24 另有 parse_mode_checked、parse_dry_run_flag（新-2）；parse_mode 嚴格只認 off／dry／live，舊 `on`→`live` 在 config_repo 轉（新-7） | — | `runner.py` 的 `_guard_mode`／`_fill_mode` 判斷規則（✓）；**沿用規則、新寫檔** | A1a-1 |
| cm-09 | `common/parsed.py` | 解析結果結構（parsers 的輸出、domain 與 app 的輸入）：Dorf1、Dorf2、PlayerInfo、HeroState、Adventure、RallyOverview、MarketState、Oasis、TileSafety、**PageFacts**（時區、offset、lang、gpack、tribeId、timestamp、`viewData.villageList` 各村座標；D-18，v0.30 起不含 `d=` 連結）。A1a 先建草案；**PlayerInfo 已由 A2a-1 定案（✓，`parsed.py` v0.2）**；A2a-2（Dorf1／Dorf2／PageFacts／BuildOption）、A2b 對照現有 parse_* 回傳值定案 | cm-01 | `travian_pages.py` 各 parse_* 的回傳 dict（✓）；`travian_models.py` 的 `Field`／`State`／`Slot`（✓ v0.22 已讀；邊界要處理：`url=""`→None、`attacks=0` 混「無」與「未知」、`secs`→`*_s`、`building` 旗標選擇器 ✓（dorf1 資源田與 dorf2 建築位皆為 class `underConstruction`）、`cap` 順序 ✓（`maxStorage` 的 l1～l4＝木／磚／鐵／糧）；v0.31 舊服樣本；A2a-2 定案時新增 `afford_in_s`、`exchange_disabled`、移動列 kind `adventure`，見 §10 v0.31）；**新寫（依舊回傳值定案）** | A1a-2 |
| cm-05 | `common/clock.py` | utc_now()→datetime（UTC）；secs_until(ts_utc, now_utc=None)→int（向上取整，已過＝0）；resolve_clock_time(text, now_utc, profile)→datetime（頁面只有時刻 HH:MM[:SS] 時，回傳不早於 now 的下一個該時刻，UTC；夏令時間不存在的時刻丟 ServerTimeError）。**不提供安靜時段**（v0.29 你決定不需要；舊 `in_quiet_hours`、`QUIET_UTC` 不保留，Config 也無對應鍵）。遊戲頁面時間一律經 `server_profile.to_utc` 轉成 UTC，內部不用伺服器本地時間 | cm-10、cm-13 | `runner.py` 的 `_now`、`dispatch.py` 的 `parse_time`（✓；`in_quiet_hours` 不保留）；**沿用（時區改由 ServerProfile 決定）** | A1b |
| cm-06 | `common/tribe_data.py` | TribeSpec（key、name、tribe_id、units（`u1`～`u10` 種族內序號；速度、攻防、載重、成本、訓練建築，沒有資料＝None，不是 0）、merchant（載重、速度）、cranny_factor、wall_gid（高盧柵欄 33、羅馬 31、日耳曼 32，△）、trap_gid（高盧陷阱 36）、queue_mode／base_queue_slots（單條；羅馬可資源田與建築並行，△）、settler／chief 兵種索引、verified）；TRIBES 唯讀登記表（高盧＝驗證對象；高盧商人載重 750、速度 24、山洞 2 倍 △；兵種數值為常規服標準值，Community Week 數值不同、不適用（v0.29）；其他種族沿用既有表，一律標「未驗證」；匈奴只有 tribe id、沒有 TribeSpec）；get_tribe(key)→TribeSpec（未知鍵→ValidationError）；resolve_tribe(name)→key；tribe_from_state(rows)→key；tribe_keys_by_id()→{tribeId: key}；merchant_info(spec, speed)→(載重, 格／時)（speed≠1 丟 TribeDataError：倍速服的商人換算官方沒有說明，✗）；cranny_factor(spec)；global_unit_id(spec, unit_key)（高盧 21～30，D-21 同意前只在內部使用）。**其他模組只能經此取得種族資料，程式碼中不得出現種族名稱字串判斷（`check_arch` 檢查）** | cm-11 | `dispatch.py` 的 `TRIBES`、`TRIBE_ALIASES`、`resolve_tribe`、`UNIT_*`、`tribe_from_state`（✓）；另併入 `travian_const.py` 的 `TRIBE_NAMES`（v0.22；`ROMAN_TRIBE_ID` 不保留，種族判斷一律經 TribeSpec）；**沿用（純搬；加 TribeSpec 結構；高盧為驗證對象，其餘保留）** | A1b |
| cm-07 | `common/geo.py` | wrap_delta(a, b, map_half)、distance(…, map_half)、map_id(x, y, map_half)（地圖大小一律由 ServerProfile 傳入，不寫死 200；座標超出 ±map_half 丟 GeoError）；travel_seconds(dist, speed)→int（speed 為已含倍速的格／時）；parse_duration(text)→秒、fmt_duration(seconds)→'HH:MM:SS'（只處理持續時間，不處理時區；舊 `parse_time`／`fmt` 的伺服器時刻語意改放 cm-05 `resolve_clock_time`） | — | `dispatch.py` 的 `wrap_delta`、`distance`、`map_id`、`parse_time`、`fmt`（✓；`parse_time`／`fmt` 的時刻語意搬到 cm-05，本檔只留持續時間）；**沿用（加 map_half 參數）** | A1b |
| cm-08 | `common/config_schema.py` | KEYS（鍵登記：型別、預設、允許值、範圍）、DEFAULTS、ORDER、NOTES、REQUIRED_KEYS、MODE_KEYS、MODE_TO_CTX、LEGACY_KEY_MAP（舊鍵→新鍵說明）、SCHEMA_VERSION；normalize_cfg(raw)→(cfg, 問題清單)（嚴重度 error／warn；必填與 `server_*`、`tribe` 的不合法值設 None 而非預設；寫入類 mode 值不合法一律視為 off 並回報；未登記或舊鍵只警告；tribe 接受別名）；validate_cfg(cfg)→問題清單（含 ServerProfile 規則、種族、資源田上限、鎖村成對、版本過新）；profile_from_cfg(cfg)→ServerProfile（呼叫 `server_profile`，`server_*` 缺值或不合法丟 ValidationError）；merge_settings(cfg, village_rows, refs)→list[VillageContext]（村級空白＝沿用帳號預設；沒有 Villages＝單村模式，首都以 Config 為準，`modes['focus']` 固定 off）。A1b 只做單村模式，B2 補多村列 | cm-01、cm-04、cm-06、cm-10、cm-11、cm-12、cm-13 | `sheets_writer.py` 的 `_default_cfg`、`_CONFIG_ORDER`、`_CONFIG_NOTES`（✓）；**沿用常數；merge_settings 新寫** | A1b／B2 |
| cm-10 | `common/serialize.py` | **唯一的格式化出口**：to_utc_str(dt)→`YYYY-MM-DDTHH:MM:SSZ`；parse_utc(str)→dt；to_cell(value, type)／from_cell(cell, type)（Sheet 儲存格）；res_to_cells／cells_to_res；dumps_stable(obj)（鍵排序、UTF-8、2 空白縮排）；loads_checked(text, schema_name, validator=None, max_version=1)（驗證函式由呼叫端注入，新-1）；另有 dumps_compact、res_to_cost_str／cost_str_to_res、SerializeError、RES_SUFFIXES（新-2）；redact(text)（遮蔽 Cookie 與 token）。其他模組不得自行 strftime／isoformat／json.dumps（`check_arch` 檢查） | — | `sheets_writer.py` 現有寫入格式（△：A4b 讀碼後回填 §6.2 的舊格式）；**新寫** | A1a-1 |
| cm-11 | `common/schema.py` | CONTRACT_SPECS（機器可讀的 §6.1 欄位規格）；validate(name, data, ctx)→錯誤清單；ValidationError(contract, field, value, rule)；ParseError(page, reason)；contract_examples()；v0.24 另有 ensure_valid、CONTRACT_NAMES（新-2）（合規與不合規範例，供 `tools/check_contracts.py` 與測試共用） | — | 無（新寫；規格來源為 §6.1）；**新寫** | A1a-1 |
| cm-13 | `common/server_profile.py` | profile_from_dict(d)→ServerProfile（缺必填鍵→ValidationError）；to_utc(server_dt, profile)；from_utc(dt, profile)；scale_speed(value, profile)（倍速換算）；**verify_against_page(profile, facts)→list[Problem]**（D-18；純函式，Problem＝severity hard／soft、key、expected、actual） | cm-01、cm-09 | 無（新寫）；**新寫** | A1a-2 |
| cm-12 | `common/game_rules.py` | 非種族的版本／倍速規則表（逐項證據標記見檔頭）：cp_required(n_villages, profile)（✓ 官方表，倍速 1／2／3／5／10、村數 1～50；第 2 村 1 倍速為 2000；其他倍速丟 ValidationError）、speed_rules(profile)→SpeedRules（✓ 官方：產量乘倍速、建造與訓練時間除以倍速、部隊速度 x2／x3／x5 乘 2 且 x10 乘 4〔不等於倍速〕、開局文化點、新手保護基本天數）、resource_field_cap(is_capital)（非首都 10 ✓；首都 None）、settle_requirements()（✓ 3 拓荒者、各 750、擴張槽數；各槽的建築等級 △／✗）、default_protection_days(profile)（Config 有填用它，否則用官方基本天數）；RESOURCE_FIELD_PRODUCTION_1X（△ 只留資料不提供函式，S9 核對後才用） | cm-01 | `travian_const.py` 的 `RESOURCE_FIELD_PRODUCTION`、`MAX_NON_CAPITAL_FIELD_LEVEL`（✓ 已讀；產量表原註解的「累積」說法已查明有誤，數值是每塊田每小時的 1 倍速產量，仍標 △，S9 樣本核對後才用，使用時乘倍速）；其餘新寫（官方指南＋遊戲內實測）；**沿用表格資料＋新寫** | A1b |

**parsers/（純解析：HTML／JSON → 結構）**

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| ps-01 | `parsers/village.py` | parse_dorf1(html)→Dorf1（庫存、產量、容量、資源田、施工佇列、來襲數）；parse_movements(html)→list；parse_dorf2(html)→Dorf2；parse_dorf2_slots(html)→建築位；**parse_page_facts(html)→PageFacts**（D-18） | cm-09、cm-03 | `travian_pages.py` 的 `parse_dorf1`、`parse_movements`、`parse_dorf2`、`parse_dorf2_slots`（✓）；**沿用＋兩處修改＋新增 parse_page_facts**：`parse_dorf2_slots` 以 aid 去重（城牆 aid 40 等級大於 0 時有 `top`／`bottom` 兩個節點，取有 `data-building-id` 者）；`parse_movements` 辨識 `hero_on_adventure` 為 kind `adventure`（其餘未見 class 仍原樣保留，來襲 `att1`／`def1` 待 S7）；`plus_s` 沿用舊設計（Plus 由人工在遊戲內開關，有開就用、沒開就不用；舊服樣本 Plus 啟用但頁面已無 `#sidebarBoxInfobox`，`plus_s` 讀不到＝None，行為只依 `plus_active`；v0.33）、`protection_s` 的 `新手保護` 字樣待 S9 找結構選擇器（v0.31） | A2a-2 |
| ps-02 | `parsers/village_list.py` | parse_active_village(html, map_half=None)→did／None（兩處來源交叉核對，不一致回 None）；resolve_home(html, map_half=None)→(x, y)／None（Config 備用與說明字串移到呼叫端 A5b）；parse_village_list(html, map_half=None)→list[VillageRef]（新寫；與側欄不符丟 ParseError；is_capital 一律 None）；A2a-1 ✓ | cm-01、cm-03、cm-11 | `travian_pages.py` 的 `parse_active_village`、`resolve_home`（✓）；**沿用＋新寫清單**；樣本 S1a／S1b ✓（v0.36） | A2a-1／B1 |
| ps-03 | `parsers/buildings.py` | parse_building_cost(html)→成本[4]；parse_build_options(html)→可蓋清單；find_upgrade_url(html)→網址 | cm-09、cm-03 | `travian_pages.py` 的 `parse_building_cost`、`parse_build_options`、`find_upgrade_url`（✓）；`_safe_build_url` 改放 `infra/gateway`；**沿用＋三處修改**：前置條件的等級與目前等級改取數字，不比對「等級」「目前等級」字樣（去中文字面）；`exceeds_storage` 改名 `exchange_disabled`（舊服樣本中「交換資源」按鈕 disabled 與「成本合計大於庫存合計」4／4 吻合，與「成本超過容量」不符，屬推測）；新增 `afford_in_s`（`errorMessage` 內 `span.timer` 的秒數）；建造佇列滿時沒有綠色按鈕、只有金幣 `builder`，舊碼與「不能蓋」無法區分，待 S10 有空位樣本再定欄位（v0.31） | A2a-2 |
| ps-04 | `parsers/player.py` | parse_player_info(html)→PlayerInfo（文化點、Plus、族群；整段讀不到丟 ParseError，個別欄位讀不到為 None；A2a-1 ✓） | cm-09、cm-11 | `travian_pages.py` 的 `parse_player_info`（✓）；**沿用（純搬）**；Plus 依 `viewData` 的 `goldFeatures.travianPlus.isActive`（人工開關，有開就用；v0.33）；輸入頁面不限：dorf1、dorf2 皆含 `viewData`（v0.31 舊服樣本 ✓，舊碼註解「dorf1 未確認」已解） | A2a-1 |
| ps-05 | `parsers/hero.py` | parse_hero_status(html)→HeroState；parse_adventures(html)→list[Adventure]；parse_hero_inventory(json)→道具清單 | cm-09 | `travian_hero.py` 的解析部分（△ 未讀）；**拆（讀碼後定）** | A2b |
| ps-06 | `parsers/rally.py` | parse_overview(html)→RallyOverview（來襲、離村）；parse_troops_home(html)→兵種→數量；parse_send_confirm(html)→確認頁欄位；D1 擴充在外兵力 parse_troops_away | cm-09、cm-03 | `hide_troops.py` 的解析概況／確認頁部分（△ 未讀）；**拆（讀碼後定）** | A2b／D1 |
| ps-07 | `parsers/market.py` | parse_market(html)→MarketState（商人空閒／總數、單商人載重、在途進出貨）；parse_send_form(html)→送貨表單欄位 | cm-09、cm-03 | 無（新寫；依賴樣本 S3／S4／S5）；**新寫** | C1 |
| ps-08 | `parsers/oasis.py` | parse_block_json(json)→list[Oasis]（座標、類型、佔用） | cm-09 | `oasis_scan.py`（△ 未讀）；**沿用（讀碼後確認）** | A2b |
| ps-09 | `parsers/tile.py` | parse_tile_details(data)→TileSafety（有無玩家／動物、可否派兵） | cm-09 | `oasis_check.py`（△ 未讀）；**沿用（讀碼後確認）** | A2b |

**domain/（純決策：給資料、回決策物件）**

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| dm-01 | `domain/build_planner.py` | plan(snapshot, BuildSettings, buildable)→BuildDecision；plan_with_order(…)→BuildDecision（依 build_order）；next_target(…)→BuildTarget／None | cm-01、cm-02、cm-09、cm-03 | `travian_agent.py` 的 `plan`、`plan_with_order`（△）；`runner.py` 的 `_next_target`（✓）；**改寫（全域 `T.*` 改成 BuildSettings 參數，其餘沿用）** | A3a |
| dm-02 | `domain/fill_in.py` | plan_fill_ins(snapshot, BuildSettings, queue)→list[FillInDecision]；should_fill_in(…)→bool | cm-01、cm-02、cm-09、cm-03 | `fill_in.py`（△）、`travian_agent.py` 的 `plan_fill_ins`（△）；**沿用（讀碼後確認）** | A3a |
| dm-03 | `domain/guard.py` | score_stock(snapshot, hidden)→分數；decide_guard(snapshot, BuildSettings, mode)→GuardDecision | cm-01、cm-02、cm-04 | `stock_guard.py`（△）；**沿用（讀碼後確認）** | A3a |
| dm-04 | `domain/focus.py` | decide_focus(snapshot, HeroState, cfg)→FocusDecision（要不要切產量加成、切到哪一種） | cm-01、cm-02、cm-09 | `hero_focus.py` 的決策部分（△）；**拆** | A3b |
| dm-05 | `domain/item_transfer.py` | decide_item_transfer(snapshot, need, 道具清單, cfg)→ItemTransferDecision（轉哪些道具、量） | cm-01、cm-02、cm-09 | `travian_transfer.py` 的決策部分（△）；**拆** | A3b |
| dm-06 | `domain/adventure.py` | decide_adventure(HeroState, list[Adventure], cfg)→AdventureDecision | cm-01、cm-02、cm-09 | `travian_hero.py` 的決策部分（△）；**拆** | A3b |
| dm-07 | `domain/hide_plan.py` | plan(HideContext, 兵力, now)→list[HideCandidate]（到達時間、往返）；recommend(candidates)→HideCandidate／None | cm-01、cm-02、cm-07、cm-06 | `dispatch.py` 的 `plan`、`recommend`（✓）；**改寫（`HOME`／`OASES`／`BLOCKED` 全域改成 HideContext 參數）** | A3c |
| dm-08 | `domain/hide_decide.py` | decide(RallyOverview, list[HideCandidate], 兵力, cfg)→HideDecision（躲或不躲、派多少、何時回） | cm-01、cm-02、cm-09 | `hide_troops.py` 的 `decide`（△）；**沿用（讀碼後確認）** | A3c |
| dm-09 | `domain/village_lock.py` | decide_lock(VillageLock, active_did)→LockDecision（ok／skip＋原因）；record_main(active_did)→VillageLock | cm-01、cm-02 | 無（新寫）。不做舊入口平檔，A3c 直接在此交付，A6b 接入 `village_cycle`；**新寫** | A3c |
| dm-10 | `domain/market_plan.py` | plan_transfers(list[VillageSnapshot], MarketConfig, 村角色)→list[TransferPlan]（捐方保留量、受方補到目標、商人載重上限、扣除在途、倉容上限） | cm-01、cm-06、cm-07 | 無（新寫；政策依 D-4）；**新寫** | C2 |
| dm-11 | `domain/troop_plan.py` | plan_troop_moves(list[VillageSnapshot], 政策)→list[TroopMovePlan]（D-3 定案後） | cm-01、cm-06、cm-07 | 無（新寫）；**新寫** | D2 |
| dm-12 | `domain/plan_validate.py` | validate_order(RawBuildOrder, VillageSnapshot, BuildSettings, buildable)→PlanVerdict（C12）；check_step(step, …)→StepVerdict。驗證項目：①格式符合 C12 輸入欄位；②建築 gid 存在於 `constants`；③目標等級不超過上限（資源田依 `game_rules.resource_field_cap(is_capital)`）；④前置條件在該步之前已滿足（含目前已蓋）。**只判定下一步要執行的那一步是否可執行**，其他被拒的步驟記錄在 `rejected` 但不 hold。純函式，不讀 Sheet、不碰網路 | cm-01、cm-02、cm-09、cm-03、cm-12 | 無（新寫）；`travian_agent.plan_with_order`（△）若已有內建檢查，讀碼後併入；**新寫** | A3a |

**infra/（有 IO：session、請求閘道、Sheet、通知）**

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| if-01 | `infra/session.py` | parse_cookie_header(str)→dict；launch()→(browser, context)；load_cache／seed_cookie；validate_session()→bool；keep_alive()；save_state()；例外 SessionLost | cm-03、cm-01、cm-10 | `travian_ci_run.py` 的 `parse_cookie_header`、建立 browser／context、cache 與種子 Cookie 流程（✓）；**沿用（純搬）** | A4a |
| if-02 | `infra/gateway.py` | Gateway(session, profile, limits)（網址一律由 ServerProfile.base_url 組出）；get(path, did=None, render=False)→html；post(path, data, did=None)→html；safe_url(url)→bool（URL 白名單）；隨機等待與重試規則；request_count()／elapsed() 供耗時紀錄。A4a 不加 did（行為不變），B1 加 did 與 newdid | cm-03、cm-01 | `travian_ci_run.py` 的 `get_html`、`submit`（✓）；`travian_pages.py` 的 `_safe_build_url`（✓）；**拆（B1 加 did）** | A4a／B1 |
| if-03 | `infra/notify.py` | notify(level, msg)（目前只印 log；E1 再加 Email／Telegram） | — | `notify.py`（△）；**沿用（純搬）** | A4a |
| if-04 | `infra/store/gsheets.py` | get_credentials()；open_sheet()；has_sheet(name)；batch_write(ws, rows)（合併寫入、配額友善） | — | `sheets_writer.py` 的 `_get_credentials`、`open_sheet`、`has_sheet`（✓）；**沿用（純搬）＋補批次寫入** | A4a |
| if-05 | `infra/store/config_repo.py` | load_config()→dict；ensure_config_rows()；disable(scope=帳號／村, did, reason)（村級錯誤不關帳號） | if-04、cm-08 | `sheets_writer.py` 的 `load_config`、`_ensure_config_rows`、`disable`（✓）；**拆（disable 區分帳號級與村級）** | A4b |
| if-06 | `infra/store/village_repo.py` | load_villages()→list[VillageSettingsRow]（沒有 Villages 分頁就回空清單＝單村模式）；ensure_villages_tab()；add_detected(VillageRef)（偵測到新村時加一列，等你設定）。A4b 只做唯讀的 load_villages，B2 補其餘 | if-04、cm-01 | 無（新寫）；**新寫** | A4b／B2 |
| if-07 | `infra/store/action_repo.py` | log_action(ActionRow)（9 欄＋第 10 欄 did）；last_action_age_hours(action, did=None)→float | if-04、cm-01 | `sheets_writer.py` 的 `log_action`、`last_action_age_hours`（✓）；**沿用（B2 加 did）** | A4b／B2 |
| if-08 | `infra/store/state_repo.py` | write_state(did, rows)（每村各一組；A4b 先 1:1 單村） | if-04、cm-01 | `sheets_writer.py` 的 `write_state`（✓）；**改寫（B2 改每村）** | A4b／B2 |
| if-09 | `infra/store/snapshot_repo.py` | append_row(VillageSnapshot)（Sheet1 24 欄＋did）；write_structure(did, 資源田, 建築, 可蓋, 變動) | if-04、cm-01 | `sheets_writer.py` 的 `append_row`（✓）；`village_log.py`（△ 未讀）；**拆** | A4b／B2 |
| if-10 | `infra/store/oasis_repo.py` | save(center, list[Oasis])（只取代該中心的列）；load(center)→list；list_centers()→list | if-04、cm-09 | `oasis_store.py` 的 `save`、`load`（✓）；**改寫（B2 改多中心；A4b 先 1:1）** | A4b／B2 |
| if-11 | `infra/store/market_repo.py` | write_market(did, MarketState)；record_transit(TransferPlan, ExecResult)；recent_transit(did)→list（防重送） | if-04、cm-01、cm-09、cm-02 | 無（新寫；Market／Transit 分頁）；**新寫** | C1 |
| if-12 | `infra/store/plan_repo.py` | load_build_order(did)→RawBuildOrder／None（讀 `build_order` 分頁；分頁不存在或空白→None，不報錯）。**只讀、不寫**（Gemini／Apps Script 是唯一寫入者）。輸入格式在 A4b 讀實際分頁後回填 | if-04、cm-01、cm-11 | 無（新寫）；現有讀 `build_order` 的程式（△，讀碼確認）；**新寫** | A4b |

**actions/（會改變遊戲狀態的動作；每個都有 off／dry／live 與送出後驗證）**

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| ac-01 | `actions/village_switch.py` | switch_to(gw, did)；assert_active(gw, did)→bool（讀 dorf1，用 parse_active_village 核對） | if-02、ps-02、cm-03 | 無（新寫）。A5b 先建檔，單村時 switch_to 為無操作；B1 起實際切村；**新寫** | A5b／B1 |
| ac-02 | `actions/build_exec.py` | submit_upgrade(gw, did, BuildTarget, mode)→ExecResult（送出前核對成本；送出後重讀驗證資源被扣、佇列增加） | if-02、ps-01、ps-03、cm-02、cm-04 | `runner.py` 送出升級與驗證那段（✓）；**沿用（純搬）** | A5a |
| ac-03 | `actions/item_transfer_exec.py` | execute_item_transfer(gw, ItemTransferDecision, mode)→ExecResult（PUT 取 nonce→POST；不可逆、失敗不重送） | if-02、ps-05、cm-02、cm-04 | `transfer_io.py`、`travian_transfer.py` 的執行段（△）；**拆** | A5a |
| ac-04 | `actions/focus_exec.py` | read_focus(gw)→HeroState；set_focus(gw, FocusDecision, mode)→ExecResult | if-02、ps-05、cm-02、cm-04 | `hero_focus.py` 的 `make_focus_io`（△）；**拆** | A5a |
| ac-05 | `actions/hero_exec.py` | read_hero(gw)→HeroState；click_adventure(gw, Adventure, mode)→ExecResult（點擊前核對、點擊後重讀確認） | if-02、ps-05、cm-02、cm-04 | `travian_ci_run.py` 的 `click_adventure`（✓）；**沿用（純搬）** | A5a |
| ac-06 | `actions/hide_exec.py` | send_troops(gw, did, HideDecision, mode)→ExecResult（兩步驟＋確認頁核對）；wait_return_window(…) | if-02、ps-06、cm-02、cm-04、cm-05 | `hide_troops.py` 的 `run_once`（△；決策部分已移 `domain/hide_decide`）；**拆** | A5b |
| ac-07 | `actions/oasis_exec.py` | fetch_block(gw, x, y)→json；scan(gw, center, radius)→list[Oasis]；verify_oasis(gw, Oasis)→TileSafety（派兵前即時驗證） | if-02、ps-08、ps-09、cm-09 | `oasis_store.py` 的 `fetch_block`、`scan`（✓）；`oasis_check.py` 即時驗證（△）；**沿用（純搬）** | A5b |
| ac-08 | `actions/market_exec.py` | send_resources(gw, TransferPlan, mode)→ExecResult（填表→確認→送出後重讀商人與在途貨驗證；不可逆，失敗不重送） | if-02、ps-07、cm-01、cm-02、cm-04 | 無（新寫；依賴樣本 S5）；**新寫** | C3 |
| ac-09 | `actions/troop_exec.py` | send_reinforce(gw, TroopMovePlan, mode)；send_recall(…)→ExecResult（確認頁核對後才按確認） | if-02、ps-06、cm-01、cm-02、cm-04 | 無（新寫；依賴樣本 S6）；**新寫** | D2 |

**app/（編排：只在這層決定先後）**

| ID | 檔 | 內容規劃 | 依賴 | 舊源→處置 | WP |
|---|---|---|---|---|---|
| ap-01 | `app/main.py` | main()：建 Session→取村莊清單→**啟動檢查（`verify_against_page`；hard＝本輪 hold，D-18）**→建 RunContext→orchestrator.run→存 session。舊入口 `travian_ci_run.py` 不留薄殼、不當回退，搬完歸檔 | if-01、if-02、if-05、if-06、cm-08、cm-13、ps-01、ps-02、ap-02、ap-08 | `travian_ci_run.py` 的 `main`：session 驗證、安靜時段 keep-alive（v0.29：取消安靜時段，不保留）、`dispatch.configure(...)`（✓）；**拆（`dispatch.configure` 改為建 HideContext）** | A6b |
| ap-02 | `app/run_context.py` | RunContext（帳號級：cfg、Gateway、各 repo、tribe、HeroState、now）；StageIO（測試時注入假 IO） | if-02、if-05、if-07、if-08、if-09、if-10、cm-01、cm-09 | 無（新寫）；**新寫** | A6a1 |
| ap-03 | `app/stage_base.py` | Stage（name、scope、mode_key、precondition、run、budget）；run_stage(stage, rc, vc, snap)→StageResult（例外一律接住，記一列 Actions，不往上丟） | ap-02、cm-01、cm-04 | 無（新寫）；**新寫** | A6a1 |
| ap-04 | `app/registry.py` | STAGES 登記表（名稱、層級＝村／帳號、mode_key、預設順序）；village_stages()；account_stages()。新增功能＝新增 stage 檔＋在此登記一行 | ap-03 | 無（新寫）；**新寫** | A6a1 |
| ap-05 | `app/observe.py` | observe_village(rc, vc)→VillageSnapshot（抓 dorf1／dorf2→parsers→快照，寫 snapshot_repo／state_repo）；fetch_build_options(rc, vc)（唯讀）；observe_player(rc)→PlayerInfo | ap-02、if-02、ps-01、ps-03、ps-04、if-09、if-08、cm-01、cm-09、cm-12 | `runner.py` 的 `log_village_snapshot`、`log_village_structure`、`log_player_state`、`build_state_rows`、`_setup_player`、`cp_summary`（✓）；`travian_pages.py` 的 `fetch_build_options`（✓）；**拆** | A6a1 |
| ap-06 | `app/formatting.py` | describe、with_queue、mins、fname、flv、now_str | cm-05 | `runner.py` 的 `describe`、`_with_queue`、`_mins`、`_fname`、`_flv`、`_now`（✓）；**沿用（純搬）** | A6a1 |
| ap-07 | `app/village_cycle.py` | run_village(rc, vc)→list[StageResult]：village_lock 核對→observe→依 registry 順序跑村級階段。串接前提（例如 wait_res 才走轉移）原樣保留成各 stage 的 precondition。**寫入前再核對（v0.20）**：進村時 `assert_active` 一次；之後每個寫入類 stage（`build` 與 mode 為 dry／live 的 stage）執行前再呼叫一次，不符則該村本輪剩餘的寫入 stage 全記 `skipped`（原因沿用 C8「村莊跳過」）、不 `disable()`；唯讀 stage 不檢查。依賴不變（已含 ac-01） | ap-05、ap-04、ap-03、dm-09、ac-01、cm-01 | `runner.py` 的 `run_build_cycle` 串接段（✓）；**拆** | A6b |
| ap-08 | `app/orchestrator.py` | run(rc, refs, vcs)：排優先序（有來襲先、最久沒處理的次之）、逐村執行、時間預算與 deferred、帳號級階段、錯誤隔離（村級例外不關帳號）、寫彙總。A6b 只做單村版，B3 擴成多村 | ap-07、ap-04、ap-03、if-05、if-03、cm-01、cm-05 | 無（新寫）；**新寫** | A6b／B3 |
| ap-10 | `app/stages/build.py` | run：plan_repo.load_build_order → domain.plan_validate → （verdict=proceed）domain.build_planner → actions.build_exec → 寫 Actions 列；（verdict=hold）本輪**不**呼叫 build_planner／build_exec，只寫一列 Actions（`skipped`＋被拒原因），其餘 stage 照跑；`build_order` 為 None 時行為同 hold（記錄「無 build_order」） | ap-03、ap-06、dm-12、dm-01、ac-02、if-12、if-07、cm-02 | `runner.py` 的 `run_build_cycle` 建城段（✓）；**拆** | A6a2 〔測試備註：含：壞的 build_order → hold 且沒有任何寫入〕 |
| ap-11 | `app/stages/item_transfer.py` | run：domain.item_transfer → actions.item_transfer_exec → 寫 Actions 列（僅英雄所在村） | ap-03、ap-06、dm-05、ac-03、if-07、cm-02 | `runner.py` 的 `_try_transfer`（✓）；**拆** | A6a2 |
| ap-12 | `app/stages/focus.py` | run：domain.focus → actions.focus_exec → 寫 Actions 列（僅英雄所在村） | ap-03、ap-06、dm-04、ac-04、if-07、cm-02 | `runner.py` 的 `_try_focus`（✓）；**拆** | A6a2 |
| ap-13 | `app/stages/fill_in.py` | run：domain.fill_in → actions.build_exec → 寫 Actions 列 | ap-03、ap-06、dm-02、ac-02、if-07、cm-02 | `runner.py` 的 `_try_fill_in`、`_fill_mode`（✓）；**拆** | A6a2 |
| ap-14 | `app/stages/guard.py` | run：domain.guard → 依決策呼叫現有 actions（實際動作依 `_try_guard` 現行行為，A6a2 讀碼確認）→ 寫 Actions 列 | ap-03、ap-06、dm-03、ac-02、ac-03、if-07、cm-02 | `runner.py` 的 `_try_guard`、`_guard_mode`（✓）；**拆**；暴露風險 lam 規則改由 Config `guard_exposure` 承接（新-8） | A6a2 |
| ap-15 | `app/stages/hide.py` | run：parsers.rally 讀概況→domain.hide_plan／hide_decide→actions.hide_exec；逐村、讀該村 HideContext | ap-03、ap-06、ps-06、dm-07、dm-08、ac-06、if-07、cm-02 | `hide_observe.py` 的 `observe`（✓）；**改寫（逐村、讀 HideContext）** | A6a2 |
| ap-16 | `app/stages/oasis.py` | run：actions.oasis_exec 掃描（額度內）→ oasis_repo 存多中心 → 把清單寫入該村 HideContext（不再寫模組全域） | ap-03、ac-07、if-10、cm-01、cm-09 | `oasis_store.py` 的 `apply`、`refresh`（✓）；**改寫** | A6a2 |
| ap-17 | `app/stages/hero.py` | run（帳號級）：actions.hero_exec 讀英雄→domain.adventure→actions.hero_exec 點冒險→寫 Actions 列 | ap-03、ap-06、dm-06、ac-05、if-07、cm-02 | `runner.py` 的 `run_hero_cycle`、`_hero_log`（✓）；**沿用（純搬）** | A6a2 |
| ap-18 | `app/stages/market.py` | run（帳號級，所有村觀察完才跑）：domain.market_plan→（送出前對關鍵村重讀）→actions.market_exec→market_repo／Actions | ap-03、ap-05、dm-10、ac-08、if-11、if-07、cm-01 | 無（新寫）；**新寫** | C4 |
| ap-19 | `app/stages/troops.py` | run（帳號級）：domain.troop_plan→actions.troop_exec→Actions | ap-03、ap-05、dm-11、ac-09、if-07、cm-01 | 無（新寫）；**新寫** | D2 |

#### tools/、tests/、其他

| 檔 | 內容 | WP |
|---|---|---|
| `tools/check_arch.py` | 依賴方向、無循環、檔案都在 manifest 登記、**新程式不得 import repo 根目錄的舊模組（v0.22）**；三個單一出口（種族字串、`strftime`／`isoformat`／`json.dumps`、`gspread`）；輸出 `VIOLATION｜規則｜路徑｜細節`，exit 0／1／2（通過／有違規／用法或輸入錯誤），`--json` 用 `dumps_stable`；WP 驗收必跑（`--expect-wp` 列出到目前為止所有已完成的 WP，加 `--strict`；`UNDECLARED_DEP` 在 `--strict` 才算違規） | A1a-3 |
| `tools/arch_manifest.py` | list，每項鍵 `id`、`path`、`layer`、`deps`、`wp`、`disp`；與 §4.2 同源 | A1a-3 |
| `tools/check_contracts.py` | 比對 models dataclass 與 `schema.CONTRACT_SPECS`，跑全部合規／不合規範例與 `from_row(to_row(x)) == x` | A1a-3 |
| `tools/dispatch_cli.py` | 離線躲兵計畫與推薦 CLI（原 `dispatch.main`） | A3c |
| `tools/scrub_sample.py` | 樣本脫敏後存 `tests/samples/` | SAMP |
| `tools/scrape_and_log.py` | `scrape_and_log.py`（△）→沿用或歸檔 | 待讀碼 |
| `tests/test_tribe_switch.py` | 對 `TRIBES` 每個種族＋假 ServerProfile＋樣本快照跑每個 domain 規劃函式，不得出錯、不得寫死高盧（A3a 起，之後每個 domain WP 都加入） | A3a |
| `tests/contracts/` | 由 `schema` 產生的 `{契約名}.valid.json`／`.invalid.json`（例：`VillageRef.valid.json`）（不得手改） | A1a-3 |

`appsscript/` 位置不動（B6 改）；`auto_build.yml` 位置不動，A6b 把入口換成 `python -m travian_bot.app.main`（D-10 確認）。

### 4.3 功能線（stage→控制鍵）

建城 `build`（無 mode，一律執行；讀 plan_repo→plan_validate→build_planner→build_exec）｜插隊 `fill_in`（`fill_mode`）｜庫存守衛 `guard`（`guard_mode`）｜道具庫轉資源 `item_transfer`（`transfer_mode`△）｜產量加成 `focus`（`focus_mode`△）｜躲兵 `hide`（`hide_mode`）｜綠洲掃描 `oasis`（`oasis_mode`△）｜英雄冒險 `hero`（`hero_mode`△）｜市場 `market`（`market_mode`）｜運兵 `troops`（`troop_mode`△）｜村莊鎖定／切村 `village_cycle`（無 mode，一律執行）。△＝沿用現有 Config 鍵名，A6a2 讀碼確認。快照與結構分頁由 `app/observe` 統一寫入。

### 4.4 執行模型

- **觀察→決策→動作**：每村先觀察（唯讀，產生 VillageSnapshot）→ domain 純函式決策 → actions（受 mode 控制）。帳號級階段（市場、運兵、英雄）在**所有村觀察完才跑**，送出前對關鍵村重讀（快照可能已過期數十秒到數分鐘）。
- **每輪順序**：①帳號級準備（session 驗證、村莊清單、Config＋Villages）→ ②依優先序逐村（有來襲最先→最久沒處理）：`switch／assert_active`＋`village_lock`→觀察→村級階段 `hide`（有來襲才動）→`build`→`item_transfer`／`focus`／`fill_in`／`guard`→`oasis`（額度內）→ ③帳號級 `hero`→`market`→`troops` → ④存 session、寫彙總。
- **Stage 介面**：name／scope（village|account）、mode_key（off／dry／live，村級可覆寫）、precondition、`run(rc, vc, snap)`→StageResult（C10）、budget（預估請求數與秒數）；例外一律由 `run_stage` 接住、記一列 Actions 後繼續。
- **寫入前核對（v0.20）**：切村是伺服器端狀態，一輪中途你手動切村會讓後面的寫入打錯村。`village_cycle` 在每個寫入類 stage 前呼叫 `assert_active`（見 ap-07）；檢查放 app 層，actions 彼此不互相依賴。多村的 `parse_active_village` 可信度待 S1／S2（B1）。
- **VillageContext（C9）** 取代全域變數：did、名稱、座標、is_capital、role、build_settings、各 stage mode（已合併帳號預設）、hide_context、priority；由 `merge_settings` 每輪開頭為每村建好。

### 4.5 Sheet 結構（v0.14：新 Sheet 全部嚴格格式；「只追加、舊欄位位置不動」只適用舊伺服器，見 D-15、D-20）

| 分頁 | 目標 | 擁有者 | 相容 |
|---|---|---|---|
| Config | 帳號級預設＋`schema_version`；舊鍵保留 | config_repo | 缺 `Villages`＝單村模式 |
| **Villages**（新） | 每村一列（C6） | village_repo | 空白欄＝沿用 Config |
| Actions | 第 10 欄 `did` | action_repo | 只追加 |
| state | 每村一組（含 did） | state_repo | Apps Script 同步改 |
| Sheet1／Fields／Buildings／Buildable／Changes | 加 `did` 欄 | snapshot_repo | 追加欄位 |
| Oases | 多中心並存（依中心取代／讀取） | oasis_repo | 欄位不變，新增中心欄 |
| **Market／Transit**（新） | 商人與在途貨快照；已送出貨運紀錄（防重送） | market_repo | 新分頁 |
| goals／build_order／advice／log | Apps Script 寫；Python 只讀 `build_order` | Apps Script | 多村版 B6 |

### 4.6 架構檢查結論（v0.8 重跑；v0.10 新增部分、v0.16 的 cm-09／cm-13／ps-01／ap-01 卡片變動未重跑；依賴方向待 A1a 的 `check_arch` 驗證，尤其 cm-13→cm-09）

已用程式驗證：依賴方向、同層無互依、無循環、WP 建立順序、舊檔覆蓋、功能線一致、無孤兒、契約範例（10 個契約合規範例通過、20 個不合規範例被擋且指到正確欄位）。曾發現並修正：`core/` 混純與 IO→拆 `common/`＋`infra/`；`models` 移到 common；infra 先於 actions；`village_switch`、唯讀 `load_villages`、單村 `merge_settings` 提前；domain 與 actions 互不依賴；契約欄位單位／型別不明→補齊（C2 `queue_busy_until`→`queue_free_in_s`、時間統一 UTC 字串、C3／C4 加 `plan_id`、時區與地圖大小改由 ServerProfile、種族加 TribeSpec）。限制：標 △ 的舊檔簽名尚未對照，WP 讀碼後有差異走 §5.1。v0.29：A1b 的卡片變動已重新轉出 `arch_manifest`，並以 `check_arch --strict` 驗證（見 §9）。

---

## 5. 舊程式：套用或重新規劃

### 5.1 判定（每個 WP 對每個交付模組都做）

1. **讀**卡片「舊源」欄指到的舊檔（標 △ 的先請使用者上傳）。
2. 以下**五條全成立才套用**：a. 舊函式輸入輸出對得上卡片簽名與 §6 契約（差別只是搬位置或加參數）；b. 不依賴模組全域可變狀態，或能用參數物件取代；c. 不違反 §4.1 依賴表；d. 有測試或樣本可做 golden 比對（舊函式只在離線測試當對照）；e. 格式符合 §6（UTC 字串時間、資源 [木,磚,鐵,穀]、空值規則），舊格式在邊界轉換、不帶進新模組。
3. **套用**：照搬或最小修改、不留 shim、golden 一致即完成。
4. **重新規劃**（任一條不成立）：不硬套、不「先放著」；先在回覆提出**修改後卡片**（檔名、公開函式、依賴、不能套用的原因）並確認依賴規則仍成立；你同意後才更新本檔 §4.2（升版、§10 追加決策）再實作；影響別的卡片或契約要列出受影響 ID／WP 並升契約版。
5. 交接區塊每個模組寫「套用」或「重新規劃（原因）」。
6. 做完跑 `check_arch`、`check_contracts`；domain WP 另跑種族煙霧測試。

### 5.2 未建卡的舊檔處置

`travian_parser.py`（△ 讀碼後併入 `parsers/village.py` 或歸檔）｜`scrape_and_log.py`（△ 移 `tools/`）｜`auto_build.py`（不在排程中，歸檔不遷移）｜`test_*.py`（隨模組搬到對應 `tests/` 層，不留舊位置）｜`auto_build.yml`（位置不動，A6b 換入口）。其餘舊檔→新模組的對應見 §4.2 各卡片的「舊源」欄。

### 5.3 遷移策略

1. 新結構一層一層長出來，**無轉接層**；舊程式從頭到尾不在新伺服器跑（D-14）；A 系列完成後歸檔。
2. **搬遷與功能分開**：A 系列驗收＝行為不變（同樣本新舊輸出一致；整合驗收見 GA）；多村功能另開 WP、不混 commit。
3. 每個 WP 一個 commit、可單獨 git 回復；部署時同一 commit 放整組。
4. 順序由下往上：common→（parsers／domain／infra 可並行）→actions→app。全域變數搬入時直接改參數物件。
5. golden 比對：樣本放 `tests/samples/`（用 `scrub_sample.py` 脫敏）。
6. 不先動 Sheet 結構，只追加。
7. 入口最後建：A6b 後 yml 只指新入口，舊 `travian_ci_run.py` 歸檔；GA 通過才 live。
8. 搬遷期間第 2 村先出現：GA 前 bot 不 live，改手動玩；A 系列可停在任何一步（`village_lock` 仍須在 GA 前完成）。

---

## 6. 介面與檔案格式協定（契約 C-v0.5，全部 ✗ 草案）

> 所有跨模組／跨檔案／跨 Sheet 資料只有一種正規寫法。**讀入可寬鬆（去空白、接受已登記同義寫法），寫出一律嚴格。** 本章即 `schema.CONTRACT_SPECS` 的來源；A1a 依下列規則重建合規／不合規範例並轉成測試（v0.10 的範例僅為示意，不另保留）。改欄位要升版並寫進 §10。

### 6.1 通用規則

| 項目 | 規則 |
|---|---|
| 時間 | 內部與持久化一律 **UTC**，`YYYY-MM-DDTHH:MM:SSZ`（秒精度、Z 結尾，例 `2026-11-02T08:15:30Z`）。頁面伺服器時間只在解析時用 `server_tz` 轉 UTC。**持續時間一律整數秒、欄位名以 `_s` 結尾** |
| 資源 | 長度 4 整數陣列，**順序固定：木、磚、鐵、穀**；Sheet 展開 4 欄（`_wood`／`_clay`／`_iron`／`_crop`），只有 `Actions.cost` 用逗號字串 `木,磚,鐵,穀` |
| ID | `did`／`aid`／`gid` 程式內 int、Sheet 存數字；讀回 `int()`，空白→None；不加引號或前綴 |
| 座標 | int，絕對值 ≤ `map_half`；map id 一律由 `geo.map_id` 算 |
| 空值 | 可選欄位 JSON `null`、Sheet 空白；必填缺失＝錯誤；**不得用 0、-1、"-"、"none" 代替空值** |
| 布林 | 寫出：Sheet `TRUE`／`FALSE`、JSON `true`／`false`；讀入接受 TRUE／FALSE／true／false／1／0，其他＝錯誤 |
| 列舉 | 小寫英文；未知值＝錯誤。**唯一例外**：寫入類 mode 值不合法一律視為 `off` 並回報 |
| 數字 | 整數欄不帶小數點／千分位；比例用整數 `*_pct`（0..100）；時數 `*_hours` 為 float |
| 字串 | UTF-8；Sheet 儲存格不含換行；超長截斷加 `…`（只在 serialize 做並標記）；讀入去前後空白 |
| JSON | UTF-8 無 BOM、LF、鍵排序、結尾換行；檔案縮排 2 空白、Sheet 儲存格內緊湊且 ≤40000 字元；**檔案頂層必須有 `schema_version`（int）** |
| 版本 | 每個持久化輸出都有 `schema_version`；**只能追加欄位**，不刪欄、不改欄序／型別；破壞相容升 major 並寫 §10；讀到比自己新的 major→拒絕 |
| 錯誤 | 驗證失敗丟 ValidationError、解析失敗丟 ParseError；**不得靜默回傳預設值**；`run_stage` 接住並記 `Actions`（`result=failed`） |
| 機密 | Cookie、token、帳密不得出現在 log、Sheet、樣本、交接區塊、錯誤訊息；輸出文字先過 `serialize.redact` |

型別寫法：`int≥0`、`int a..b`、`×4`＝資源陣列（木磚鐵穀）、`T?`＝可為 null。

### 6.2 契約逐欄規格

**子結構**
- `BuildTarget`：aid int≥1（1～18 資源田，19～40 建築）、gid int≥1、name str≤40、to_level int≥1、cost int≥0×4、ready_in_s int≥0（0＝現在就夠）
- `Merchants`：free int≥0、total int≥0、capacity_each int≥1；規則 free ≤ total
- `Transit`：from_did int≥1?（別的玩家為 null）、to_did int≥1、amount int≥0×4、arrive_utc UTC 字串
- `Oasis`：x int、y int、kind str≤20（如 wood25）、safe bool?（未驗證 null）
- `BuildSettings`：target_level int≥1（非首都上限 10 △）、queue_slots int 1..3、build_order str?（格式 ✗ 待 A4b／B6）
- `HideContext`：home_x、home_y int、oases list[Oasis]、blocked list[int≥0]（封鎖 map id）、tribe str（須為 `TRIBES` 鍵）

**C1 `VillageRef`**：did int≥1、name str≤60、x、y int、is_capital bool?（頁面讀不到則 null，以 Villages 為準）、active bool。規則：|x|、|y| ≤ map_half。

**C2 `VillageSnapshot`**（每村每輪唯讀快照；建立後唯讀，stage 只能經 `StageResult.snapshot_updates` 提出更新）：did int≥1、ts_utc、stock int≥0×4、prod int×4（可負，穀可為負）、cap_wh int≥0、cap_gr int≥0、hidden int≥0×4（山洞可隱藏量，高盧倍率傾向 2 △）、**queue_free_in_s** int≥0（佇列最早空出還要幾秒，0＝空閒）、queue_slots_used int≥0、next_target BuildTarget?、merchants Merchants?（市場 0 級為 null）、incoming_res list[Transit]、outgoing_res list[Transit]、incoming_attacks int≥0?（B8，未知 null）、units_home dict?、units_away dict?（兵種鍵→int≥1，未讀 null）。

**C3 `TransferPlan`**：plan_id（`^T\d{12}-\d+-\d+$`＝`T`＋規劃時間 `YYYYMMDDHHMM`＋`-來源-目標`，防重送鍵）、from_did、to_did int≥1、amount int≥0×4、merchants_needed int≥1、arrive_utc、reason str≤200、mode off／dry／live。規則：from≠to；amount 總和>0；`merchants_needed = ceil(總和 ÷ capacity_each)`；同一 plan_id 只能送一次（Transit 防重送）。

**C4 `TroopMovePlan`**：plan_id（`^M\d{12}-\d+-\d+$`）、from_did、to_did、units dict（鍵 `u1`～`u10`、`hero`，數量≥1，至少一種）、kind reinforce／recall（其他待 D-3）、arrive_utc?、reason str≤200、mode。規則：from≠to。

**C5 `ActionRow`**（Actions 目標格式 10 欄，欄序固定；是否沿用舊 9 欄由 D-15 決定）：ts_utc、action str≤40（常數）、aid int≥1?、gid int≥1?、level int≥0?、cost（`^\d+,\d+,\d+,\d+$`）?、mode off／dry／live、result ok／dry／skipped／failed／deferred、detail str≤300（可空字串）、**did** int≥1（第 10 欄）。規則：`mode=dry` 時 result 不可為 ok。

**C6 `VillageSettingsRow`**（Villages 分頁，一列一村，欄序依此）：did int≥1、name str≤60、enabled bool（預設 TRUE）、role capital／resource／military／other（預設 resource）、is_capital bool（預設 FALSE）、queue_slots int 1..3（預設 1）、build_order str?、hide_mode／guard_mode／fill_mode off／dry／live?（空白＝用 Config）、priority int 1..999（預設 100，越小越先）、note str≤200?。規則：全表最多 1 列 is_capital=TRUE；did 不重複；`enabled=FALSE` 整輪跳過、不寫 Actions；座標由頁面讀取不在此填。

**C7 市場 Config 鍵**：見 §6.4 `market_*`。

**C8 `VillageLock`**（Config 兩個鍵）：main_did int≥1、main_did_set_utc。第一次執行記錄、之後只讀；每輪核對 main_did 與目前 active 村，不符該村本輪跳過、寫「村莊跳過」，**不 `disable()`**；G2 後由 Villages 取代。

**C9 `VillageContext`**：did、name、x、y、is_capital bool、role、enabled bool、priority int 1..999、build_settings、modes dict（鍵只能是 fill_in／guard／item_transfer／focus／hide／oasis／hero／market／troops，`build` 不受 mode 控制；值 off／dry／live，已合併帳號預設與村級覆寫）、hide_context。規則：`hide_context.tribe == ServerProfile.tribe`。

**C10 `StageResult`**：status ok／skipped／failed／deferred、actions list[ActionRow]（由 app 統一寫入）、snapshot_updates dict（鍵須是 C2 欄位名）、note str≤200（failed 時不可為空）、requests_used int≥0、elapsed_s float≥0。

**C11 `ServerProfile`**：server_id str≤80、base_url（`^https://[^/\s]+/?$`，不含路徑與帳密）、game legends（預設）、speed int≥1（預設 1）、map_half int≥1（預設 200 △）、tribe str（預設 gaul；非 gaul 啟用時警告「未驗證」）、start_utc、server_tz（`^(UTC|[A-Za-z_]+/[A-Za-z_+\-0-9]+)$` IANA）、protection_days int≥0?（△）、version str≤20?（頁面 gpack 版號，例 `678.2`）、**locale** str（預設 `zh-TW`；與頁面 `<html lang>` 不符→啟動警告，parsers 不得依賴中文字面）。`server_tz` ＝ 頁面 `Travian.Game.timeZone` 的 IANA 名稱（舊頁為 `Europe/London`，有夏令時間）。規則：tribe 須為 `TRIBES` 鍵（`profile_from_dict` 檢查）；不得含帳密或 Cookie。

**C12 `PlanVerdict`**（build_order 驗證結果）：did int≥1、checked_utc、verdict proceed／hold、next_seq int≥1?（整份讀不到為 null）、rejected list[{seq int≥1、rule bad_format／unknown_building／level_over_cap／prereq_unmet／missing_order、reason str≤200}]（可為空）。輸入 `RawBuildOrder` 欄位 ✗ 待 A4b 回填（至少需每步：順序號、目標建築、目標等級）。
- `hold` 若且唯若 `rejected` 含 `seq=next_seq` 項目，或 `rule=missing_order`（此時 next_seq 為 null）。
- hold 時 stage 不寫入遊戲，只寫一列 Actions（`skipped`＋第一個被拒原因）；下一輪重新讀取並驗證，**不快取上一份通過的版本、不套預設順序**。
- 後面的步驟被拒但還沒輪到：`proceed`，`rejected` 照列、同一份被拒內容只記錄一次。

### 6.3 Google Sheet 分頁格式

> **D-15 已定（v0.14）＝全部嚴格格式**：下表所有分頁（含 state、Sheet1、Fields／Buildings／Buildable／Changes、Oases）都依 §6.1 重新定義欄位，不沿用舊欄位位置；標 ✗ 的列仍是草案，欄位清單待 A4b 以舊函式為參考定案並升契約。Apps Script 要同步改成讀新格式（D-20）。

| 分頁 | 識別鍵 | 寫入方式 | 唯一寫入者 | 格式 |
|---|---|---|---|---|
| Config | key | 依鍵取代；`schema_version` 只增 | config_repo | 三欄 `key`、`value`、`note` |
| Villages（新） | did | 依 did 取代；偵測到新村追加一列（`enabled=FALSE` 待你設定） | village_repo | C6 |
| Actions | 無 | 只追加 | action_repo | 目標 C5（10 欄） |
| state | did | 依 did 區塊取代 | state_repo | ✗ 舊格式待回填＋did 欄 |
| Sheet1 | 無 | 只追加 | snapshot_repo | ✗ 舊 24 欄待回填；**只在最後追加 did** |
| Fields／Buildings／Buildable／Changes | did | 依 did 取代 | snapshot_repo | ✗ 待回填＋did 欄 |
| Oases | 中心座標 | 依中心取代（不再整份清空） | oasis_repo | ✗ 待回填；新增 `center_x`、`center_y` |
| Market（新） | did | 依 did 取代 | market_repo | ts_utc、did、merchants_free、merchants_total、capacity_each、incoming_json、outgoing_json（緊湊 JSON list[Transit]） |
| Transit（新） | plan_id | 只追加；送出後回寫 result | market_repo | plan_id、ts_utc、from_did、to_did、wood、clay、iron、crop、merchants_needed、arrive_utc、mode、result（sent／dry／failed／skipped）、detail str≤300 |
| goals／build_order／advice／log | — | Apps Script（Gemini）寫 | Apps Script | Python 只讀 `build_order`（plan_repo），先過 plan_validate；格式單村 A4b／多村 B6 回填 |

### 6.4 Config 鍵

每鍵必須登記在 `config_schema.DEFAULTS`（型別、預設、允許值）；未登記鍵只警告；型別錯誤改用預設並回報，寫入類 mode 一律視為 off。既有鍵已由 A1b 讀 `_default_cfg` 補齊（v0.29，見下表；舊鍵對照見 `config_schema.LEGACY_KEY_MAP`）。讀入規則：值可為儲存格字串或已型別化的值，空白＝用預設（必填鍵缺值＝錯誤）；`tribe` 接受已登記別名；布林只認 TRUE／FALSE／true／false／1／0；`enabled` 看不懂＝視為 FALSE（緊急停止）；嚴重度 error＝不能安全使用、warn＝已用預設或已忽略。

| 鍵 | 型別／預設 | 範圍 | 說明 |
|---|---|---|---|
| `tribe` | str／gaul | 帳號 | `TRIBES` 的鍵；現固定 gaul |
| `server_id`、`server_base_url`、`server_tz`、`server_start_utc` | 必填 | 帳號 | C11 |
| `server_speed`／1、`server_map_half`／200（△）、`server_protection_days`／空 | int | 帳號 | C11 |
| `server_locale` | str／`zh-TW` | 帳號 | C11 |
| `main_did`、`main_did_set_utc` | 空（village_lock 第一次記錄） | 帳號 | C8 |
| `hide_mode`、`guard_mode`、`fill_mode` | off／dry／live，預設 off | 帳號＋村 | 新鍵名維持 `guard_mode`、`fill_mode`。`runner.py` 實際的舊鍵是 `hero_guard_mode`、`fill_in_mode`（✓ v0.24 更正，原「沿用現有鍵名」作廢），由 config_repo 在邊界對應舊鍵（若測試舊服需要），或以新 Sheet 重填；舊 `fill_in_mode` 的 `on`→`live`（新-7）；`hide_mode` 舊值 `observe` 不再合法（視為 off 並回報，舊預設 observe 改為 off，v0.29） |
| `guard_exposure` | str／always、incoming，預設 incoming ✗ | 帳號＋村 | 承接舊 `hero_guard_mode` 的 incoming／always 語意（新-8） |
| `transfer_mode`△、`oasis_mode`△、`hero_mode`△、`market_mode`、`troop_mode` | off／dry／live，預設 off | 帳號 | 鍵名 △ A6a2 確認；舊 `hero_adventure`（TRUE→live）、`hero_transfer_mode` 由 config_repo 在邊界對應（v0.29：舊 incoming_only／always 的區分暫無對應鍵，A6a2 需要時再開 `transfer_exposure`） |
| `focus_mode`△ | enum off／auto，預設 off | 帳號 | 舊 `hero_focus_mode` 值為 auto／off；新值域待 A6a2 定案，不直接套用 off／dry／live；`merge_settings` 目前固定當 off |
| `market_max_per_ship` | int≥0／0（不限） | 帳號 | C7 |
| `market_min_ship` | int≥0／200 ✗ | 帳號 | 太小不送 |
| `market_reserve_hours` | float≥0／2.0 ✗ | 帳號 | 捐方至少保留幾小時產量 |
| `market_target_fill_pct` | int 0..100／80 ✗ | 帳號 | 受方補到容量幾 % |
| `market_max_ships_per_run` | int≥1／3 ✗ | 帳號 | |
| `schema_version` | int≥1／1 | 帳號 | Config 格式版本 |
| `enabled` | bool／TRUE | 帳號 | FALSE＝緊急停止；填錯一律視為 FALSE（舊版看不懂＝啟用，已改） |
| `target_level`、`queue_slots`、`is_capital` | int≥1／10；int 1..3／空＝依種族預設（單條 1、羅馬 2；Plus 的 +1 由 stage 處理）；bool／FALSE | 帳號＋村 | 單村模式以 Config 為準（頁面目前讀不出首都）；非首都 `target_level` 超過資源田上限 10 ＝ error（`level_over_cap`）；舊 `is_capital` 空白會變 TRUE（疑似 bug），新版空白＝FALSE |
| `max_builds`、`target_building_level`、`build_order` | int≥0／2；int≥0／0；str／空 | 帳號 | `target_building_level` 與 `build_order` 的格式、舊流程去留 A4b 定案 |
| `hero_min_health`、`hero_hard_min_health`、`hero_allowed`、`hero_skip_on_incoming`、`hero_focus_min_hours`、`hero_guard_hidden` | int 0..100／45；int 0..100／60；集合 normal、hard／normal；bool／TRUE；float≥0／1.0；int≥0／2000 | 帳號 | 沿用舊鍵，A6a2 一併檢討 |
| `hero_transfer_min`、`hero_transfer_max_gap`、`hero_transfer_eta_min` | int≥0／20000、1000、45 | 帳號 | 沿用舊鍵，A6a2 |
| `fill_in_slack_min`、`hide_min_attack`、`hide_wait_max_s` | int≥0／0、20、180 | 帳號 | 沿用舊鍵 |
| 舊鍵（不再登記） | — | — | `hero_adventure`→`hero_mode`；`hero_transfer_mode`→`transfer_mode`；`hero_focus_mode`→`focus_mode`；`hero_guard_mode`→`guard_mode`＋`guard_exposure`；`fill_in_mode`→`fill_mode`；`map_size`→`server_map_half`（(邊長−1)÷2）；`village_id`→`main_did`；`home_x`、`home_y` 不再使用（座標改由 VillageRef）；環境變數 `QUIET_UTC` 不保留（v0.29）。讀到舊鍵只警告（`LEGACY_KEY_MAP`） |

草案預設標 ✗ 者在 C2 之前定案。

### 6.5 非 Sheet 檔案格式

| 檔案 | 格式與規則 |
|---|---|
| session 快取 | ✗ 路徑檔名待 A4a 回填。JSON：`schema_version`、`saved_utc`、`server_id`、`cookies`（list，每項 name／value／domain／path／expires）。**含憑證：不入 git、log、artifact**；讀入時 `server_id` 不等於目前 `ServerProfile.server_id` 整份丟棄（新伺服器不誤用舊 Cookie）；只有 `infra/session` 讀寫 |
| 頁面樣本 | `tests/samples/{sid}_{kind}_{YYYYMMDD}.html／.json`，每個配同名 `.meta.json`：`schema_version`、`sample_id`、`kind`、`path_only`（URL 路徑，不含主機與查詢）、`captured_utc`、`server_id`、`did`（int 或 null）、`scrubbed`（true）、`scrub_tool`、`note`。沒 meta 或 `scrubbed≠true` 不得入 repo |
| golden 檔 | `tests/golden/{layer}/{module}/{case}.expected.json`（`dumps_stable`）；更新要在交接區塊說明原因 |
| log | stdout 單行 `{ts_utc} {LEVEL} {stage} {did或-} {msg}`；LEVEL＝INFO／WARN／ERROR；msg 已 redact；例外堆疊寫入 `Actions.detail` 前 300 字 |
| CLI 工具 | `--json` 時 `dumps_stable`；exit 0＝成功、1＝檢查失敗、2＝用法或輸入錯誤 |
| 交接區塊、決策列 | 表格；每欄必填，沒內容寫「無」 |

### 6.6 驗證機制

邊界驗證：parsers 回傳前驗證；`*_repo` 寫入前驗證、讀出後驗證；gateway 不驗內容。契約測試（A1a 起）：合規範例通過、不合規範例被擋且指到正確欄位、`from_row(to_row(x)) == x`、Sheet 輸出與 golden 一致。舊程式或舊 Sheet 的舊格式只在邊界（`*_repo` 或 parsers）轉換，不帶進 domain／actions／app。

### 6.7 格式缺口（回填前不得改該項）

| 項目 | 缺什麼 | 回填 |
|---|---|---|
| Actions 舊 9 欄 | ✓ 已回填（v0.24，取自 `runner.py` v2.36）：欄＝時間、動作、aid、gid、level、cost、mode、result、detail。時間 `YYYY-MM-DD HH:MM:SS`（UTC，無 T／Z）；cost 用 `/` 分隔；mode 為 DRY／LIVE；result 為中文；空值寫空字串 | A4b 才改格式 |
| 舊動作名稱與 result 值 | ✓ 已回填。動作：升級、轉移、加成、防搶加成、插隊、冒險；建城決策標籤：等待資源、等待佇列、倉容不足、計畫卡住、無空地、已完成。result：未升級、未送出、成功、沒看到變化、找不到按鈕、採用、不動、讀取失敗、失敗、例外、未出發 | A4b 才改格式；新契約 result 改 ok／dry／skipped／failed／deferred，中文只留在 detail |
| Sheet1 24 欄 | 欄名、型別、格式 | A4b 讀 `append_row` |
| state 分頁 | ✓ 已回填：`(key, 值, 說明)` 三欄；鍵：tribe、plus_active、cp_have、cp_need、cp_gap、cp_eta_days、cp_per_day、village_slots_used、village_slots_max、queue_slots、cap_wood／clay／iron／crop；讀不到的欄位不列；覆蓋式寫入 | A4b 才改格式 |
| Fields／Buildings／Buildable／Changes | 版面與欄位 | A4b 讀 `write_state`、`village_log.py` |
| Oases | 欄位與中心欄 | A4b 讀 `oasis_store` |
| Config 既有鍵 | 完整清單、型別、預設、允許值 | A1b 讀 `_default_cfg` |
| session 快取檔 | 檔名 ✓ `travian_state.json`（repo 根目錄；Actions cache key 前綴 `travian-state-`，v0.22 取自 yml）；內容欄位 ✗ | A4a 讀 `travian_ci_run` |
| 邊界轉換原則（v0.24） | 以上舊格式只在 `*_repo` 或 parsers 轉換，不帶進 domain／actions／app（§6.6） | — |
| build_order 格式 | 方案名稱或內容、Apps Script／Gemini 如何產生、每步欄位（順序號、建築、等級） | A4b（單村）、B6（多村、角色感知） |
| Apps Script 讀寫的分頁與欄位 | 依賴哪些分頁、欄位 | A4c（單村）、B6（多村） |

---

## 7. 工作包（WP）

**ID**：A 遷移（行為不變）｜B 多村｜C 市場｜D 運兵｜E 收尾｜SAMP 樣本。每個 WP 一次對話完成；先對每個模組做 §5.1 判定。規模：S＝≤150 行＋測試、M＝≤400 行＋測試、L＝要再拆；「（補）」＝該卡片在更早 WP 已建立、這個 WP 補完一部分。舊 WP 編號對照：WP-00→A0｜WP-01a→取消｜WP-01→SAMP｜WP-02、03→B1｜WP-04→B2｜WP-05、06→B3｜WP-07→B4｜WP-08→B5｜WP-09→B6｜WP-10～13→C1～C4｜WP-14、15→D1、D2｜WP-16、17→E1、E2。

### Phase A（單村，G0 就可做）

| WP | 內容 | 交付模組 | 要上傳的現有程式 | 處置 | 規模 | 依賴 |
|---|---|---|---|---|---|---|
| **A0**（v0.17 拆成 A0a 開服前／A0b 開服後，見 §9） | 新伺服器開局準備，逐項清單見 **§11.6-D**：①取得 `ServerProfile` 各值（§11.6-A）並填進新 Config ②依 §6.3 用模板建新 Sheet、分享給 bot 的服務帳號 ③新 Secrets（與舊 workflow 的 Secrets 分開，D-17）④新 Cookie 建新 session（不沿用舊檔）⑤手動抓頁面樣本（S3、S6、S8、S9；`scrub_sample.py` 脫敏後放 `tests/samples/`），記錄與舊伺服器頁面的差異；**不在新伺服器跑舊程式、不啟用排程**⑥（v0.17 取消：不重跑欠債測試，見 A-6） | — | 脫敏樣本＋測試結果＋新 Sheet Config 初值（貼文字） | — | S | 你 |
| **A1a-1** | 骨架與格式基礎：建各層目錄與 `__init__`；`serialize`、`schema`（`CONTRACT_SPECS` 依 §6.1／§6.2 涵蓋 C1～C12，含 `contract_examples`）、`constants`（拆分後）、`modes`；**先驗證 Actions 上的 import 方式（D-10）**：在分支手動跑 workflow，只執行 `python -c "import travian_bot…"`，不碰 main。四個模組互不依賴 | cm-03、04、10、11 | `auto_build.yml`（main 現況版）、`requirements.txt`、`travian_const.py` | 新寫＋沿用常數 | M | A0 |
| **A1a-2** | 資料結構與時間：`models`（C1～C12 dataclass、`validate`、`to_row`／`from_row`）、`parsed`（草案）、`decisions`（草案）、`server_profile`；§6.2 範例轉測試（含 `from_row(to_row(x)) == x`） | cm-01、02、09、13 | `travian_models.py` | 新寫（`Field`／`State`／`Slot` 的邊界轉換見 cm-09 舊源欄） | M | A1a-1 |
| **A1a-3** | 檢查工具：`arch_manifest`（與 §4.2 同源，73 張）、`check_arch`、`check_contracts`；`tests/contracts/` 範例檔；對 A1a-1／2 全部檔案跑檢查並修到通過 | —（`tools/`、`tests/contracts/`） | repo 目錄清單 | 新寫 | M | A1a-2 |
| **A1b** | common 純函式搬入與規則表：`clock`、`tribe_data`（加 TribeSpec）、`geo`（加 map_half）、`config_schema`（單村 merge_settings、profile_from_cfg）、`game_rules`（△） | cm-05、06、07、08、12 | `dispatch.py`、`runner.py`（`_now`；`in_quiet_hours` 不保留）、`sheets_writer.py`（`_default_cfg` 等）、相關測試、官方指南（種族、文化點） | 沿用（純搬） | M | A1a |
| **A2a-1** | parsers（player、village_list）；定案 PlayerInfo | ps-02、04 | `travian_pages.py` 的 `parse_player_info`、`parse_active_village`、`resolve_home`、相關測試；樣本 dorf1、S1 | 沿用（純搬）＋新寫 `parse_village_list` | S | A1a |
| **A2a-2** | parsers（village、buildings）；定案 Dorf1／Dorf2／BuildOption／PageFacts | ps-01、03 | `travian_pages.py` 的 `parse_dorf1`、`parse_movements`、`parse_dorf2`、`parse_dorf2_slots`、`parse_building_cost`、`parse_build_options`、`find_upgrade_url`、相關測試；樣本 dorf1、dorf2、S10、S11 | 沿用＋修改（見 §10 v0.31～v0.33） | M | A1a、A2a-1（共用 `parsed.py`，須先做 A2a-1） |
| **A2b** | parsers（英雄／集結點／綠洲）；定案 HeroState／Adventure／RallyOverview／Oasis／TileSafety | ps-05、06、08、09 | `travian_hero.py`、`hide_troops.py`、`oasis_scan.py`、`oasis_check.py` | 讀碼後判定 | M | A1a |
| **A3a** | domain（建城與守衛）：`build_planner`、`fill_in`、`guard`、`plan_validate`；建立 `tests/test_tribe_switch.py` | dm-01、02、03、12 | `travian_agent.py`、`stock_guard.py`、`fill_in.py`、`runner.py`（`_next_target`） | build_planner 改寫，其餘讀碼後判定 | M | A1a、A1b |
| **A3b** | domain（英雄相關）：`focus`、`item_transfer`、`adventure` | dm-04、05、06 | `hero_focus.py`、`travian_transfer.py`、`travian_hero.py` | 讀碼後判定 | M | A1a |
| **A3c** | domain（躲兵與鎖定）：`hide_plan`（全域→HideContext）、`hide_decide`、`village_lock`；`tools/dispatch_cli` | dm-07、08、09、`dispatch_cli.py` | `dispatch.py`、`hide_troops.py` | hide_plan 改寫、village_lock 新寫 | M | A1b |
| **A4a** | infra 連線層：`session`、`gateway`（先不加 did）、`notify`、`store/gsheets` | if-01、02、03、04 | `travian_ci_run.py`、`notify.py`、`sheets_writer.py`（連線部分） | 沿用／拆 | M | A1a |
| **A4b** | infra 各分頁 repo（以舊函式為參考、輸出 §6.3 嚴格格式，不再 1:1 包住；D-20）：`config_repo`、`action_repo`、`state_repo`、`snapshot_repo`、`oasis_repo`；唯讀 `village_repo.load_villages`；唯讀 `plan_repo.load_build_order`（回填 build_order 輸入格式）；定案 state、Sheet1、Fields／Buildings／Buildable／Changes、Oases 的新欄位清單並升契約；開始時重估是否拆成兩次 | if-05、06、07、08、09、10、12 | `sheets_writer.py`、`village_log.py`、`oasis_store.py`（save／load）、現有 `build_order` 分頁內容（脫敏）與 Apps Script 產生它的程式 | 改寫 | M→L | A4a、A1b |
| **A4c** | Apps Script 單村新格式（D-20）：產生 `build_order`（A4b 定案的格式）；Apps Script 讀的其餘分頁（state、Sheet1、Fields…）改讀新格式；不動多村邏輯；**GA 前必須完成** | —（`appsscript/`） | Apps Script 五檔、`triggerTravian` 所在檔、`travian_rules.md`、現有 `build_order` 分頁內容（脫敏） | 改寫 | M | A4b |
| **A5a** | actions（建城、英雄）：`build_exec`、`item_transfer_exec`、`focus_exec`、`hero_exec` | ac-02、03、04、05 | `runner.py`（送出升級段）、`transfer_io.py`、`hero_focus.py`（`make_focus_io`）、`travian_ci_run.py`（`click_adventure`） | 沿用／拆 | M | A2a、A2b、A4a |
| **A5b** | actions（躲兵、綠洲、切村）：`hide_exec`、`oasis_exec`、`village_switch`（單村無操作） | ac-01、06、07 | `hide_troops.py`（`run_once`）、`oasis_store.py`（`fetch_block`／`scan`）、`oasis_check.py` | 拆 | M | A2a、A2b、A4a |
| **A6a1** | app 基礎：`run_context`、`stage_base`、`registry`、`observe`、`formatting` | ap-02、03、04、05、06 | `runner.py`（`log_*`、`build_state_rows`、`_setup_player`、`cp_summary`）、`travian_pages.py`（`fetch_build_options`） | 拆 | M | A4b、A2a |
| **A6a2** | app stages（建議分兩批：先 build／fill_in／guard／item_transfer／focus，再 hide／oasis／hero） | ap-10～17 | `runner.py`（`_try_*`、`run_build_cycle`、`run_hero_cycle`）、`hide_observe.py`、`oasis_store.py`（`apply`／`refresh`） | 拆／改寫 | L→拆 | A3a～A3c、A5a、A5b、A6a1 |
| **A6b** | app 入口：`village_cycle`、`orchestrator`（單村版）、`main`；yml 只指新入口（`DRY_RUN` 預設 `"1"`，A-8），舊入口歸檔 | ap-01、07、08 | `auto_build.yml`、`travian_ci_run.py` | 拆 | M | A6a2 |

> **A1a 拆分的依賴說明（v0.23）**：其他 WP 的依賴欄寫的「A1a」＝A1a-1～A1a-3 全部完成。實際開工條件較寬：A2a／A3a 等只需 `models`／`parsed`，**A1a-2 完成即可開始**；A1b 的 `config_schema` 需 `server_profile`，也是 A1a-2；A1a-3 通過（`check_arch`、`check_contracts` 全綠）才算 A1a 關閉。

> **A2a 拆分的依賴說明（v0.35）**：其他 WP 的依賴欄寫的「A2a」＝A2a-1、A2a-2 都完成。A2a-2 與 A2a-1 都會改 `common/parsed.py`，須依序做（A2a-1 → A2a-2），不可同時在不同對話做。

**關卡 GA（新程式 live 的唯一關卡）**：單村 dry 一天，Actions 列與 Sheet 寫入符合 §6 契約與 §6.3；耗時與請求數有記錄；`village_lock` 已接入 `village_cycle`；`build_order` 驗證已接入 build stage，用一份刻意壞掉的 `build_order` 實測會 hold 且沒有任何寫入；啟動檢查（D-18）已接入 `main`，用一份故意與頁面不符的 Config（錯的 `tribe` 或 `server_tz`）實測會 hold 且沒有任何寫入；`check_arch` 與 `check_contracts` 通過；A4c 完成（Apps Script 產生與讀取的都是新格式）；（無舊版可比，以契約測試、`tests/golden`、種族煙霧測試驗收）。**全過才開 live，從第 0 天資料起算**；live 後第一天逐輪檢查 Actions 列，有寫入失敗或契約驗證失敗就把相關 stage 調回 dry／off。

> **可並行**：A2a、A2b、A3a、A3b、A4a 只依賴 A1，可同時在不同對話做；A3c 需 A1b；A4b 需 A4a；A5 需 A2＋A4a；A6 需前面全部。

### SAMP（不寫程式）

抓樣本（§11.2）並脫敏。**G0 可抓**：S3 市場頁、S6 集結點頁（第 1 村）。**等第 2 村（G2）**：S1、S2、S4、S5、S7。

### Phase B～E

| WP | 內容 | 交付模組 | 依賴 |
|---|---|---|---|
| **B1** | `village_list` 清單、`gateway` 加 did＋newdid、`village_switch` 實際切村＋`assert_active`（依樣本 S1／S2，重新規劃風險較高） | ps-02、if-02、ac-01（補） | GA、SAMP |
| **B2** | Sheet 多村：`village_repo` 完整版、`action_repo` 第 10 欄、`state_repo` 每村、`snapshot_repo` 加 did、`oasis_repo` 多中心、`merge_settings` 多村列 | cm-08、if-06～10（補） | GA |
| **B3** | `orchestrator` 逐村＋優先序＋時間預算＋錯誤隔離；VillageContext 逐村；`is_capital`／`build_order` 逐村；角色模板；**動態跳過（v0.20）**：只在「`queue_free_in_s`>0 且資源不足 且 `next_target` 為資源田（不需 dorf2 前置）」時省略 dorf2；next_target 是建築時照抓（`plan_validate` 的 `prereq_unmet` 需要 dorf2）；優先序以來襲為先，但 B8（來襲數帳號級或村級）未用 S7 驗證前，不以來襲數排序，退回「最久沒處理」（L→拆） | ap-08（補） | B1、B2 |
| **B4** | 逐村躲兵與綠洲（HideContext 每村）；查證來襲數是帳號級或村級 | — | B3 |
| **B5** | 逐村守衛與加成；英雄與道具庫轉移限定英雄村 | — | B3 |
| **B6** | Apps Script 多村：每村一份 `build_order`、角色感知、白名單補 36；規則檔換高盧章節與多村分工（單村版 build_order 讀取與驗證已在 A3a／A4b 完成、Apps Script 單村新格式已在 A4c 完成）；要傳 Apps Script 五檔＋規則檔 | — | B2 |
| **C1** | 解析市場頁、快照加 merchants、寫 `Market` 分頁；**只讀**（樣本 S3／S4／S5） | ps-07、if-11 | GB |
| **C2** | `market_plan` 純函式＋離線測試（商人不足、受方倉滿、捐方不夠、在途重複計算；政策 D-4） | dm-10 | C1、D-4 |
| **C3** | `market_exec`：送出與驗證、不可逆原則、`Transit` 防重送（樣本 S5） | ac-08 | C2 |
| **C4** | 掛成帳號級 stage；`market_mode=dry` 先跑 3 天 | ap-18 | C3 |
| **D1** | 集結點在家／在外兵力解析、快照加 `units_*`；只讀（S6） | ps-06（補） | GB |
| **D2** | `troop_plan`＋`troop_exec`＋stage；確認頁核對後才按確認（D-3 定案後；L→拆） | dm-11、ac-09、ap-19 | D1、D-3 |
| **E1** | 主動通知（來襲、停用、運送失敗）：擴充 `infra/notify` | — | GB |
| **E2** | README 重寫、主筆記 §2 檔案表更新 | — | 全部 |

**關卡 GB**：兩個村 dry 一天，耗時與請求數有記錄、單村輸出仍與 GA 一致。

**順序**：`A0 → A1a-1 → A1a-2 → A1a-3 → A1b → ［A2a／A2b／A3a／A3b／A4a 任意或並行］→ A3c → A4b →（A4c 與 A5a／A5b 可並行）→ A6a1 → A6a2 → A6b →［GA］→（第 2 村出現後）SAMP → B1／B2 → B3 → B4／B5／B6 →［GB］→ C1 → C2 → C3 → C4 → D1 → D2 → E1／E2`

---

## 8. 跨 AI 延續機制

**檔案分工**（同一 repo 的 `docs/`）：`project-notes-vX.md`（單村現況、事實、決策，有新結論才更新）｜`multi-village-dev-vX.md`（本檔，每個 WP 結束更新）｜`samples/`（脫敏樣本，檔名帶日期與用途）。舊 `architecture-v0_1.md`、`multi-village-plan-v0_4.md` 移 `docs/old/`，不要再附。

### 8.1 開新對話的標準開場（貼給 AI）

> 這是 Travian 自動化專案（Python＋Playwright＋Google Sheet）。我只要你做**工作包 WP-XX**。
> 附件：`multi-village-dev`（先讀 §0、§1、§4.1、§4.2 中該 WP 要交付的卡片與其依賴的卡片、§5.1、§6、該 WP 在 §7 的那一列與 §9 的前置交接）＋以下檔案：〔列出該 WP「要上傳的現有程式」欄〕。
> 規則：先對每張卡片做 §5.1 的「套用／重新規劃」判定並回報，等我同意才寫；新功能放新檔、舊檔唯讀（不改、不掛鉤、不留 shim）；寫入動作要有 dry／live；不要重印整份大檔；完成後跑 `tools/check_arch.py` 並輸出交接區塊。

### 8.2 交接區塊範本（每個 WP 結束由 AI 產出，貼進 §9）

| 欄位 | 內容 |
|---|---|
| WP／日期／版本 | |
| 做了什麼（≤5 行） | |
| 每張卡片的結果 | 卡片 ID：套用／重新規劃（原因、新卡片內容） |
| 架構卡片變動 | 檔名、公開函式、依賴改動及受影響的卡片與 WP（沒有寫「無」） |
| 新增或修改的檔案與版本 | |
| 介面／契約變動 | 欄位與新版本 |
| 格式變動 | 欄位、型別、單位、範例（§6） |
| 測試 | 跑了什麼、結果、**沒跑的** |
| 部署注意 | 同一 commit 的檔案、Config 新鍵與預設 |
| 證據標記 | 哪些 ✓、哪些仍 ✗ |
| 留給下個 WP 的問題 | |

### 8.3 節省額度

1. 每次只上傳該 WP「要上傳的現有程式」；不附整份主筆記。
2. 要 AI **給新檔**（舊的 `runner.py`／`sheets_writer.py` 唯讀，不整份重印）。
3. 樣本與 log 先自己裁掉無關部分（Cookie、無關 HTML）。
4. 一個 WP 一個對話，做完貼交接區塊，**不在同一對話延伸下一個 WP**。
5. 兩輪內沒收斂就寫成 §10 待決事項，換下一個 WP。

### 8.4 切片（v0.23）

**主檔是唯一真相來源，所有更新只寫主檔；不拆成多個手動維護的檔（避免版本漂移）。** 每個 WP 開始前執行 `python tools/make_slice.py <主檔> <WP>`，產生該 WP 的切片貼給 AI：內容為標頭與 §0、§1、§4.1、§4.2 說明、該 WP 交付的卡片與其**直接依賴**的卡片（含 `tools/`、`tests/` 列）、§5.1、§6（`--no-contracts` 可略）、該 WP 在 §7 的那一列與表頭、§9 狀態表與最近 3 筆交接、**最新 WP 的交接區塊與後續事項（v0.28，整段）＋舊 WP「留給後續 WP 的事項」中點名本 WP 的列（自動篩選，不用手動刪；範圍如 `A3a～A3c` 也會對上）**、§10 待決與風險（`--decisions` 才附已定決策，`--extra cm-05,…` 可多附卡片）。切片不手改、不保存。WP 結束後：交接區塊貼回主檔 §9；卡片、契約或決策有變動時，在附主檔的對話升版。§9 交接紀錄太長時，舊紀錄移 `docs/old/`。**寫法約定（v0.28）**：交接區塊標題用 `**<WP> 交接區塊（§8.2 格式）**`、後續事項標題用 `**<WP> 留給後續 WP 的事項**`，表格最後一欄（或清單文字）要寫出目標 WP 名稱，切片才篩得到。

---

## 9. WP 狀態與交接紀錄

| WP | 狀態 | 備註 |
|---|---|---|
| A0a | ⬜ 未開始（可先做） | 開服前：①（原「重跑欠債測試」已取消，見 A-6）②建新 Sheet 骨架（Config、Villages、Actions 10 欄、Market、Transit 等，欄位依 §6.3；`server_*` 先留空）③決定 Secrets 名稱草案（正式名稱仍待 A4a 回填，D-17）。不需要新伺服器 |
| A0b | ⏸ 等新伺服器開服 | 開服後：登入選高盧、記主機、確認 `zh-TW`；S8、S9、S3、S6 樣本；開服時間與保護天數；新 Cookie 與 Secrets 設定；填 Config 初值。依賴新服，開服前不能做（不跑舊程式） |
| A4c | ⬜ 未開始 | D-20：Apps Script 單村改新格式（GA 前必須完成） |
| B0 | ✂ 已取消（v0.9） | `village_lock` 併入 A3c／A6b，GA 必備 |
| A1a-1 | ✅ 完成（2026-10-27） | cm-03、04、10、11；77 個 unittest 全過；D-10 在 Actions 實跑通過；cm-04 已與舊 `runner.py` 的 `_guard_mode`、`_fill_mode` 離線比對（`tests/common/test_modes_golden.py`）。待補：gid 29、30、44、48 名稱待樣本核對 |
| A1a-2 | ✅ 完成（2026-10-27） | cm-01、02、09、13；四個新檔皆 v0.1，契約仍 C-v0.5；新增 78 個測試；Actions（Python 3.11）全部 155 個 OK。cm-02、cm-09 為草案（✗），分別由 A3a～A3c、A2a-1／A2a-2／A2b 定案 |
| A1a-3 | ✅ 完成（2026-10-28） | `tools/{arch_manifest,check_arch,check_contracts,make_manifest}.py` 皆 v0.1；`tests/contracts/` 40 個範例檔（20 契約×valid／invalid）；新增 51 個測試（`tests/tools/`）；Actions（Python 3.11）全部 206 個 OK（含測試靜音與 make_manifest 的 10 個測試，已實跑確認）；`check_arch --expect-wp A1a-1,A1a-2 --strict` 與 `check_contracts` 對 A1a-1／2 全部 8 個檔案一次通過，**主檔案無修改**。已在分支測試 workflow 加這兩步並實跑通過。備註：A1a-3 沒有交付 `travian_bot/` 底下的模組卡片（73 張的 WP 欄沒有任何一張是 A1a-3） |
| A1b | ✅ 完成（2026-10-30） | cm-05、06、07、08、12；五個新檔皆 v0.1，契約仍 C-v0.5；新增 121 個測試（含舊 `dispatch.py` v1.8 離線輸出的 golden、官方文化點表逐格核對）；`check_arch --expect-wp A1a-1,A1a-2,A1b --strict` 本機對 13 個檔案通過（違規 0、警告 0）；Actions（Python 3.11）unittest 全部 328 個 OK、check_arch 通過（違規 0、警告 0、13 個檔案、73 張卡片）、check_contracts 通過（契約 20、範例 99） |
| A2a-1 | 🟡 程式已交付（2026-11-01）、待 Actions 驗收 | ps-02、ps-04；`parsers/{player,village_list}.py` v0.1、`parsed.py` v0.2（PlayerInfo 定案）；本機 36 個測試全過（Python 3.12.3）、對 15 處刻意改壞逐一確認會失敗、與舊 `travian_pages.py` 在兩份樣本與三種破壞情況下輸出一致；`check_arch --strict` 只用「只含已有檔案」的迷你 manifest 跑過（0 違規）。**沒跑**：完整 repo 的 unittest／`check_arch`／`check_contracts`、Python 3.11。見 A2a-1 交接區塊 |
| A2a-2 | ⬜ 未開始（A2a-1 之後） | ps-01、ps-03；定案 `Dorf1`／`Dorf2`／`PageFacts`／`BuildOption`；前置：dorf1、dorf2、S10、S11 原始樣本（見 §10 v0.31～v0.34） |
| A2b～A6b、SAMP、B1～B6、C1～C4、D1、D2、E1、E2 | ⬜ 未開始 | 架構卡片已定（§4.2） |

**交接紀錄（只追加；已精簡）**
- 2026-10-25｜v0.7：架構先行，§4.2 卡片、§5.1 判定、分層改 common／parsers／domain／infra／actions／app，WP 重排為 A1a～A6b。
- 2026-10-26｜v0.8：全新伺服器、種族固定高盧（`TribeSpec`＋煙霧測試）、§6 嚴格格式協定（新增 serialize／schema／server_profile／game_rules／check_contracts）。
- 2026-10-26｜v0.9：新程式直接開局（無舊程式上線、無 shim、無回退）；D-14 定案、D-9 作廢；取消 B0。
- 2026-10-26｜v0.10：Gemini 邊界——新增 dm-12／if-12／C12、ap-10 hold 行為；模組共 73。
- 2026-10-26｜**v0.11：僅精簡文件。§4.2 卡片由 `tools/compress_cards.py` 自 v0.10 轉換（依賴改卡片 ID、去測試欄、逐字保留內容規劃與舊源處置）；其餘章節手寫精簡（移除版本沿革敘述、範例 JSON、重複說明）；設計無變更。**
- 2026-10-26｜**v0.12：新增 §11.6（新伺服器要更新的資訊與安裝設定）；依舊伺服器 Asia 8 的 dorf1 頁面解析出 `ServerProfile` 各欄來源、頁面可直接讀的資料源、舊伺服器專屬不得沿用的項目；契約 C-v0.5（C11 加 `locale`、`server_tz` 語意定義）；新增決策 v0.12、待決 D-17／D-18／D-19；新增樣本 S8／S9。無程式變動。**
- 2026-10-26｜**v0.13：記下舊伺服器主機 `ts8.x1.asia.travian.com` 與 lobby 伺服器 UUID；實測未登入 dorf1 只回登入頁（英文、無遊戲資料、無 `Travian.Game` 區塊）→ S8（公開 JS）可由 AI 協助抓，S9（dorf1）必須由你登入後貼；新增決策 v0.13。無程式變動。**
- 2026-10-26｜**v0.14：D-15＝嚴格格式、D-17＝Secrets／Config 分界、D-19＝不買 Plus 定案；新增 D-20（A4b／B6 連帶範圍）。無程式變動。**
- 2026-10-26｜**v0.15：舊服 S8 解析（§11.6-F）；倍速、地圖大小、`wuid` 可由 S8 直接讀；新增 D-21；新增風險「單位編號兩套混用」。無程式變動。**
- 2026-10-26｜**v0.16：D-18、D-20 定案並落到卡片（cm-09、cm-13、ps-01、ap-01）與 WP（新增 A4c；A4b 改寫、M→L；B6 只剩多村）；GA 加兩項實測；D-21 仍待同意。無程式變動。**
- 2026-10-26｜**v0.17：僅進度管理。A0 拆成 A0a（開服前可做）與 A0b（等開服）；你決定先做後面的 WP、新服開服後再給設定檔開始玩；補上「欠債測試」定義（A-6）與開服當天要提供的清單（§0）。A1a 只需 D-10、不需新服的值，可在等開服期間推進。另定案 A-6：舊功能全部靠直接跑驗證，舊測試不可信，取消重跑欠債測試與逐項對照；golden 以脫敏樣本＋你確認的舊函式輸出為準，各 WP 搬入模組時新寫測試。無程式變動、契約不變。**
- 2026-10-26｜**v0.18：依你貼的 `auto_build.yml` 與 `triggerTravian` 記錄 D-10 現況與建議（套件放根目錄、`python -m` 執行，待確認）；新增 A-7（Apps Script 觸發器與 Secrets 衝突）、A-8（`DRY_RUN` 預設 `"0"`、`QUIET_UTC`、`TRAVIAN_BASE_URL`、cache key）；A0b 設 Secrets 前先關觸發器；A6b 的 yml 預設 `DRY_RUN: "1"`。A1a 仍缺：`requirements.txt`、repo 目錄清單、`travian_const.py`、`travian_models.py`。無程式變動、契約不變。**
- 2026-10-26｜**v0.19：D-10 定案（根目錄套件＋`python -m`）；A-7 修訂（觸發器維持開著、新服用新名稱 Secrets、A6b 合併＝切換點）；記錄 repo 清單、`requirements.txt`（無版本釘選）與 A1a 三檔已收到；A1a 的 §5.1 判定報告已提出，待你同意後才更新 §4.2 卡片與開始寫程式。無程式變動、契約不變。**
- 2026-10-26｜**v0.20：把審查後合理的三點寫入——D-1／D-8 提前、D-3／D-4 等樣本（§10 待決）；`village_cycle` 寫入前再核對 `assert_active`（ap-07、§4.4）；動態跳過規則與前提寫進 B3；新增 D-22。無程式變動、契約不變。**
- 2026-10-26｜**v0.23：A1a 拆成 A1a-1／2／3；新增 §8.4 切片機制；A1a 依賴說明；無程式變動、契約不變。**
- 2026-10-26｜**v0.22：依你回覆與三個檔案修正卡片舊源（cm-01／03／06／09／12）、A-8、D-22 測試方式、§6.7 session 快取檔名、check_arch 規則；repo 清單確認有 `travian_parser.py`、`travian_transfer.py`、`village_log.py`（A-3 的 △ 仍待各 WP 讀碼）。無程式變動、契約不變。**
- 2026-10-26｜**v0.21：D-22 定案——舊服可當新程式測試場（僅 dry／唯讀、不 live）；規則 12、§10 決策、新增風險 A-9 同步；§0 待定清單移除 D-22。無程式變動、契約不變。**
- 2026-10-27｜A1a-1 完成，`common/{constants,modes,serialize,schema}.py` 皆 v0.1，契約仍 C-v0.5；D-10 已驗證；補 cm-04 比對舊 `runner.py`，新增 Config 鍵 `guard_exposure`；更正 §6.4 的鍵名；§6.7 回填舊 Actions 與 state 格式。
- 2026-10-27｜A1a-2 完成：`common/{models,decisions,parsed,server_profile}.py` v0.1，契約不變。cm-01 含 C1～C12（含 C7 MarketConfig、C12 PlanVerdict）；ActionRow、VillageSettingsRow 有 `to_row`／`from_row`。資源用 tuple，`to_dict` 轉回 list。`ServerProfile.tribe` 必填，預設由 `config_schema` 提供。`BuildSettings.target_level` 維持必填，預設 10 由 Config 提供（已決定）。D-21 未動、`wuid` 未加。
- 2026-10-27｜依國際 11 的 dorf1 樣本回填（無程式變動）：穀物 `l4`＝淨產量、`l5`＝可用穀物（僅此樣本 ✓）；`queue_slots` 與 Plus 不一致、`notNow` 解讀有疑；新增待決 D-23（穀物赤字擋建築，C2 暫無 `free_crop`）。契約仍 C-v0.5。
- 2026-10-28｜A1a-3 完成：`tools/{arch_manifest,check_arch,check_contracts,make_manifest}.py` v0.1、`tests/contracts/` 40 個範例檔、`tests/tools/` 51 個測試；對 A1a-1／2 的 8 個檔案檢查一次通過，無主檔案變動，契約仍 C-v0.5。範例檔檔名用契約名（`VillageRef.valid.json`），不用 C1～C12 編號。

- 2026-10-30｜A1b 完成：`common/{clock,tribe_data,geo,config_schema,game_rules}.py` v0.1、新增 121 個測試與 6 個 golden；§4.2 卡片更新並重新轉出 `arch_manifest`；取消安靜時段、伺服器定為 1 倍速常規服；契約仍 C-v0.5。Actions（Python 3.11）全部 328 個 OK、check_arch 與 check_contracts 通過。
- 2026-10-31｜**v0.30：D-18 修正（見 §10 v0.30 列）。依舊服樣本（dorf1／dorf2 共五份、集結點概覽一份）確認 `karte.php?d=` 只在集結點概覽；執行期檢查拿掉該項，改查各村座標 ≤ `map_half`；cm-09 PageFacts 欄位、§11.2 S6 樣本要求、§11.6 `server_map_half` 列、A0b 步驟 8 同步。無程式變動、契約仍 C-v0.5。**
- 2026-10-31｜**v0.31：A2a 前置決定（見 §10 v0.31 列）。ps-01／03／04、cm-09 卡片依舊服樣本實跑結果更新；§11.2 新增 S10／S11；§9 待辦更新；`scrub_sample.py` v0.2。無程式變動、契約仍 C-v0.5。**
- 2026-10-31｜**v0.32：A2a 前置決定補充（見 §10 v0.32 列）。S10／S11 舊服頁面實跑結果入檔；§11.2 S10／S11 註明現有樣本與缺口；§9 待辦更新。無程式變動、契約仍 C-v0.5。**
- 2026-10-31｜**v0.33：修正 v0.31 ②：Plus 沿用舊設計（有開就用、沒開就不用，見 §10 v0.33 列）；ps-01、ps-04 卡片同步。無程式變動、契約仍 C-v0.5。**
- 2026-10-31｜**v0.34：主檔同步（§0／§7／§9／待決 D-28／風險 A-10，見 §10 v0.34 列）。無程式變動、契約仍 C-v0.5。**
- 2026-11-01｜**v0.35：A2a 拆成 A2a-1（ps-02、ps-04）與 A2a-2（ps-01、ps-03）（見 §10 v0.35 列）；§7、§4.2 WP 欄、§9、§0 同步；留給後續 WP 的事項改點名 A2a-2。無程式變動、契約仍 C-v0.5；`arch_manifest` 須重新轉出。**
- 2026-11-01｜**v0.36：A2a-1 程式交付（見 §10 v0.36 列）：`parsers/{player,village_list}.py`、`parsed.py` v0.2（PlayerInfo 定案）、樣本 S1a／S1b 與 golden；ps-02／ps-04 卡片更新（依賴加 cm-11）；`arch_manifest` 須重新轉出。契約仍 C-v0.5。**

**A2a-1 交接區塊（§8.2 格式）**

| 欄位 | 內容 |
|---|---|
| WP／日期／版本 | A2a-1／2026-11-01／`parsers/player.py`、`parsers/village_list.py` v0.1；`common/parsed.py` v0.1→v0.2；主檔 v0.36；契約仍 C-v0.5 |
| 做了什麼 | ①ps-04 `parse_player_info`→`PlayerInfo`②ps-02 `parse_active_village`／`resolve_home`（沿用，`map_size`→`map_half`，去掉 Config 備用）③ps-02 `parse_village_list` 新寫（`viewData.villageList`＋側欄交叉核對）④cm-09 `PlayerInfo` 定案⑤舊服 dorf1 兩份脫敏樣本（S1a／S1b）、2 個 golden、36 個測試 |
| 每張卡片的結果 | ps-04：套用（純搬＋小改：回 `PlayerInfo`、整段讀不到丟 `ParseError`、`tribe_id` 排除 bool；§5.1 五條成立，d 條以舊函式離線輸出對照）。ps-02：`parse_active_village`／`resolve_home` 套用（`map_half`、`resolve_home` 只回座標；舊 `cfg_home` 與說明字串搬到呼叫端）；`parse_village_list` 新寫 |
| 架構卡片變動 | ps-02 依賴 cm-01、cm-03→＋cm-11；ps-04 依賴 cm-09→＋cm-11（兩者都丟 `schema.ParseError`，`--strict` 否則 UNDECLARED_DEP）；ps-02 公開簽名＋`map_half`、`resolve_home` 回 `(x, y)｜None`；cm-09 `PlayerInfo` 定案。受影響：A5b（`hide_exec` 自己處理 Config 備用）、A2a-2、B1。§4.2 已更新；**`tools/arch_manifest.py` 須用 `make_manifest.py` 重新轉出並提交（本次沒有該工具，未轉）** |
| 新增或修改的檔案與版本 | 新增：`travian_bot/parsers/{player,village_list}.py`（v0.1）；`tests/parsers/{__init__,_util,test_player,test_village_list,test_viewdata_helpers}.py`；`tests/samples/S1a_dorf1_20261031.{html,meta.json}`、`S1b_dorf1_20261031.{html,meta.json}`；`tests/golden/parsers/player/dorf1.expected.json`、`tests/golden/parsers/village_list/dorf1.expected.json`。修改：`travian_bot/common/parsed.py`（v0.2，只動檔頭與 `PlayerInfo` 說明）、`tools/arch_manifest.py`（重新轉出）、分支測試 workflow（`--expect-wp` 加 A2a-1） |
| 介面／契約變動 | 無（C-v0.5 不變）。`PlayerInfo` 欄位不變，只定案 |
| 格式變動 | 無新的持久化格式。golden 頂層 `{schema_version:1, cases:[…]}`；樣本 `.meta.json` 加 `source` 欄（A-10 建議） |
| 測試 | 新增 36 個（本機 Python 3.12.3 全過）；對 15 處刻意改壞的程式碼逐一確認測試會失敗；新舊函式離線比對：兩份樣本的 `parse_player_info`、`parse_active_village`、`resolve_home` 與舊 `travian_pages.py` v2.38 輸出一致，另在「無側欄」「無 viewData」「座標被改」三種破壞下也一致。`check_arch --expect-wp A2a-1 --strict`：只用含已有檔案的迷你 manifest 跑，0 違規（對照：依賴欄不加 cm-11 會報 2 筆 UNDECLARED_DEP）。**沒跑**：完整 repo 的 unittest（既有 328 個）、完整 `check_arch`、`check_contracts`、Python 3.11（Actions）、真實的單村頁與 3 個以上村的頁面 |
| 部署注意 | 同一 commit：2 個模組＋`parsed.py`＋5 個測試檔＋2 個樣本 html＋2 個 meta＋2 個 golden＋`tools/arch_manifest.py`＋主檔 v0.36。`tests/` 與 `tests/parsers/` 要有 `__init__.py`（`discover -t .`）。`UPDATE_GOLDEN=1` 會改寫 golden，更新要在交接區塊說明原因。`beautifulsoup4` 已在 `requirements.txt`。不在 bot 執行路徑 |
| 證據標記 | ✓：`viewData.ownPlayer` 的 `tribeId`、`goldFeatures.travianPlus.isActive`、`culturalPointsOverview` 五欄、`village`、`villageList` 在 S1a／S1b 一致；側欄與 viewData 的村莊、座標、作用中的村一致；與舊函式輸出一致。△：樣本 `source=raw` 為特徵判斷（`viewBox` 大小寫、無 `data-value`）；Plus 只見過 true、`tribeId` 只見過 3。✗：`is_capital`（頁面沒有首都標記）、單村頁與 ≥3 村頁（單村以改寫樣本測邏輯）、新服頁面 |
| 留給下個 WP 的問題 | 見下 |

**A2a-1 留給後續 WP 的事項**

| 項目 | 留給 |
|---|---|
| `resolve_home` 不再有 Config 備用與說明字串：`hide_exec` 要自己處理（`home_x`／`home_y` 備用、頁面與 Config 不同時以頁面為準並記說明、都沒有則本輪不躲兵） | A5b |
| `village.py` 加 `viewData` 私有複本，並把它加進 `tests/parsers/test_viewdata_helpers.py` 的 `MODULES`；`ParseError` 的 page 名稱沿用檔名（`player`、`village_list`、之後 `village`） | A2a-2 |
| `parsed.py` 其餘結構（Dorf1／Dorf2／PageFacts／BuildOption）只動各自一段，`PlayerInfo` 不動 | A2a-2 |
| PageFacts 的各村座標可直接用 `viewData.ownPlayer.villageList`；`parse_village_list` 已讀並與側欄核對，可參考 | A2a-2、A2b |
| `is_capital` 頁面沒有標記，一律 None，以 Villages 分頁為準；其他頁面是否有首都標記待樣本 | B1 |
| 樣本缺口：單村頁、≥3 村頁；新服重抓 S1 並與舊服比對（A-9） | A0b／B1 |
| 樣本 meta：`server_id` 暫用頁面標題「Asia 8」（不是主機名稱）、`source=raw` 為特徵判斷；確認取得方式與主機名稱後修正 meta | 你（下次抓樣本）／SAMP |
| 驗收：先 `python tools/make_manifest.py <主檔>` 並提交 `tools/arch_manifest.py`，再跑 `python tools/check_arch.py --expect-wp A1a-1,A1a-2,A1b,A2a-1 --strict`、`python tools/check_contracts.py`、`python -m unittest discover -s tests -t .` | 驗收 A2a-1 |

**A1b 交接區塊（§8.2 格式）**

| 欄位 | 內容 |
|---|---|
| WP／日期／版本 | A1b／2026-10-30／五個新檔皆 v0.1；契約仍 C-v0.5 |
| 做了什麼 | ①cm-07 `geo`（`map_half`、持續時間）②cm-06 `tribe_data`（凍結的 TribeSpec，`u1`～`u10`）③cm-05 `clock`（`utc_now`、`secs_until`、`resolve_clock_time`；取消安靜時段）④cm-12 `game_rules`（官方文化點表、倍速係數、拓荒、保護天數）⑤cm-08 `config_schema`（46 個鍵登記、`normalize_cfg`、單村 `merge_settings`、`profile_from_cfg`） |
| 每張卡片的結果 | cm-07：`wrap_delta`／`distance`／`map_id` 套用（加 `map_half`）；`parse_time`／`fmt` 重新規劃（舊版是伺服器時刻與 `strftime`，改為持續時間，時刻語意搬 cm-05）。cm-06：資料套用、結構重新規劃（全域表→frozen TribeSpec；`tribe_from_state` 去掉 Sheet IO；鍵複數→單數；兵種鍵 `t`→`u`）。cm-05：`_now`／`parse_time` 語意以 `resolve_clock_time` 套用，`in_quiet_hours` 取消。cm-12：表格套用＋新寫。cm-08：重新規劃（依賴補列、舊鍵遷移、`merge_settings` 新寫） |
| 架構卡片變動 | cm-05：刪 `in_quiet_hours`，依賴 cm-13→cm-10＋cm-13。cm-06：依賴＋cm-11。cm-07：`parse_time`／`fmt`→`parse_duration`／`fmt_duration`。cm-08：依賴＋cm-06、cm-10、cm-12；公開項目＋`normalize_cfg`、`KEYS`、`LEGACY_KEY_MAP`、`REQUIRED_KEYS`、`MODE_KEYS`、`MODE_TO_CTX`。cm-12：＋`speed_rules`、`SpeedRules`（`field_production` 不提供）。ap-01：舊源註記「安靜時段 keep-alive」不保留（A6b 注意）。§4.2 已更新並重新轉出 `arch_manifest` |
| 新增或修改的檔案與版本 | 新增：`travian_bot/common/{clock,tribe_data,geo,config_schema,game_rules}.py`（v0.1）；`tests/common/test_{clock,tribe_data,geo,config_schema,game_rules}.py`；`tests/golden/common/clock/`（1）、`geo/`（3）、`tribe_data/`（2）共 6 個 JSON。修改：`tools/arch_manifest.py`（重新轉出）、分支測試 workflow（import 改自動掃描全部模組、`--expect-wp` 加 A1b） |
| 介面／契約變動 | 無（C-v0.5 不變）。`tribe_data` 內部先用 `u1`～`u10` 與 `global_unit_id`，D-21 仍待同意，不動契約 |
| 格式變動 | 無新的持久化格式。Config 鍵見 §6.4；golden 檔頂層 `{schema_version:1, …}` |
| 測試 | 新增 121 個（本機 Python 3.12 全過）；另對 14 處刻意改壞的程式碼逐一確認測試會失敗。golden：舊 `dispatch.py` v1.8 的離線輸出（距離、`map_id`、單程秒數、`resolve_tribe`、`tribe_from_state`、兵種表、`parse_time` 在 UTC 與倫敦時區）、官方文化點表（5 種倍速 × 50 村逐格）。本機 `check_arch --expect-wp A1a-1,A1a-2,A1b --strict`：通過（違規 0、警告 0）。Actions（Python 3.11，2026-10-30）：unittest 全部 328 個 OK（A1a 原有＋A1b 新增 121；比 §9 先前記的 206＋121 多 1 個，來源未逐一核對，可能是 v0.27 後補的 `check_arch` 測試案例）、`check_arch` 通過（違規 0、警告 0、13 個檔案、73 張卡片）、`check_contracts` 通過（契約 20、範例 99）。本機沒跑的項目已由 Actions 補上 |
| 部署注意 | 同一 commit：5 個模組＋5 個測試檔＋6 個 golden JSON＋`tools/arch_manifest.py`＋主檔 v0.29；golden 缺檔測試會失敗；不在 bot 執行路徑；新 Config 鍵與預設見 §6.4（`server_*` 仍由 A0b 填） |
| 證據標記 | ✓：文化點表、倍速係數、保護天數、資源田上限 10、拓荒需求與擴張槽數、高盧商人 750／24、拓荒者速度 5、常規服與 Community Week 數值的差異來源（官方）。△：兵種數值（常規服標準值）、資源田逐級產量、柵欄／陷阱 gid、衝車 4／投石車 3／首領 5。✗：t7～t10 防禦與成本、商人倍速換算、各槽建築等級、埃及資料 |
| 留給下個 WP 的問題 | 見下 |

**A1b 留給後續 WP 的事項**

| 項目 | 留給 |
|---|---|
| `focus_mode`、`transfer_mode`、`hero_mode` 等值域與鍵名（`merge_settings` 目前 focus 固定 off）；舊 `hero_transfer_mode` 的 incoming_only／always 區分需要時再開 `transfer_exposure` | A6a2 |
| config_repo：讀 Config 用 `normalize_cfg`；邊界對應舊鍵（對照 `LEGACY_KEY_MAP`）；`tribe_from_state` 的 rows 由 state_repo 提供 | A4a／A4b、A1b 使用者 |
| 開服後核對：兵種數值（S8）、`server_map_half`、產量表（S9）、種族；商人倍速換算（目前 speed≠1 拒絕，固定 1 倍速不受影響） | A0b／SAMP |
| 舊 `main` 的「安靜時段 keep-alive」不保留；`app/main` 不再讀 `QUIET_UTC` | A6b |
| 多村 `merge_settings`（`village_rows` 非空目前丟 NotImplementedError） | B2 |
| `target_building_level`、`build_order` 格式與舊流程去留 | A4b |
| 頁面時刻字串用 `clock.resolve_clock_time`；時間解析優先用 timer value／epoch（§10 v0.12） | A2a-2／A2b、B8 |
| D-21 同意後才升 C-v0.6；`tribe_data` 已先用 `u1`～`u10`，不需改 | D-21 |
| 上一份第 4 點（`check_arch` 種族字串補 `spartan`、`viking`）：repo 的 `tools/check_arch.py` 已是 v0.1.1 且含這兩個字串；`tests/tools/test_check_arch.py` 對應案例是否已加，待確認 | 下次動 `tools/` |
| 驗收指令：`python tools/check_arch.py --expect-wp A1a-1,A1a-2,A1b --strict`、`python tools/check_contracts.py`、`python -m unittest discover -s tests -t .` | 每個 WP |

**A1a-3 交接區塊（§8.2 格式）**

| 欄位 | 內容 |
|---|---|
| WP／日期／版本 | A1a-3／2026-10-28／工具皆 v0.1；契約仍 C-v0.5 |
| 做了什麼 | ①`arch_manifest`：73 張卡片（id、path、layer、deps、wp、disp），由 `make_manifest` 自 §4.2 轉出（轉出前檢查依賴方向、循環、張數） ②`check_arch`：依賴方向、循環、登記、舊模組 import、三個單一出口等 ③`check_contracts`：spec 對 dataclass、全部範例、dict／row 往返、範例檔新舊比對 ④產生 `tests/contracts/` 範例檔 ⑤對 A1a-1／2 跑檢查 |
| 每張卡片的結果 | 無新交付卡片。A1a-1／2 的 cm-01、02、03、04、09、10、11、13 檢查全部通過，無需重新規劃 |
| 架構卡片變動 | 無 |
| 新增或修改的檔案與版本 | 新增：`tools/arch_manifest.py`、`check_arch.py`、`check_contracts.py`、`make_manifest.py`（皆 v0.1）；`tests/tools/{__init__,test_check_arch,test_check_contracts,test_make_manifest}.py`；`tests/contracts/*.json`（40）。修改：分支測試 workflow 加兩步，actions 升 checkout／setup-python v6（Node 24） |
| 介面／契約變動 | 無 |
| 格式變動 | 範例檔頂層 `{schema_version:1, contract, kind, cases}`；cases 每項 `{data, ctx}`，invalid 另有 `field`、`rule`；ctx 內的集合（`tribes`、`action_names`）存成排序後的 list，讀回用 `load_cases` 還原；檔案為 `dumps_stable` 輸出 |
| 測試 | 新增 51 個（check_arch 20、check_contracts 21、make_manifest 10）；Actions 已確認 206 個 OK（155 個 A1a-1／2 原有＋51 個新增）；測試時 CLI 輸出已改為擷取並斷言，日誌不再出現假的 VIOLATION／usage |
| 部署注意 | 不在 bot 執行路徑；`tools/`、`tests/tools/`（含 `__init__.py`）、`tests/contracts/` 要同一 commit；`tests/tools/` 缺 `__init__.py` 時 discover 會整個跳過（已踩過）；無新 Config 鍵 |
| 證據標記 | ✓：兩個工具對真實 A1a-1／2 檔案的結果、196 個測試。✗：靜態看不出的規則（只有 `*_repo` 讀寫 Sheet、只有 `infra/session` 讀寫 session 檔）仍靠 code review；`arch_manifest` 的 `disp` 欄只供參考 |
| 留給下個 WP 的問題 | 見下 |

**A1a-3 留給後續 WP 的事項**
1. 驗收指令每個 WP 都跑：`python tools/check_arch.py --expect-wp <本 WP> --strict`、`python tools/check_contracts.py`、`python -m unittest discover -s tests -t .`。`--expect-wp` 要列出到目前為止所有已完成的 WP（A1b 起為 `A1a-1,A1a-2,A1b`…），否則新檔不會被檢查是否存在。
2. §4.2 變動（卡片增減、依賴改動）後要重新轉出：`python tools/make_manifest.py <主檔.md>`，再提交 `tools/arch_manifest.py`；`--check` 可只比對是否過期。腳本在轉出前會檢查依賴方向、循環、文中「N 個模組」與解析張數是否相符，不過就不寫檔。
3. `UNDECLARED_DEP`（實際 import 不在卡片「依賴」欄）目前是警告，`--strict` 才算違規；現況 0 筆，建議之後驗收一律加 `--strict`。
4. **已定（v0.27）**：種族字串檢查保留 egyptian、hun，並補 spartan、viking（官方資料：Legends 共 6 族，另有 Vikings 在 Northern Legends 世界取代 Teutons；`Constants.TRIBE_ID` 也有 viking，見 §11.6-F）。**要做**：`tools/check_arch.py` 的種族字串清單補 `spartan`、`viking`，並在 `tests/tools/test_check_arch.py` 加對應案例（下次動 `tools/` 時一併做，不影響 A1a-3 已通過的結果）。
5. **已定（v0.27）**：範例檔沿用契約名命名（`{契約名}.valid.json`／`.invalid.json`），不改 C1～C12 編號（編號只是文件用，契約名才是程式與 `CONTRACT_SPECS` 的鍵）；§4.2 `tests/contracts/` 列已改。
6. `schema.py` 的範例或規格有變動後，要重新執行 `python tools/check_contracts.py --write` 並提交 `tests/contracts/`；否則 CI 會報 `FILE_STALE`。

**A1a-2 留給後續 WP 的事項**

| 項目 | 留給 |
|---|---|
| Transit、Market 分頁的 row 轉換（Transit 多了 ts_utc、result、detail，建議新增 TransitRow） | A6a2／market_repo |
| tribe 預設值，以及非預設種族的「未驗證」警告 | A1b（config_schema、tribe_data）✅ 已完成（v0.29） |
| `profile_from_dict` 傳 `tribes=tribe_data.TRIBES`；`verify_against_page` 傳種族 id 對照表 | A1b（`profile_from_cfg`、`tribe_keys_by_id()` ✅ 已完成 v0.29）、config_repo、A2b |
| `scale_speed` 哪些量乘、哪些量除 | cm-12（game_rules）✅ 已完成（v0.29：`speed_rules`；部隊速度不等於倍速，不能一律用 `scale_speed`） |
| PageFacts 欄位語意、`tz_offset_s` 核對、hard／soft 分級（v0.30：各村座標 ≤ `map_half` 為 hard） | A2b（對照 S9 樣本） |
| parsed 欄位：`cap` 順序 ✓、`building` 選擇器 ✓（v0.31）；movements 結構仍缺來襲樣本（S7） | A2a-2、A2b |
| S10／S11 樣本（見 §11.2；舊服現在即可抓）：佇列有空位的空地建築頁、既有建築升級頁 | A2a-2 開工前（2026-10-31 已收到舊服頁面，尚需存成檔案並用 `scrub_sample.py` 脫敏） |
| decisions 欄位 | A3a～A3c |
| §4.2 cm-01 卡片文字補上 C7、C12 | 已於 v0.25 完成 |
| A1a-1 遺留：gid 29、30、44、48 名稱待樣本核對 | A0b／SAMP |

---

## 10. 決策紀錄

### 已定（精簡；只追加、不刪）

| 版本 | 決定 |
|---|---|
| v0.1 | 逐村依序執行，不平行（單一 session、避免狀態競爭）；多村主要障礙是請求不帶村 id、Sheet 無村維度、Oases 單中心覆蓋，**不是**全域變數；`Actions` 只在最後加第 10 欄；每個寫入動作先 dry、關卡通過才 live |
| v0.2 | **以村數為關卡**；**專攻高盧**；`is_capital` 逐村（首都可能是第 2 村）；村莊鎖定不符時「跳過該村」而非 `disable()` |
| v0.3 | 階段可開關、模組只經契約溝通、單村相容 |
| v0.4～v0.5 | 先定目標架構再把舊程式搬進去；遷移由下往上；合併為單一 `multi-village-dev` |
| v0.7 | **架構先行**（每檔一張卡片，WP 只實作卡片，偏離＝重新規劃）；分層 common／parsers／domain／infra／actions／app；domain 與 actions 互不依賴、由 stage 串接；遷移順序 common→(parsers／domain／infra)→actions→app；舊程式能套用就套用、不能就重新規劃（§5.1）；單村階段先建唯讀 `load_villages`、單村 `merge_settings`、`village_switch`（無操作）；排程相關不納入本檔 |
| v0.6／v0.8 | 高盧山洞倍率先填 2（△，遊戲內實測後改 ✓） |
| v0.8 | 主筆記視為全新伺服器第 0 天；`ServerProfile`（C11）；session 快取綁 `server_id`；種族固定高盧、保有換族彈性；**嚴格格式協定（§6）**；契約升 C-v0.3；`geo`／`clock`／`gateway` 不寫死地圖大小、時區、網址 |
| v0.9 | **新程式直接開局**（舊程式不跑、不留 shim／回退／掛鉤；GA 通過才 live）；取消 B0、`village_lock` 由 A3c 新寫、A6b 接入、GA 必備（D-9 作廢）；GA 驗收改為契約／golden／煙霧測試＋單村 dry 一天 |
| v0.10 | **Gemini 邊界**：現階段只產生 `build_order`，Sheet 是唯一中繼點、Python 只讀不信任、一律先經 `plan_validate`；驗證不過＝**hold**（不動作、不寫入、不套預設、不快取舊版，其他 stage 照跑）；單村版 `build_order` 讀取與驗證提前到 A3a／A4b 並列入 GA，B6 只留多村與角色感知；資源調度、躲兵的 Gemini 介入之後再討論 |
| v0.12 | **ServerProfile 放 Config（帳號級），機密不放 Config**（Cookie、帳密、Sheet 憑證走 Secrets）；契約 C-v0.5：C11 加 `locale`；`server_tz` 取頁面 `Travian.Game.timeZone`；`map_half` 以 `karte.php?d=` 與座標用公式驗證（舊頁驗得 200 ✓）；`tribe` 以頁面 `tribeId` 交叉檢查（3＝高盧 ✓）；時間解析優先用 `timer value`（秒）與 `Travian.Game.timestamp`（epoch），不解析 HH:MM 文字；村莊清單與文化點優先讀頁面 `viewData` JSON；A0 期間不啟用排程 |
| v0.13 | `server_id` 用主機名稱；`x數字` 只當 `server_speed` 的交叉檢查、不當來源；未登入頁不能當樣本（語言與內容都不同），樣本一律登入後抓；伺服器 UUID 不進契約 |
| v0.14 | **D-15 定案＝(b) 嚴格格式**：新 Sheet 所有分頁依 §6.1 重新定義欄位、不沿用舊欄位位置（舊「只追加、舊欄位位置不動」只適用舊伺服器）；Apps Script 同步改（連帶範圍見 D-20）。**D-17 定案**：Sheet ID、Cookie、帳密放 GitHub Secrets，`server_*` 放 Config；Secrets 名稱仍待 A4a 回填，舊 workflow 的同名 Secrets 不覆蓋。**D-19 定案**：新服不買 Plus，`queue_slots` 預設 1（C6 不改），快速連結與連結列表視為不可用 |
| v0.15 | 倍速與地圖大小以新服 S8（`Variables.js`）為來源，`d=` 公式降為交叉驗算；`tribe_id` 以 `Constants.TRIBE_ID` 為準；英雄狀態碼、事件類型、村型態以 `Constants.js` 數值為準（A2b、B8）；aid 與 gid 不得混用（aid 26＝主建築格、gid 26＝皇宮）；單位編號分「全域 id」與「種族內序號」兩套，契約用後者（待 D-21 同意） |
| v0.16 | **D-18 定案（含修正；其中 `d=` 硬性檢查、③的「0 次額外請求」之前提與⑤的 PageFacts 欄位已由 v0.30 修正，見該列）**：①檢查分「硬性（不符＝本輪 hold）」與「軟性（只警告）」。硬性：頁面 `tribeId`≠`tribe`；頁面 `timezoneOffsetToUTC`≠依 `server_tz` 與頁面 `timestamp` 算出的 offset；頁面第一個 `karte.php?d=` 與座標代入 `map_half` 公式不符；S8 的 `Speed`／`Map.Size`≠Config。軟性：gpack 版號變動、`<html lang>`≠`server_locale`（A2a 確認 parsers 沒有中文字面依賴後才維持軟性，否則升硬性）、頁面 `timestamp` 與本機 UTC 差 >120 秒。②主機核對沒有意義（請求本來就打 `base_url`），身分核對靠 `wuid`（待 D-21，同意前不含）。③頻率：PageFacts 取自每輪本來就抓的 dorf1（0 次額外請求）；S8 只在每日第一輪或 gpack 版號變動時重抓（2 次請求）。④hold＝本輪所有寫入遊戲的 stage 不動作，只寫一列 Actions `skipped`＋原因（`did` 用目前村）。⑤落點：`cm-13.verify_against_page(profile, facts)→list[Problem]`（純函式）、`ps-01.parse_page_facts`、`cm-09.PageFacts`、`ap-01` 建 RunContext 前呼叫；GA 加實測。**D-20 定案**：A4b 改為「以舊函式為參考、輸出 §6.3 嚴格格式」，規模 M→L，開始時重估是否拆；新增 **A4c**（Apps Script 單村新格式，GA 前必須完成）；B6 只剩多村；各新分頁欄位清單在 A4b 定案並升契約 |
| v0.17 | **A0 拆分**：A0a（Sheet 骨架、Secrets 名稱草案）開服前做；A0b（主機、S8、S9、S3、S6、Cookie、Config 初值）等新服開服再做。順序上允許先做 A1a 以後的 WP（A1a 只依賴 D-10，不依賴新服的值）；A 系列用離線測試驗收，GA 前 bot 不 live、不跑舊程式（規則 12 不變）。開服後以設定檔（Config 初值）一次交給 AI 即可開始手動玩 |
| v0.18 | **D-10 現況（✓ 你貼的檔）**：根目錄平檔、Python 3.11、`pip install -r requirements.txt`、`python travian_ci_run.py`，由 Apps Script 以 `workflow_dispatch` 觸發。**建議、待確認**：套件放 repo 根目錄、`python -m` 執行。`auto_build.yml` 檔名與 `main` 分支固定（Apps Script 依賴）；A6b 的 yml `DRY_RUN` 預設 `"1"`；`TRAVIAN_BASE_URL` 不再當 Secret（D-17）；A0b 設新 Secrets 前先關 Apps Script 觸發器（A-7）（此條已被 v0.19 取代） |
| v0.19 | **D-10 定案＝套件放 repo 根目錄、`python -m travian_bot.app.main` 執行**（與現況差別只有程式放 `travian_bot/` 子資料夾、`run:` 指令不同；Python 3.11、`pip install -r requirements.txt`、cache、`workflow_dispatch`、yml 檔名與 `main` 分支都不變；不需 PYTHONPATH 或安裝步驟；每層需 `__init__.py`、需在 repo 根目錄執行）。**A-7 修訂**：Apps Script 觸發器維持開著（GitHub schedule 會漏跑），改靠新名稱 Secrets 隔離新舊。**事實（✓ 你貼的截圖與檔案）**：repo 根目錄全是平檔——`auto_build.py`、`check_layout.py`、`debug_fields.py`、`debug_login_flow.py`、`debug_village_buildings.py`、`dispatch.py`、`fill_in.py`、`hero_focus.py`、`hide_observe.py`、`hide_troops.py`、`notify.py`、`oasis_check.py`、`oasis_scan.py`、`oasis_store.py`、`runner.py`、`sample_dorf2.html`、`scrape_and_log.py`、`sheets_writer.py`、`stock_guard.py`、`transfer_io.py`、`travian_agent.py`、`travian_ci_run.py`、`travian_const.py`、`travian_hero.py`、`travian_models.py`、`travian_pages.py`、`README.md`、`requirements.txt`；清單截止在 `travian_pages.py`（下面是否還有 `travian_parser`、`travian_transfer`、`village_log` 等 ✗ 待確認）；圖中沒有 `tests/`、`appsscript/` 資料夾、沒有 `test_*.py`（✗ 待確認）。`requirements.txt` 六個套件無版本釘選（beautifulsoup4、lxml、requests、gspread、google-auth、playwright），無 pytest；A1a 新程式只需標準庫（含 `zoneinfo`），測試用套件另放 `requirements-dev.txt`（待你同意）。新程式放 `travian_bot/` 後，根目錄舊平檔仍在同一 sys.path：`check_arch` 要加規則，禁止新程式 import 舊根目錄模組 |
| v0.23 | **A1a 拆成 A1a-1（serialize／schema／constants／modes＋D-10 import 驗證）、A1a-2（models／parsed／decisions／server_profile）、A1a-3（arch_manifest／check_arch／check_contracts／範例檔）**，規模各 M；§4.2 卡片 WP 欄與 §7、§9、順序行同步。**筆記維護**：主檔為唯一真相來源，切片由 `tools/make_slice.py` 自動產生、不手改（§8.4）。契約與卡片簽名不變 |
| v0.22 | ①**yml 現況**：你附的 `auto_build.yml` 是舊版（`cron: "7,27,47"` 啟用），你確認 main 現況為 **schedule 已註解、只靠 Apps Script 觸發**（A-7 前提不變）；A6b 改 `run:` 行前，要重新附 main 版。②**常數拆分**：`travian_const.py` 不整份進 `constants`（見 cm-03／06／12 的舊源欄）。③**`travian_models.py` 屬於 cm-09 的來源，不是 cm-01**。④**D-22 測試方式＝你手動在分支上跑 `workflow_dispatch`**（分支改自己那份 `auto_build.yml`：`run:` 行、新名稱 Secrets、`DRY_RUN: "1"`）：Apps Script 打的是 main、排程只在 main，不會誤觸發分支；**保留 `concurrency: travian`**（與舊 bot 序列化、不會同時用 session，撤回 v0.21 對話中「改不同 group」的建議）；快取 key 前綴改成與舊 bot 不同（如 `travian-test-`），避免分支還原 main 的 session（依 GitHub 快取範圍規則 △：分支存的快取 main 看不到，但分支看得到 main 的）；若與舊 bot 用同一帳號，新 Cookie 是否踢掉舊 session ✗（S2），測試前確認舊 bot 沒在跑。⑤A-8 修正（見 A-8）。契約不變 |
| v0.21 | **D-22 定案＝舊服可當新程式的測試場，僅限 dry／唯讀**。條件：①`DRY_RUN=1`、寫入類 mode 只能 off／dry，舊服不 live（live 只在新服過 GA 後，從第 0 天起算）；②Config `server_*` 填舊服值（`server_id`＝舊主機，session 快取因此與新服隔離）；③新名稱 Secrets（如 `TRAVIAN_SEED_COOKIE_S1TEST`、`GOOGLE_SHEET_ID_TEST`），不覆蓋舊名稱；④**測試用 Sheet 另開一份**，不與舊 bot 的 Sheet 共用，舊 bot 與新程式不同時寫同一分頁；⑤舊服狀態（村、英雄、建築）只當測試資料，**不帶進新服**（規則 9 不變）；⑥舊服樣本脫敏後可當 golden 與離線測試（S9 的穀物欄位、`d=` 驗算等可提前確認）。**時機**：A6b 之前沒有入口，所謂「跑」只能是離線測試＋舊服樣本；A6b 合併到 main 是切換點（A-7），之後觸發器跑新入口、舊服的舊 bot 停止，若要舊服舊 bot 繼續跑須另開 workflow。D-14「舊程式不上線」仍只針對新服。契約不變 |
| v0.20 | **D-1、D-8 提前到 G0 定案**（`is_capital`、資源田上限、`build_order` 都依賴）；**D-3、D-4 不提前**（市場載重、文化點門檻仍 △，等 C1／D1 真實樣本）；`Villages` 分頁完整版仍在 B2，單村階段只把答案記入 §10。**寫入前再核對**：`village_cycle` 在每個寫入類 stage 前呼叫 `assert_active`，不符＝該村剩餘寫入 stage `skipped`、不 `disable()`；不放在 actions（分層）。**動態跳過歸 B3**，省 dorf2 須同時滿足佇列忙、資源不足、next_target 為資源田；來襲優先序待 S7 驗證 B8。契約不變（C-v0.5） |
| v0.24 新-1 | `serialize.loads_checked(text, schema_name, validator=None, max_version=1)`：驗證函式由呼叫端注入（影響：cm-10；讀 JSON 檔的 infra 模組） |
| v0.24 新-2 | 核准卡片外新增的公開項目：`serialize.{dumps_compact, res_to_cost_str, cost_str_to_res, SerializeError, RES_SUFFIXES}`、`modes.{parse_mode_checked, parse_dry_run_flag}`、`schema.{ensure_valid, CONTRACT_NAMES}`、`constants.UNVERIFIED_GIDS`（影響：cm-03、04、10、11） |
| v0.24 新-3 | C3／C4 的 `plan_id` 內嵌來源與目標必須等於 `from_did`、`to_did`；C12 的 `missing_order` ⇔ `next_seq` 為 null；`missing_order` 那筆的 `seq` 仍 ≥1（建議之後明訂）（影響：C3、C4、C12） |
| v0.24 新-4 | C2 兵種鍵暫不限格式、C4 `units` 鍵限 `u1`～`u10`／`hero`，兩者隨 D-21 定案；C11 暫不加 `wuid`（影響：D-21） |
| v0.24 新-5 | C11 `server_tz` 沿用原 regex，不接受兩層斜線名稱；「非 gaul 警告」留給 cm-06 之後的 WP（影響：C11） |
| v0.24 新-6 | D-10 已驗證：`travian_bot/` 放 repo 根目錄、`python -m` 執行，無需 `PYTHONPATH`（影響：A6b） |
| v0.24 新-7 | 舊 `fill_in_mode` 的 `on` 在讀 Config 的邊界（config_repo）轉成 `live`；`parse_mode` 本身保持嚴格，只認 off／dry／live。寫出一律用 `live`（影響：config_repo（A1b）、cm-04） |
| v0.24 新-8 | `guard_mode` 只用 off／dry／live；舊 `hero_guard_mode` 的 incoming／always 語意（沒有來襲時，暴露風險算不算）改由新 Config 鍵 `guard_exposure`（always／incoming，預設 incoming ✗）承接。對應 `runner.py` `_try_guard` 的 lam：always 或 dry 或有來襲時為 0.5，否則 0.0。預設值需用舊行為確認後再定案（影響：`config_schema.DEFAULTS`（A1b）、守衛 stage（A6a2）、§6.4） |
| v0.24 新-9 | 舊版把 live 當 off 的行為不保留。新伺服器的 Config 全部重填，不受影響（影響：無） |
| v0.25 | `DEFAULT_TARGET_BUILDING_LEVEL`＝10，放 `config_schema.DEFAULTS`；`BuildSettings` 不重複給預設，預設只有一個來源（2026-10-27） |
| v0.27 | ①種族字串檢查清單＝gaul、roman、teuton、egyptian、hun、spartan、viking（依官方：Legends 6 族，Vikings 於 Northern Legends 世界取代 Teutons）；`tribe_data` 仍只先填高盧，其他族補表屬換族工作。②`tests/contracts/` 範例檔以契約名命名，不用 C1～C12 編號（2026-10-29） |
| v0.29 | A1b 定案：①**取消安靜時段**（D-24，你決定不需要；舊 `QUIET_UTC`、`in_quiet_hours` 不保留，Config 無對應鍵）。②**伺服器＝1 倍速常規服**（D-16 的倍速與伺服器類型；其餘欄位待 A0b）；D-27（單位數值版本欄位）關閉，兵種表只放常規服標準值，Community Week 數值不同（高盧劍士 70／7、雷法師 110、海頓 150）、不適用；將來改玩活動服或倍速服要先開 C-v0.6。③**Config 舊鍵遷移**（D-25）：見 §6.4 與 `LEGACY_KEY_MAP`；`hide_mode` 的 `observe` 取消；`hero_adventure`、`hero_transfer_mode` 由 `hero_mode`、`transfer_mode` 取代；`focus_mode` 維持 off／auto（merge 時固定 off，A6a2 定案）。④**卡片依賴**（D-26）：cm-05＝cm-10＋cm-13、cm-06＝cm-11、cm-08＝cm-01／04／06／10／11／12／13（`config_schema` 用 `game_rules` 檢查非首都 `target_level` 不超過 10）。⑤單村模式首都以 Config 為準（頁面讀不出首都時）。⑥商人在倍速服的換算官方沒有說明（部隊速度乘數不等於倍速），`merchant_info` 在 speed≠1 拒絕。⑦`tribe_data` 已先用 `u1`～`u10` 與 `global_unit_id`（內部資料），D-21 仍待同意才升契約（2026-10-30） |
| v0.30 | **D-18 修正**：①硬性（不符＝本輪 hold）：頁面 `tribeId`≠`tribe`；頁面 `timezoneOffsetToUTC`≠依 `server_tz` 與頁面 `timestamp` 算出的 offset；S8 的 `Speed`／`Map.Size`≠Config；`viewData.villageList` 任一村座標的 |x| 或 |y| > `map_half`（新增，取自每輪 dorf1，不需額外請求）。軟性：gpack 版號變動、`<html lang>`≠`server_locale`（條件同 v0.16）、頁面 `timestamp` 與本機 UTC 差 >120 秒。②不變。③頻率不變：PageFacts 取自每輪 dorf1（0 次額外請求）；S8 只在每日第一輪或 gpack 版號變動時重抓（2 次請求）。**執行期不抓集結點、不讀 `karte.php?d=`**：依舊服 Asia 8 樣本，`karte.php?d=` 只出現在集結點概覽（`build.php?id=39&gid=16&tt=1`）的 `table.troop_details`，dorf1／dorf2 共五份都沒有；無部隊時表格可能不存在；第一張表不保證是目前村（英雄出擊時是「出擊軍團」）。`d=` 公式（`geo.map_id`）只用於 A0b 對 S6 樣本做一次性交叉驗算，以及 `geo` 單元測試（舊服 3 組 d／座標全符：114461＝(−25｜−85)、109245＝(−28｜−72)、115264＝(−24｜−87)，`map_half`＝200 ✓）。④不變。⑤落點不變；`cm-09.PageFacts` 欄位：時區、offset、lang、gpack、tribeId、timestamp、各村座標。D-21（`wuid`）仍待同意，本次不涉及。契約不變（C-v0.5） |
| v0.31 | **A2a 前置決定**（依舊服樣本與舊 `travian_pages.py` 實跑；未改契約，cm-09 仍為草案）：①**去中文字面**：舊碼有 3 處依賴中文（`新手保護`、`等級\s*N`、`目前等級:`）；A2a 把建築前置條件的兩處改成只取數字；`新手保護` 暫無結構選擇器，待 S9。**維持 D-18 原規則**：A2a 完成時若仍有中文字面依賴，`<html lang>`≠`server_locale` 升為硬性。②（Plus 部分已由 v0.33 修正，沿用舊設計）；`protection_s` 欄位保留，讀不到＝None 並記警告，S9 後定案。③`parse_dorf2_slots` 以 aid 去重（城牆 aid 40 在等級大於 0 時有 `top`／`bottom` 兩個 `.buildingSlot`，舊碼回 23 筆）。④`parse_movements`：class `hero_on_adventure` 定為 kind `adventure`；其餘未見 class 原樣保留；來襲（`att1`／`def1`）仍只憑舊註解，待 S7。⑤`BuildOption`：`exceeds_storage` 改名 `exchange_disabled`（與「成本合計大於庫存合計」4／4 吻合，屬推測）；新增 `afford_in_s`；建造佇列滿與「不能蓋」的區分待 S10。⑥`parse_player_info` 輸入不限 dorf1／dorf2（兩者皆含 `viewData` ✓）。⑦已驗證：施工佇列 `div.buildingList li span.timer`、`underConstruction` 旗標（dorf1 資源田、dorf2 建築位）、`maxStorage` l1～l4 順序、`parse_active_village` 兩處一致。⑧樣本脫敏工具 `scrub_sample.py` 升 v0.2（通用座標平移、`d=` 重算、他人名稱與 id 替換、自動驗證）。契約仍 C-v0.5 |
| v0.32 | **A2a 前置決定補充**（S10／S11 舊服頁面實跑；仍未改契約）：①`exchange_disabled` 再得 2 筆佐證：研究院（庫存合計 4367、成本合計 6020）disabled；兵營 5 級（成本合計 2505）enabled；累計 6／6 與「成本合計大於庫存合計」吻合，仍屬推測。②`afford_in_s` 可驗算：研究院頁 `errorMessage` 內 `span.timer[value]`＝14323 秒，與「各資源 (成本−庫存)÷每小時產量 的最大值」吻合（木：(2595−367)÷560×3600＝14323），代表「依目前產量、不計倉容」的時間；兵營 5 級頁同一欄位隨時間遞減（兩次抓取相差 50 秒，值差 50）。③建造按鈕三態（推測）：有綠色按鈕（空地頁 `green new`、升級頁 `green build`）、旁邊有 `span.none` 註記「（等待排程）」＝可排入佇列但前面已有施工；只有金幣 `gold builder`、沒有綠色＝佇列已滿；兩者都沒有＝資源或條件不足。佇列內容待同時刻的 dorf1／dorf2 佐證（S10 補件）。④建築名稱 `div.build_desc h2` 可能帶序號前綴（「2. 山洞」，疑為新手任務標記）：建築身分一律用 `contract_building<gid>` 的 gid，名稱取用時去掉開頭的「數字＋點＋空白」。⑤`parse_building_cost`／`find_upgrade_url` 對研究院（頁內有研究清單）與兵營（頁內有訓練表單）只讀 `div.upgradeBuilding`，以新樣本結構實跑通過（v2.38 的處理仍有效）。⑥被劃掉的前置條件（皇宮頁的行宮）維持 `forbidden=True`、`level=0`、`current=None`。⑦**樣本必須是原始 HTML，不可用瀏覽器複製的 DOM**：DOM 版會補 `<tbody>`、屬性小寫化（`data-troopid`）、移除 `title`（「目前等級」與 tooltip 全失）、加 `data-value`；`parse_build_options` 讀 DOM 版時 `current` 變成 None。⑧建築 `checksum` 兩村不同（34593 為 f16456、29786 為 afcf66；訓練表單 5055de 兩村相同），疑為每村各一，不得跨村沿用。契約仍 C-v0.5 |
| v0.33 | **Plus 沿用舊設計（修正 v0.31 ②）**：Plus 由人工在遊戲內開關；系統不購買（D-19「不買 Plus」不變）。頁面顯示有開（`viewData.ownPlayer.goldFeatures.travianPlus.isActive`＝true）就用：`PlayerInfo.plus`＝True，stage 對 `queue_slots` 加 1（舊設計「Plus 的 +1 由 stage 處理」，C6 不改）；沒開就不用，`queue_slots` 維持預設。`plus_s`（Plus 剩餘秒數）維持舊欄位，讀 dorf1 的 `#sidebarBoxInfobox`；舊服樣本 Plus 啟用但該區塊不存在，讀不到＝None，行為不依賴它。⚠ 待確認（已列 D-28）：D-19 的「快速連結與連結列表視為不可用」是否改為隨 Plus 狀態啟用（舊設計未在本文件載明）；不影響 A2a 解析。契約仍 C-v0.5 |
| v0.34 | **主檔同步（無新決定）**：§0 的舊檔版本 `travian_pages` 改 v2.38（依你上傳的檔案）；§0 進度加註 A2a 前置資料；§7 A2a 處置由「沿用（純搬）」改「沿用＋修改」、內容加 BuildOption／PageFacts；§9 狀態列加註；§10 待決新增 D-28（Plus 有開時的快速連結與連結列表）；風險新增 A-10（樣本來源：DOM 與原始 HTML）。契約仍 C-v0.5 |
| v0.35 | **A2a 拆成 A2a-1 與 A2a-2**（無新設計決定）：原因＝單次對話額度不足以一次處理 4 張卡片與樣本。**A2a-1**＝ps-02（village_list）、ps-04（player），定案 `PlayerInfo`；**A2a-2**＝ps-01（village）、ps-03（buildings），定案 `Dorf1`／`Dorf2`／`PageFacts`／`BuildOption`。兩半都改 `common/parsed.py`（cm-09），須依序 A2a-1→A2a-2。其他 WP 依賴欄寫的「A2a」＝A2a-1、A2a-2 都完成。§4.2 卡片內容不變、只改 WP 欄；§7、§9、§0 同步；`arch_manifest` 須重新轉出。`--expect-wp` 於 A2a-1 完成後加 `A2a-1`、A2a-2 完成後再加 `A2a-2`。契約仍 C-v0.5 |
| v0.36 | **A2a-1 定案**（程式交付、待 Actions 驗收；契約仍 C-v0.5）：①`resolve_home(html, map_half=None)→(x, y)｜None` 照卡片，Config 備用與說明字串移到呼叫端（A5b）；舊 `map_size`（401）改 `map_half`，沒給就略過範圍檢查（同 schema 的 ctx 慣例）②`parse_player_info` 整段讀不到（沒有 viewData、ownPlayer 不是物件）丟 `ParseError`（舊回 None），個別欄位讀不到仍 None；文化點與名額五欄同進同出③`parse_village_list` 與側欄的 did 集合、座標、作用中的村任何一項不一致丟 `ParseError`；頁面沒有側欄時只用 viewData④`viewData` 讀取函式在每個 parser 各放私有複本（check_arch 禁止 parsers 互相 import，common 不放頁面解析）；`tests/parsers/test_viewdata_helpers.py` 用同一批案例跑每份複本，A2a-2 新增 `village.py` 時加進 `MODULES`⑤ps-02、ps-04 依賴欄加 cm-11（`ParseError` 在 schema；`--strict` 的 UNDECLARED_DEP）⑥`PlayerInfo` 定案（cm-09 v0.2），其餘 parsed 結構仍草案⑦樣本 S1a／S1b：舊服 dorf1、脫敏；`captured_utc` 取自頁面 `Travian.Game.timestamp`，`server_id` 暫用頁面標題「Asia 8」（頁面無主機名稱），`source=raw` 為特徵判斷、未經取得方式確認 |

### 待決（你的決定）

| 編號 | 問題 | 影響 |
|---|---|---|
| **D-1** | （v0.20：G0 前定案，答案先記 §10，B2 一次填入 `Villages`）五個村各自角色（首都／資源／軍事…）與開村時間表 | `build_order`、運資源方向、捐方 |
| **D-2** | 開新村節奏（第幾天達第 2 村文化點門檻；倍速見 D-16）；是否願意手動到 `Villages` 加一列 | 自動偵測新村做到什麼程度 |
| **D-3** | （v0.20：等 D1 解析出在家／在外兵力後再定）「運兵」用途：①守軍移到被打的村 ②躲兵改增援自己另一村 ③軍事村集中 ④其他 | D1／D2 設計；可能取代部分躲兵邏輯 |
| **D-4** | （v0.20：等 C1 市場樣本後再定）資源調度政策：誰優先、捐方保留量、受方補到多滿、是否把易被搶村的溢出轉走 | `market_plan` |
| **D-5** | 英雄住哪個村、是否搬家；多村後是否只服務英雄村 | B5、B6 |
| **D-6** | 單輪逾時上限（目前 8 分；五村估 3.5～6 分） | B3 時間預算 |
| **D-7** | 村級錯誤要不要主動通知 | E1 |
| **D-8** | **首都放哪個村**（官方建議第 2 村）、皇宮何時蓋、第 1 村首都移走後 `build_order` 是否改上限 10（已蓋超過 10 級的田會不會降級 ✗） | G0 就要定；`is_capital`、`build_order`、Gemini |
| ~~**D-10**~~（v0.19 已定，見 §10 已定） | 套件名與執行方式（`python -m travian_bot.app.main`、`PYTHONPATH`、`pip install -e` 或平檔＋子資料夾）；先在測試分支驗證 Actions 上能 import。**v0.18 現況（你貼的 yml ✓）**：repo 根目錄平檔、`pip install -r requirements.txt`、Python 3.11、`python travian_ci_run.py`，無 PYTHONPATH、無安裝步驟；`workflow_dispatch` 可在分支手動跑。**已定（v0.19）**：`travian_bot/` 放 repo 根目錄，yml 改 `python -m travian_bot.app.main`，不需 PYTHONPATH 或安裝。驗證方式：測試分支手動跑一次 workflow，只執行 `python -c "import travian_bot…"`，不碰 main | A1a 第一件事 |
| **D-11** | 遷移期間是否凍結新功能（只修 bug）；A 系列以離線測試驗收，GA 前 bot 不 live | 遷移風險與節奏 |
| **D-16** | 新伺服器參數：網址與代號、倍速、地圖大小、時區、開服時間、新手保護天數、遊戲版本（v0.29 已定：倍速＝1、常規服；其餘待 A0b） | C11、A0、geo／clock／game_rules；**欄位逐項見 §11.6-A（v0.12）** |
| **D-21** | 契約兩處澄清（同意才升 C-v0.6）：①C11 加選填 `wuid`（伺服器唯一碼，Config 鍵 `server_wuid`；啟動檢查 D-18 比對頁面 `Travian.Constants.wuid`；取代 v0.13「UUID 不進契約」）②C4 `units` 的鍵 `u1`～`u10` 定義為**種族內序號**（對應集結點表單 `t1`～`t10`，英雄 `hero`＝`t11`），全域單位 id 只在 `tribe_data` 換算（高盧 21～30） | C11、C4、cm-06、cm-13、ps-05 |
| **D-23** | **穀物赤字／可用穀物不足時建築被擋**（你的說明：穀物赤字低到一個程度，建物都不能蓋）。樣本：庫存 750／穀倉 800、淨產量 −30、可用穀物 7，約 25 小時後耗盡，另有一筆建築（資源田 17，穀物 1300）超過穀倉上限 800 而永遠買不起（舊標籤「倉容不足」）。待定：①被擋的門檻（✗ 推測與可用穀物 `l5` 對建築新增人口有關，需實測）②C2 要不要加 `free_crop`（目前沒有，同意才升 C-v0.6）③決策標籤新增「糧食不足」與其處理（優先蓋農田？停其他建築？通知？） | C2、`plan_validate`／建城決策、E1 通知 |
| **D-28** | （v0.33）Plus 由人工在遊戲內開關、有開就用；D-19 原寫「快速連結與連結列表視為不可用」，是否改為「Plus 有開時可用、沒開時不可用」？舊設計未在本文件載明 | 快速連結與連結列表相關功能的有無；不影響 A2a、A2b 解析 |

### 架構與遷移風險

| 編號 | 問題 | 對策 |
|---|---|---|
| A-3 | 未讀檔（△）：`travian_agent`、`hide_troops`、`village_log` 等實際函式與依賴 | 各 WP 開始前先上傳該檔，走 §5.1，不符就重新規劃 |
| A-4 | 全域→參數物件改寫動最多呼叫點 | 不用 shim：搬入時直接改、不留全域後門；該模組單獨一個 commit，以 golden 與 `test_tribe_switch` 驗證 |
| A-5 | 效能：包裝層與每村 Sheet 寫入不能讓逾時惡化 | 搬遷驗收記錄每輪耗時與請求數 |
| A-6 | 測試債（v0.17 定案）：**舊功能全部是你直接跑來驗證，舊 repo 的 `test_*.py` 不可信、不重跑、不逐項對照**；舊測試不當安全網，也不當 golden | ①所有舊功能一律視為「沒有測試」。②golden 以「脫敏真實樣本＋舊函式離線輸出，經你確認符合實際遊戲行為」為準（沒有舊函式可比的新模組，以契約測試與種族煙霧測試驗收）。③每個 WP 搬入模組時，順便為該模組新寫測試（放 `tests/<層>/`），舊 `test_*.py` 只在讀碼時當線索參考，不隨模組搬遷。④A0a 因此不含重跑舊測試 |
| A-7 | 觸發器與 Secrets（v0.19 修訂）：Apps Script `triggerTravian` 以 `workflow_dispatch` 打 `auto_build.yml`、分支 `main`（`GH_OWNER`／`GH_REPO`／`GH_TOKEN` 存在 Script Properties）。**觸發器是刻意開著的**：yml 的 schedule 已註解，因為 GitHub 的 schedule 會漏跑，改由 Apps Script 準時觸發（✓ 你說明）。風險：main 上的 yml 與 Secrets 同時決定「跑哪份程式、打哪個伺服器」，若新服的值覆蓋同名舊 Secrets，舊 `travian_ci_run.py` 會打到新服（違反規則 12） | 觸發器**維持開著、不關**；`auto_build.yml` 檔名、`main` 分支、`workflow_dispatch: {}` 不可改（A6b 只換 `run:` 行與 env）；新服用**新名稱**的 Secrets、不覆蓋舊名稱（D-17），舊程式繼續讀舊名稱、不受影響；草案名稱 `TRAVIAN_SEED_COOKIE_S2`、`GOOGLE_SHEET_ID_S2`，`GOOGLE_SERVICE_ACCOUNT_JSON` 與伺服器無關可沿用，正式名稱 A4a 定案。**A6b 合併到 main 的那一刻就是切換點**：之後觸發器跑的是新入口（`DRY_RUN` 預設 `"1"`，A-8），舊服的舊 bot 隨之停止；若你要舊服繼續跑，需另開 workflow（A6b 前再決定） |
| A-9（v0.21） | 舊服當測試場的風險：①新程式誤對舊服 live（舊服是真帳號）②測試與舊 bot 寫同一 Sheet 互相覆蓋③舊服資料誤入新服 Config④舊服版面與新服不同，golden 與解析器假設被錯誤固化 | ①`effective_mode` 在 `DRY_RUN=1` 時一律降 dry，且 A6b 的 yml 預設 `"1"`，寫入類 mode 預設 off；測試分支另用 Secrets 名稱②測試 Sheet 另開③Config 與 Sheet 不複製；開服後 A0b 全部重填④舊服樣本與新服 S9 比對，差異記錄；解析器不得依賴舊服獨有值 |
| A-8 | `DRY_RUN` 預設為 `"0"`（正式送出）（v0.18）；舊 yml 的 `QUIET_UTC`、`TRAVIAN_BASE_URL` 與新設計（Config 的 `server_*`、D-17）不一致 | A6b 的 yml 預設 `DRY_RUN: "1"`，GA 通過才改 `"0"`；`app/main` 讀此旗標並傳給 `modes.effective_mode`（common 層不碰環境變數，v0.22）；`TRAVIAN_BASE_URL` 不再當 Secret（改讀 Config）；`QUIET_UTC` 不保留（v0.29：不需要安靜時段，Config 無對應鍵）；session cache key 前綴 `travian-state-` 換新（A4a／A6b） |
| A-10（v0.34） | 樣本來源不一致：瀏覽器開發者工具複製的 DOM 與原始 HTML 不同（補 `<tbody>`、屬性小寫化、移除 `title`、加 `data-value`），golden 與解析器若依 DOM 版會固化錯誤假設（v0.32 實測：DOM 版的「目前等級」全部消失） | ①樣本一律用原始回應（程式取回或「檢視原始碼」另存），不得用複製元素②`*.meta.json` 建議新增 `source` 欄位（`raw` 或 `dom`），DOM 版只當線索、不進 golden③SAMP 或 `scrub_sample.py` 加檢查：含 `<tbody` 且 `source` 不是 `raw` 時警告 |

---

## 11. 還需要的資訊

### 11.1 要你補的遊戲事實（文字回答即可）

1. 新伺服器參數（D-16）：逐項與取得方式見 §11.6-A。
2. 第 1 村座標與名稱；確認它是否預設首都（預期是）；五村角色（D-1）；第 2 村預計位置與是否當首都（D-8）。
3. 市場等級、商人數、高盧商人載重（市場建好才看得到）。
4. 英雄的家在哪個村（D-5）。
5. 山洞倍率實測（傾向高盧 2 倍 △）。
6. 市場送貨實測時間（手動送一次小量，記下距離與抵達秒數）。

### 11.2 要抓的樣本（脫敏：不含 Cookie；cURL 的 `-b` 換成 `XXX`）

| 編號 | 樣本 | 取得時機 | 用途 |
|---|---|---|---|
| S1 | 有 ≥2 個村時的 dorf1 HTML（含側欄村莊清單與 `viewData`）；**舊服已收 S1a／S1b（2026-10-31，各以不同村為作用中；脫敏存 `tests/samples/`）**，新服仍待 | G2 | VillageRef、B1、B8 |
| S2 | 切村行為：切村請求的 URL／參數，再開不帶參數的 dorf1 看停在哪個村；同時確認 bot 與瀏覽器是否共用 session | G2 | 驗證 `newdid`、切村是否黏著、手動切村是否影響 bot（✗） |
| S3 | 第 1 村市場頁（gid 17）各分頁 HTML（送資源、我的貨運／在途） | **G0 可抓** | 商人、載重、在途貨解析 |
| S4 | 同上，有在途貨時（先手動送小量） | G0／G2 | 在途貨解析、避免重複計算 |
| S5 | 手動送資源的完整請求流程（URL、方法、body、是否有確認頁／checksum、回應；送 1 資源小量） | G2 | `market_exec` |
| S6 | 集結點（gid 16）：概況（`tt=1`，**有部隊與沒有任何部隊各存一份**；有多個村後再補「目前村非第一個村」一份）、在家兵力、派兵表單、增援確認頁（不要按確認） | **G0 可抓** | 運兵解析與送出；`karte.php?d=` 與座標的 `geo.map_id` 驗算（D-18 v0.30）；確認無部隊時表格與連結是否消失；以 `data-did`＝`data-ort` 挑出本村那張表（A2b） |
| S7 | 某村被攻擊時的 dorf1 與另一村同時刻的 dorf1（遇到時順手存） | 遇到時 | 來襲是帳號級或村級（B8） |
| S8 | 新伺服器 `/js/Variables.js?版號` 與 `/js/Constants.js`（公開靜態檔，免登入、不含帳號資料；版號從 S9 原始碼搜 `Variables.js` 取得） | **G0 可抓** | 倍速、地圖大小、`wuid`、各種常數（舊服已取得並解析，見 §11.6-F；新服照抓） |
| S9 | 新伺服器第 0 天 dorf1 完整原始碼（含 `Travian.Game` 的 script 區塊與 `viewData`），脫敏 | **G0 可抓** | ServerProfile 比對、`prod` 穀物欄位定案、`tribeId` 檢查 |
| S10 | 空地「建造新的建築物」頁（`build.php?id=<空地>&category=1／2／3`）：**建造佇列有空位**（要有綠色興建按鈕）與**佇列已滿**各一份；舊服已有兩份（29786 的空地頁無綠色按鈕；34593 的空地頁有綠色按鈕與「（等待排程）」註記），但抓取時沒有同時存下各村 dorf1／dorf2，佇列內容仍待證實；樣本須為原始 HTML，不可用瀏覽器複製的 DOM | 舊服現在即可抓；新服 **G0 可抓** | `parse_build_options` 的 `buildable`、佇列滿與不能蓋的區分、`afford_in_s`、`exchange_disabled` 的意義（§10 v0.31） |
| S11 | 既有建築的升級頁：一般建築（倉庫／糧倉）、研究院（頁面含兵種研究清單）、兵營（含 `buildActionOverview` 訓練表單）各一份；舊服已有兵營 1 級（34593）、兵營 5 級（29786，含「訓練中」表格）、研究院 10 級（29786），其中兵營 5 級與研究院一份是 DOM 複製片段，需重抓原始 HTML | 舊服現在即可抓；新服 **G0 可抓** | `parse_building_cost`、`find_upgrade_url`（升級區塊 `upgradeBuilding` 與特例判斷） |

### 11.3 要補的官方 Guide 頁面

Developing Your First Villages／Early Development Guide（兩村同步發展順序）｜Types of Capitals and Their Development（首都類型、皇宮、資源田上限）｜高盧種族頁（山洞、陷阱、商人）｜市場與商人（載重、速度、規則）｜開新村與文化點（拓荒者成本、門檻）。

### 11.4 要上傳的檔案（按 WP 需要時才傳）

`travian_agent.py`（B3）｜`travian_const.py`／`travian_models.py`（B1／B3）｜`village_log.py`、`travian_parser.py`、`scrape_and_log.py`（B2）｜`hide_troops.py`、`oasis_scan.py`、`oasis_check.py`（B4）｜`transfer_io.py`、`travian_transfer.py`、`hero_focus.py`、`stock_guard.py`、`fill_in.py`、`travian_hero.py`（B5）｜`auto_build.yml`、`requirements.txt`（B3、D-6）｜Apps Script 五檔、`triggerTravian` 所在檔、`travian_rules.md`（A4c、B6）｜新 Sheet 的 Config 初值與分頁清單（貼文字；A0、A1b、B2、B6）。

### 11.5 查證摘要（2026-10-25）

✓：第 2 村多半是未來首都、換首都＝蓋皇宮（官方新手指南）；高盧商人 750 載重／24 格／時（加速伺服器乘倍速）；NPC 商人只在英雄道具不夠時用；Sheets API 每分鐘每使用者 60 次寫入。
△：第 1 村為首都（很可能 true，遊戲內確認）；非首都資源田上限 10（Legends 現行數值遊戲內確認）；第 2 村需 2000 文化點（1 倍速）；高盧山洞 2 倍（來源為 Kingdoms／舊版手冊，實測）；「高盧低時間需求、前期防守便宜」出自社群網站、非官方。
✗：切村 `newdid`、切村是否黏著、來襲數帳號級或村級——靠 S2、S7。

### 11.6 新伺服器開局：要更新的資訊與安裝設定（v0.12）

**來源與限制**：只有一份舊伺服器（標題 `Asia 8`）的 dorf1 HTML，2026-10-26 05:59:57 UTC 抓取。它不是新伺服器；下列「舊頁看到的值」只當差異參考，**不得複製進新伺服器設定**（規則 9）。頁面內**沒有**伺服器主機名稱（連結全是相對路徑）、倍速、開服時間、新手保護天數。

**回答「ServerProfile 會在 Config 嗎」**：會。`server_id`、`server_base_url`、`server_tz`、`server_start_utc`（必填）與 `server_speed`、`server_map_half`、`server_protection_days`、`server_locale`（選填）都是 Config 的帳號級鍵（§6.4），由 `config_schema.profile_from_cfg`（A1b）組成 `ServerProfile`。不放 Villages（那是每村設定）。Cookie、帳密、Sheet 憑證**不放 Config**（D-17）。

#### A. ServerProfile 各欄：舊頁看到什麼、新伺服器怎麼取得

| 欄位（Config 鍵） | 舊頁看到的 | 新伺服器怎麼取得 | 狀態 |
|---|---|---|---|
| `server_id` | 標題 `Asia 8`（只是顯示名）；舊服主機 `ts8.x1.asia.travian.com`；伺服器唯一碼 `Travian.Constants.wuid`＝`f0c88000-b7ed-11f1-6808-000000000000`，與未登入頁註冊連結的 UUID 相同（✓） | 自訂穩定代號，建議用主機名稱；`wuid` 當身分核對（D-21）；session 快取綁 `server_id` | 舊＝主機 ✓；新 你定 |
| `server_base_url` | 舊服 `https://ts8.x1.asia.travian.com/`（✓ 使用者提供，並以未登入頁的登入連結驗證） | 新服從瀏覽器網址列或大廳登入連結複製，格式 `https://主機/`，不含路徑、不含 `?` | 舊 ✓；新 你貼 |
| `server_speed` | **`Travian.Variables.Speed = 1`**（`Variables.js`）✓；主機 `x1` 一致 | 新服讀自己的 `Variables.js`（S8，免登入）；主機 `x數字` 只當交叉檢查 | 舊＝1 ✓；新 讀 S8 |
| `server_map_half` | **`Travian.Variables.Map.Size`：left −200、right 200、bottom −200、top 200（401×401）**✓；與 `d=` 公式（`d = (map_half − y)×(2×map_half+1) + (x + map_half) + 1`，英雄村 d=109245、座標 (−28｜−72) 解得 200；v0.30 確認該 `d=` 出自集結點概覽，不在 dorf1／dorf2）互相印證 | 新服讀 S8 的 `Map.Size.right`；`d=` 公式只當交叉驗算：A1b 放進 `geo` 測試，A0b 用 S6 樣本一次性驗算，**執行期不抓**（D-18 v0.30） | 舊＝200 ✓；新 讀 S8 |
| `tribe` | `viewData.ownPlayer.tribeId = 3`；`Travian.Constants.TRIBE_ID`：roman 1、teuton 2、gaul 3（另有 nature 4…viking 9），`playableTribeIds` 只有 1～3 ✓ | 開局選高盧；`tribe_data` 加 `tribe_id`（1／2／3）；啟動檢查頁面 `tribeId` 必須相符（D-18） | ✓ |
| `server_start_utc` | 頁面沒有 | 大廳／公告的開服時間，換算成 UTC | 你貼 |
| `server_tz` | `Travian.Game.timeZone="Europe/London"`、`timezoneOffsetToUTC=0`、`timeFormat=0`（24 小時）；`#servertime` 標示 UTC；`Travian.Game.timestamp=1792994397` 就是 2026-10-26 05:59:57 UTC，與頁面顯示一致 ✓ | 新頁面同一段 script 再讀一次（檢視原始碼找 `Travian.Game.timeZone`）。**注意**：Europe/London 有夏令（2026-10-25 剛結束，下次 2027-03-28）；夏令期間頁面時間與 UTC 標籤怎麼顯示 ✗ 未驗證 | 舊＝Europe/London；新 ✗ |
| `server_protection_days` | 頁面沒有 | 遊戲規則／公告 | 你貼 |
| `version` | gpack 版號 `678.2`（CSS／JS 路徑與 `Strings.js?678.2`） | 新頁面同處讀取；版號變動→警告（版面可能改） | ✓ |
| `server_locale`（新） | `<html lang="zh-TW">`、`data-language="zh-TW"`、`/js/zh-TW/Strings.js` | 新伺服器帳號語言維持繁中；或 A2a 把 parsers 的中文字面全改成結構選擇器 | 新欄位 |

#### B. 頁面上可直接當資料源的東西（影響 A2a／B1 解析器設計）

1. **側欄的 `viewData`（JSON）**：`ownPlayer.village`、`villageList` 有村 id（舊頁 29786，也是 URL 的 `newdid`）、名稱、座標、人口、忠誠度、`tribeId`、`sortIndex`、`isSitter`；`culturalPointsOverview` 有已用村位、最多可控村數、下一村位進度與文化點日產；`goldFeatures` 有 Plus／Gold Club 是否啟用。→ `VillageRef`（C1）與 B1 的村莊清單優先讀這份 JSON，不解析 HTML。這份 query **沒有 `is_capital`**，維持 C1「讀不到＝null、以 Villages 為準」。
2. **頁內 script 的 `resources = {production, storage, maxStorage}`**：庫存、倉庫／穀倉容量、各資源產量都是數字 → `VillageSnapshot.stock／prod／cap_wh／cap_gr`。**穀物欄位（v0.26 依 2026-10-27 國際 11 dorf1 樣本回填）**：`production.l4`＝穀物平衡提示的值＝**淨產量**（樣本 −30，可為負）；`production.l5`＝頂欄「可用穀物」＝穀物提示「扣除建築物所需之後的生產力」＝**可用穀物**（樣本 7）。此樣本沒有出現舊頁的第三個數字（舊頁 325 對 320 的差異未重現）。✓ 僅限這一個樣本；`VillageSnapshot.prod[3]` 取 `l4`，`l5` 目前契約沒有欄位（見 D-23），A2a 仍用 S9 新服樣本再確認一次。
3. **時間**：建造倒數用 `timer` 元素的 `value`（秒，舊頁範例 6482）→ 直接得 `*_s`；絕對時間用 `Travian.Game.timestamp` 當「伺服器現在」。不要解析「07:47」這種 HH:MM 文字（驗算：05:59:57＋6482 秒＝07:47:59 ✓）。
4. **建造佇列**：每項有取消 id 與倒數；資源田連結 class `notNow` 表示佇列忙時不能升級。高盧無 Plus＝1 格，與 `queue_slots` 預設 1 相符（D-19 已定：不買 Plus，`queue_slots=1`）。**v0.26 樣本觀察（國際 11，`tribeId`＝6，非高盧）**：`goldFeatures.travianPlus.isActive`＝true，佇列同時有 2 筆建造中，即該帳號實際 2 格，與 D-19 的 `queue_slots=1` 不一致（v0.33：這是 Plus 人工開啟後 stage 加 1 的預期行為，沿用舊設計）；樣本另一點：資源田 17 買不起但沒有 `notNow`，與「`notNow`＝佇列忙」的解讀有出入，需「佇列空、資源足」與「佇列空、資源不足」各一份頁面對照（✗）。
5. **資源田版面**：舊村是 4 木 4 磚 4 鐵 6 穀，各格 gid 依村不同 → 不得寫死 aid→gid。
6. **英雄與切村**：`/hero`、`/hero/adventures`（按鈕顯示可冒險數）；英雄所在村連結帶 `newdid=`（部分佐證切村參數，**是否黏著仍待 S2 實測**）。
7. **伺服器功能旗標**：`serverSupportedFeatures.keepVidOnConquer=false`；`bootstrapData.buildings` 列出本服開放建築與種族限制（沒有 gid 12；gid 40 無種族＝不可建）→ A1b 的 `game_rules` 建築表可與這份比對（△）。

#### F. 舊服 S8 解析（`Variables.js`／`Constants.js`，使用者貼上；2026-10-26）

兩個檔未登入即可打開。結論：**倍速、地圖大小、伺服器唯一碼都能由 S8 直接讀**，不必從大廳猜；開服時間與新手保護天數仍不在內，要從大廳或公告取。

| 來源鍵 | 舊服值 | 用途／影響 |
|---|---|---|
| `Variables.Speed` | 1 ✓ | `server_speed` |
| `Variables.Map.Size` | −200～200（401×401）✓ | `server_map_half`＝right |
| `Constants.wuid` | `f0c88000-b7ed-11f1-6808-000000000000` ✓ | 伺服器唯一碼；比主機更適合核對身分（D-21） |
| `feature_flags.travelOverTheWorldEdge` | true | 地圖邊緣相連，`geo` 的 `wrap_delta`／`distance` 必須環繞（與卡片一致 ✓） |
| `feature_flags` 其餘 | territory、cities、boostedStart、tribesVikings、craftingItems、legendaryItems、governors、shards 皆 false；auctionsV2 true | 本服沒有這些功能，A 系列不處理 |
| `playableTribeIds`、`TRIBE_ID` | 可玩 1 羅馬／2 日耳曼／3 高盧 ✓ | `tribe_data.tribe_id` |
| `keepVidOnConquer`、`productionBoostPercent` | false、25 | 被佔村 id 會變（B 之後才用）；頁面「+25%」是付費生產加成 |
| `HERO_STATUS` | 在村 100、死亡 101、出擊攻擊 3／搶奪 4／增援 5、返回 9、躲避 40、冒險 50、被俘 102、駐守他村 103 | A2b `HeroState` 列舉直接用這組數值（40＝躲避，與躲兵有關） |
| `EVENT_TYPES` | attack 3、raid 4、forward 72 | B8 來襲與移動事件類型 |
| `VILLAGE_TYPE_*` | 普通 0、首都 1；綠洲 已佔 2、空 3 | 若地圖資料帶村型態，可補 `is_capital`（✗ 待樣本確認）；綠洲解析 free＝3 |
| `BUILDING_SLOT_*` | 集結點 aid 39、主建築 aid 26 | **aid 26 是主建築格，gid 26 是皇宮**（`BUILDING_IDS.palace`），不得混用 |
| `BUILDING_IDS` | market 17、barracks 19、stable 20、workshop 21、blacksmith 13、rallyPoint 16、greatBarracks 29、greatStable 30、townHall 24、residence 25、palace 26、commandCenter 44、trapper 36、herosMansion 37、hospital 46、asclepeion 48 | `game_rules` gid 表（A1b） |
| `TIME_FORMAT_MODE` | eu 0、us 1、uk 2、iso 3、acp 4 | 頁面 `timeFormat=0`＝eu（24 小時） |
| `MAX_CHARS_VILLAGE_NAME` | 20 | C1 `name` 上限 60 較寬，不衝突 |

**單位編號有兩套**（✓ 舊頁 `class="unit u21"`＝方陣兵、`u30`＝開拓者）：頁面圖示用**全域單位 id**（高盧 21～30）；集結點表單與 `TROOP_NUMBER_TYPES`（catapult `t8`、hero `t11`、tradeShip `t901`）用**種族內序號** `t1`～`t10`、英雄 `t11`（catapult＝t8 與高盧第 8 種兵相符）。換算：全域 id＝(tribe_id−1)×10＋序號（高盧 ✓；羅馬、日耳曼 △ 由 `troopIds` 1～30 推得）。C4 的 `u1`～`u10` 沒說是哪一套，容易混用 → D-21。

**意義待確認 ✗**：`TRADE_POPULATION_THRESHOLD=200`、`TRADE_OFFER_RATIO_LIMIT=1`（市場）；`TROOPS_MOVEMENT_SPEEDUP_DISTANCE=20`（名稱暗示距離超過 20 格後行軍加速，若成立 `geo.travel_seconds` 要分段計算；D 系列才用到）。

#### C. 舊伺服器專屬，新伺服器**不得沿用**

村 id 29786、座標 (−28｜−72)、村名、人口 295、文化點與村位數字、英雄（體力、經驗、冒險數）、金銀幣餘額、建築等級與兵力、Cookie 與 session 快取、舊 Sheet 全部分頁。

#### D. 開服當天安裝設定清單（依序）

1. 登入新伺服器、選高盧；從網址列記下主機；確認帳號語言為繁中（**未登入的頁面是英文**，語言跟著帳號；舊服未登入頁已實測為英文，登入後 `lang=zh-TW`）。〔你〕
2. 取 `ServerProfile` 各值（§11.6-A）：**倍速與地圖大小直接讀新服的 S8**（`Variables.js`／`Constants.js`，免登入）；`timeZone`／`timezoneOffsetToUTC`／`timeFormat`／`timestamp` 與 gpack 版號從登入後 dorf1 原始碼（S9）讀；開服時間、新手保護天數從大廳或公告；`d=` 公式只當地圖大小的交叉驗算。〔你；AI 協助驗算〕
3. 建新 Google Sheet（§6.3 模板）：Config、Villages（空，C6 欄位）、Actions（10 欄）、state、Sheet1、Fields、Buildings、Buildable、Changes、Oases、Market、Transit、goals、build_order、advice、log；格式依 D-15；分享給 bot 使用的 Google 服務帳號（△ 舊程式用 `get_credentials`，帳號型態 A4a 讀碼確認）。
4. **（v0.19）Apps Script 觸發器維持開著（GitHub schedule 會漏跑，A-7）；新服用新名稱的 Secrets（草案 `TRAVIAN_SEED_COOKIE_S2`、`GOOGLE_SHEET_ID_S2`；`GOOGLE_SERVICE_ACCOUNT_JSON` 可沿用；正式名稱 A4a 定案），不覆蓋舊名稱。** 新 Sheet ID、帳密／Cookie 放 GitHub Secrets；D-17 已定；Secrets 名稱仍待 A4a 回填。舊 workflow 若仍跑舊伺服器，不要覆蓋同名 Secrets。
5. 新 Config 初值（不從舊 Sheet 複製）：`server_*`、`server_locale=zh-TW`、`tribe=gaul`、`schema_version=1`、所有 mode 鍵 `off`；`main_did`／`main_did_set_utc` 留空（`village_lock` 第一次執行才記錄，那時帳號只有一個村）。
6. 新 session：用新 Cookie 建；快取檔內 `server_id` 必須等於 Config 的值，舊快取一律丟棄；Actions cache key 換新。
7. `auto_build.yml`：A0 **不改、不啟用排程**（規則 12：GA 前 bot 不 live）；A6b 才換入口。
8. 抓樣本 S3、S6（概況要有部隊與無部隊兩份，見 §11.2）、S8、S9、S10、S11（G0 可抓），`scrub_sample.py` 脫敏後放 `tests/samples/`，每檔配 `.meta.json`。
9. 啟動檢查（D-18 通過後在 A1b／A6b 實作）：Config 與頁面實值比對，不符＝hold。
10. ~~重跑欠債測試並貼結果~~（v0.17 取消，見 A-6）。

#### E. 仍 ✗（開服後補）

新服主機、開服時間、保護天數（大廳／公告）、夏令期頁面時間顯示、穀物三個數字的意義、`TRADE_POPULATION_THRESHOLD`＝200 與 `TROOPS_MOVEMENT_SPEEDUP_DISTANCE`＝20 的實際規則（§11.6-F）；倍速與地圖大小改由新服 S8 直接讀。


---

## 12. 風險

| 風險 | 緩解 |
|---|---|
| 切村造成請求打錯村（與你手動操作競爭） | 每個請求帶 did＋`assert_active`；不符就跳過該村 |
| 運資源重複送出（不可逆；在途貨沒算進缺口） | 快照含在途貨；`Transit` 紀錄；每輪上限；失敗不重試 |
| 資源集中在易被搶的村 | D-4 政策；先 dry 看決策 |
| 逾時 | B3 實測後調整；輪替處理 |
| 請求量增加（自動化合規請你自行評估） | 縮短不必要抓取、保留隨機等待 |
| 帳號級 `disable()` 關全部 | B4 村級錯誤隔離 |
| 契約／格式漂移（不同 AI 各用各的寫法） | §6 契約升版＋§10 紀錄；`serialize`／`schema` 單一出口；`check_arch`／`check_contracts`；Sheet 欄只追加 |
| 誤用舊伺服器 Cookie 或資料 | 快取綁 `server_id`，不符整份丟棄；遊戲狀態不從舊 Sheet 帶過來 |
| 種族寫死 | `check_arch` 字串檢查＋種族煙霧測試；種族資料只經 `TribeSpec` |
| Gemini 產出壞的 `build_order` | `plan_validate`＋hold；不套預設、不快取；GA 以壞檔實測 |
| 新服語言或時區與 Config 不符（解析錯位、時間差 1 小時） | `server_locale`、`server_tz` 與頁面實值啟動比對（D-18）；時間優先用 `timer value` 與 epoch；夏令切換日（2027-03-28）特別檢查 |
| 新舊伺服器 Secrets 混用（舊 workflow 打到新服或反之） | D-17：新 Secrets 另名；A0 不啟用排程；session 快取綁 `server_id` |
| 單位編號兩套混用（全域 id 21～30 vs 種族內序號 t1～t10） | 契約只用種族內序號；換算只在 `tribe_data`；`test_tribe_switch` 加高盧 u21＝序號 1 的斷言（D-21） |
