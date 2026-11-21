# A2b 新增樣本（測試帳號、原始頁、未脫敏；2026-11-07 前後抓取）

來源：舊服 Asia 8（zh-TW，帳號 doga／doga2）與 International 11（埃及，WoodViking）；皆為測試帳號，依 A-11⑦ 不脫敏。
`checksum` 是 token：若日後樣本來自正式帳號，入庫前要換成 000000（`tools/scrub_sample.py`）。

| 檔案 | 原檔名 | 內容 | 供誰使用 |
|---|---|---|---|
| S18a_adventure_raw_asia8_return | Asia_8英雄任務 | 冒險頁原始 HTML，status 9（返回），18 筆冒險 | ps-05 |
| S18b_adventure_raw_asia8_return | Asia_8冒險頁 | 冒險頁原始 HTML，status 9，17 筆，體力 24% | ps-05 |
| S18c_adventure_raw_i11_going | International_11英雄離村 | 冒險頁原始 HTML，status 50（去冒險），1 筆 | ps-05 |
| S18d_adventure_dom_asia8_table | heromission | 渲染後 `#heroAdventure` 的 **DOM 片段**（無 timestamp、無 viewData；與 S18a 同一時間的 18 列表格）。只用於表格核對：測試把它塞進 S18a 的空 `#heroAdventure` 組成 `page.content()` 的樣子 | ps-05 |
| S6a～S6c | Asia_8部隊概況／Asia_8英雄出任務回來／Asia_8概況 | 集結點概況，英雄冒險返回中（`inReturn`），本村在家有兵 | ps-06 |
| S6d、S6e | 英雄出發綠洲集結點／International_11英雄出發集結點概況 | 概況，英雄單獨搶奪綠洲中（`outRaid`、`inRaid`×2、`inAttack`×1），本村在家全 0；兩份相隔 29 秒 | ps-06 |
| S6f | International_11英雄離村1 | 概況，英雄去冒險中（`outHero`、`inRaid`×5），本村在家全 0 | ps-06 |
| S17a～S17c | Asia_8_確認_增援／正常攻擊／攻擊搶奪 | 送兵第二步確認頁，`eventType` 5／3／4，10 個 t1 | ps-06 |
| S17d | 英雄出發綠洲 | 確認頁，英雄單獨掠奪綠洲（`eventType` 4、`villagename` 空） | ps-06 |
| S17e | I11_heroathome | 第一步送兵表單（英雄在家，由綠洲掠奪連結進來）；A2b 只當「不是概況頁」的反例與 HUD 在家樣本 | ps-05／06 |
| S17f、S17g | International_11英雄出發頁面／…頁面確認 | 第一步表單：S17f 由綠洲連結進來（x／y 預填、eventType 5／3 disabled）；S17g（原檔名「確認」有誤導）是沒帶目標的普通表單。**A2b 不解析**，留給 D2 | — |
| S16_block_asia8.json | MAP.json | 區塊 JSON，249 格（32 個綠洲）。**原檔是 cp950（Big5）編碼，已無損轉成 UTF-8**（地形格標題是中文字面「森林」等，ps-08 忽略） | ps-08 |

| S15a_tile_oasis_free_empty | map_NN | tile-details 的 html 欄（`div#tileDetails` 片段，CRLF 原樣），未佔領綠洲 (−19｜−88)，動物表「無」，3 筆佔領事件 | ps-09 |
| S15b_tile_oasis_free_animals | map_NY | 未佔領綠洲 (−26｜−85)，野豬 5／野狼 4／灰熊 3，報告分頁有 1 筆 | ps-09 |
| S15c_tile_oasis_taken | map_YN | 已佔領綠洲 (−18｜−78)，持有人／公會／村莊連結，沒有動物表 | ps-09 |

（三份 S15 皆舊服 zh-TW；`#village_info`、`#distribution`、`#distance`、`#troop_info` 的結構與 v0.46 描述一致。）
