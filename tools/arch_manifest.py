"""arch_manifest.py  v0.1  (A1a-3)

用途：73 張模組卡片的機器可讀登記表，與主檔 §4.2 同源。本檔由 tools/make_manifest.py 轉出，
      §4.2 有變動請改主檔後重新轉出，不要手改本檔。
依賴：無（純資料）。
部署狀態：僅供 tools/check_arch.py 與測試使用，不在 bot 執行路徑上。

每項鍵：
  id    卡片 ID（cm-/ps-/dm-/if-/ac-/ap-）
  path  相對 travian_bot/ 的檔案路徑
  layer common／parsers／domain／infra／actions／app
  deps  依賴的卡片 ID list
  wp    交付的 WP（含「／」者＝多個 WP 接力，第一個為首次交付）
  disp  處置：沿用／拆／改寫／新寫（依「舊源→處置」欄最後的粗體字分類；僅供參考，不參與檢查）
"""

SOURCE = 'multi-village-dev-v0_54.md v0.54 §4.2'
EXPECTED_COUNT = 73

MANIFEST = [
    {'id': 'ac-01', 'path': 'actions/village_switch.py', 'layer': 'actions', 'deps': ['if-02', 'ps-02', 'cm-03'], 'wp': 'A5b／B1', 'disp': '新寫'},
    {'id': 'ac-02', 'path': 'actions/build_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-01', 'ps-03', 'cm-02', 'cm-04'], 'wp': 'A5a', 'disp': '沿用'},
    {'id': 'ac-03', 'path': 'actions/item_transfer_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-05', 'cm-02', 'cm-04'], 'wp': 'A5a', 'disp': '拆'},
    {'id': 'ac-04', 'path': 'actions/focus_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-05', 'cm-02', 'cm-04'], 'wp': 'A5a', 'disp': '拆'},
    {'id': 'ac-05', 'path': 'actions/hero_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-05', 'cm-02', 'cm-04'], 'wp': 'A5a', 'disp': '沿用'},
    {'id': 'ac-06', 'path': 'actions/hide_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-06', 'cm-02', 'cm-04', 'cm-05'], 'wp': 'A5b', 'disp': '拆'},
    {'id': 'ac-07', 'path': 'actions/oasis_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-08', 'ps-09', 'cm-09'], 'wp': 'A5b', 'disp': '沿用'},
    {'id': 'ac-08', 'path': 'actions/market_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-07', 'cm-01', 'cm-02', 'cm-04'], 'wp': 'C3', 'disp': '新寫'},
    {'id': 'ac-09', 'path': 'actions/troop_exec.py', 'layer': 'actions', 'deps': ['if-02', 'ps-06', 'cm-01', 'cm-02', 'cm-04'], 'wp': 'D2', 'disp': '新寫'},
    {'id': 'ap-01', 'path': 'app/main.py', 'layer': 'app', 'deps': ['if-01', 'if-02', 'if-05', 'if-06', 'cm-08', 'cm-13', 'ps-01', 'ps-02', 'ap-02', 'ap-08'], 'wp': 'A6b', 'disp': '拆'},
    {'id': 'ap-02', 'path': 'app/run_context.py', 'layer': 'app', 'deps': ['if-02', 'if-05', 'if-07', 'if-08', 'if-09', 'if-10', 'cm-01', 'cm-09'], 'wp': 'A6a1', 'disp': '新寫'},
    {'id': 'ap-03', 'path': 'app/stage_base.py', 'layer': 'app', 'deps': ['ap-02', 'cm-01', 'cm-04'], 'wp': 'A6a1', 'disp': '新寫'},
    {'id': 'ap-04', 'path': 'app/registry.py', 'layer': 'app', 'deps': ['ap-03'], 'wp': 'A6a1', 'disp': '新寫'},
    {'id': 'ap-05', 'path': 'app/observe.py', 'layer': 'app', 'deps': ['ap-02', 'if-02', 'ps-01', 'ps-03', 'ps-04', 'if-09', 'if-08', 'cm-01', 'cm-09', 'cm-12'], 'wp': 'A6a1', 'disp': '拆'},
    {'id': 'ap-06', 'path': 'app/formatting.py', 'layer': 'app', 'deps': ['cm-05'], 'wp': 'A6a1', 'disp': '沿用'},
    {'id': 'ap-07', 'path': 'app/village_cycle.py', 'layer': 'app', 'deps': ['ap-05', 'ap-04', 'ap-03', 'dm-09', 'ac-01', 'cm-01'], 'wp': 'A6b', 'disp': '拆'},
    {'id': 'ap-08', 'path': 'app/orchestrator.py', 'layer': 'app', 'deps': ['ap-07', 'ap-04', 'ap-03', 'if-05', 'if-03', 'cm-01', 'cm-05'], 'wp': 'A6b／B3', 'disp': '新寫'},
    {'id': 'ap-10', 'path': 'app/stages/build.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'dm-12', 'dm-01', 'ac-02', 'if-12', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '拆'},
    {'id': 'ap-11', 'path': 'app/stages/item_transfer.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'dm-05', 'ac-03', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '拆'},
    {'id': 'ap-12', 'path': 'app/stages/focus.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'dm-04', 'ac-04', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '拆'},
    {'id': 'ap-13', 'path': 'app/stages/fill_in.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'dm-02', 'ac-02', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '拆'},
    {'id': 'ap-14', 'path': 'app/stages/guard.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'dm-03', 'ac-02', 'ac-03', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '拆'},
    {'id': 'ap-15', 'path': 'app/stages/hide.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'ps-06', 'dm-07', 'dm-08', 'ac-06', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '改寫'},
    {'id': 'ap-16', 'path': 'app/stages/oasis.py', 'layer': 'app', 'deps': ['ap-03', 'ac-07', 'if-10', 'cm-01', 'cm-09'], 'wp': 'A6a2', 'disp': '改寫'},
    {'id': 'ap-17', 'path': 'app/stages/hero.py', 'layer': 'app', 'deps': ['ap-03', 'ap-06', 'dm-06', 'ac-05', 'if-07', 'cm-02'], 'wp': 'A6a2', 'disp': '沿用'},
    {'id': 'ap-18', 'path': 'app/stages/market.py', 'layer': 'app', 'deps': ['ap-03', 'ap-05', 'dm-10', 'ac-08', 'if-11', 'if-07', 'cm-01'], 'wp': 'C4', 'disp': '新寫'},
    {'id': 'ap-19', 'path': 'app/stages/troops.py', 'layer': 'app', 'deps': ['ap-03', 'ap-05', 'dm-11', 'ac-09', 'if-07', 'cm-01'], 'wp': 'D2', 'disp': '新寫'},
    {'id': 'cm-01', 'path': 'common/models.py', 'layer': 'common', 'deps': ['cm-11', 'cm-10'], 'wp': 'A1a-2', 'disp': '新寫'},
    {'id': 'cm-02', 'path': 'common/decisions.py', 'layer': 'common', 'deps': ['cm-01'], 'wp': 'A1a-2', 'disp': '新寫'},
    {'id': 'cm-03', 'path': 'common/constants.py', 'layer': 'common', 'deps': [], 'wp': 'A1a-1', 'disp': '沿用'},
    {'id': 'cm-04', 'path': 'common/modes.py', 'layer': 'common', 'deps': [], 'wp': 'A1a-1', 'disp': '沿用'},
    {'id': 'cm-05', 'path': 'common/clock.py', 'layer': 'common', 'deps': ['cm-10', 'cm-13'], 'wp': 'A1b', 'disp': '沿用'},
    {'id': 'cm-06', 'path': 'common/tribe_data.py', 'layer': 'common', 'deps': ['cm-11'], 'wp': 'A1b', 'disp': '沿用'},
    {'id': 'cm-07', 'path': 'common/geo.py', 'layer': 'common', 'deps': [], 'wp': 'A1b', 'disp': '沿用'},
    {'id': 'cm-08', 'path': 'common/config_schema.py', 'layer': 'common', 'deps': ['cm-01', 'cm-04', 'cm-06', 'cm-10', 'cm-11', 'cm-12', 'cm-13'], 'wp': 'A1b／B2', 'disp': '沿用'},
    {'id': 'cm-09', 'path': 'common/parsed.py', 'layer': 'common', 'deps': ['cm-01'], 'wp': 'A1a-2', 'disp': '新寫'},
    {'id': 'cm-10', 'path': 'common/serialize.py', 'layer': 'common', 'deps': [], 'wp': 'A1a-1', 'disp': '新寫'},
    {'id': 'cm-11', 'path': 'common/schema.py', 'layer': 'common', 'deps': [], 'wp': 'A1a-1', 'disp': '新寫'},
    {'id': 'cm-12', 'path': 'common/game_rules.py', 'layer': 'common', 'deps': ['cm-01'], 'wp': 'A1b', 'disp': '沿用'},
    {'id': 'cm-13', 'path': 'common/server_profile.py', 'layer': 'common', 'deps': ['cm-01', 'cm-09'], 'wp': 'A1a-2', 'disp': '新寫'},
    {'id': 'dm-01', 'path': 'domain/build_planner.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09', 'cm-03'], 'wp': 'A3a', 'disp': '改寫'},
    {'id': 'dm-02', 'path': 'domain/fill_in.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09', 'cm-03'], 'wp': 'A3a', 'disp': '沿用'},
    {'id': 'dm-03', 'path': 'domain/guard.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-04'], 'wp': 'A3a', 'disp': '沿用'},
    {'id': 'dm-04', 'path': 'domain/focus.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09'], 'wp': 'A3b', 'disp': '拆'},
    {'id': 'dm-05', 'path': 'domain/item_transfer.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09'], 'wp': 'A3b', 'disp': '拆'},
    {'id': 'dm-06', 'path': 'domain/adventure.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09'], 'wp': 'A3b', 'disp': '拆'},
    {'id': 'dm-07', 'path': 'domain/hide_plan.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-07', 'cm-06'], 'wp': 'A3c', 'disp': '改寫'},
    {'id': 'dm-08', 'path': 'domain/hide_decide.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09'], 'wp': 'A3c', 'disp': '沿用'},
    {'id': 'dm-09', 'path': 'domain/village_lock.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02'], 'wp': 'A3c', 'disp': '新寫'},
    {'id': 'dm-10', 'path': 'domain/market_plan.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-06', 'cm-07'], 'wp': 'C2', 'disp': '新寫'},
    {'id': 'dm-11', 'path': 'domain/troop_plan.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-06', 'cm-07'], 'wp': 'D2', 'disp': '新寫'},
    {'id': 'dm-12', 'path': 'domain/plan_validate.py', 'layer': 'domain', 'deps': ['cm-01', 'cm-02', 'cm-09', 'cm-03', 'cm-12'], 'wp': 'A3a', 'disp': '新寫'},
    {'id': 'if-01', 'path': 'infra/session.py', 'layer': 'infra', 'deps': ['cm-03', 'cm-01', 'cm-10'], 'wp': 'A4a', 'disp': '沿用'},
    {'id': 'if-02', 'path': 'infra/gateway.py', 'layer': 'infra', 'deps': ['cm-03', 'cm-01'], 'wp': 'A4a／B1', 'disp': '拆'},
    {'id': 'if-03', 'path': 'infra/notify.py', 'layer': 'infra', 'deps': [], 'wp': 'A4a', 'disp': '沿用'},
    {'id': 'if-04', 'path': 'infra/store/gsheets.py', 'layer': 'infra', 'deps': [], 'wp': 'A4a', 'disp': '沿用'},
    {'id': 'if-05', 'path': 'infra/store/config_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-08'], 'wp': 'A4b', 'disp': '拆'},
    {'id': 'if-06', 'path': 'infra/store/village_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-01'], 'wp': 'A4b／B2', 'disp': '新寫'},
    {'id': 'if-07', 'path': 'infra/store/action_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-01'], 'wp': 'A4b／B2', 'disp': '沿用'},
    {'id': 'if-08', 'path': 'infra/store/state_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-01'], 'wp': 'A4b／B2', 'disp': '改寫'},
    {'id': 'if-09', 'path': 'infra/store/snapshot_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-01'], 'wp': 'A4b／B2', 'disp': '拆'},
    {'id': 'if-10', 'path': 'infra/store/oasis_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-09'], 'wp': 'A4b／B2', 'disp': '改寫'},
    {'id': 'if-11', 'path': 'infra/store/market_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-01', 'cm-09', 'cm-02'], 'wp': 'C1', 'disp': '新寫'},
    {'id': 'if-12', 'path': 'infra/store/plan_repo.py', 'layer': 'infra', 'deps': ['if-04', 'cm-01', 'cm-11'], 'wp': 'A4b', 'disp': '新寫'},
    {'id': 'ps-01', 'path': 'parsers/village.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-03', 'cm-11'], 'wp': 'A2a-2a', 'disp': '沿用'},
    {'id': 'ps-02', 'path': 'parsers/village_list.py', 'layer': 'parsers', 'deps': ['cm-01', 'cm-03', 'cm-11'], 'wp': 'A2a-1／B1', 'disp': '沿用'},
    {'id': 'ps-03', 'path': 'parsers/buildings.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-03', 'cm-11'], 'wp': 'A2a-2b', 'disp': '沿用'},
    {'id': 'ps-04', 'path': 'parsers/player.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-11'], 'wp': 'A2a-1', 'disp': '沿用'},
    {'id': 'ps-05', 'path': 'parsers/hero.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-03', 'cm-11'], 'wp': 'A2b', 'disp': '沿用'},
    {'id': 'ps-06', 'path': 'parsers/rally.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-03', 'cm-11'], 'wp': 'A2b／D1', 'disp': '沿用'},
    {'id': 'ps-07', 'path': 'parsers/market.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-03'], 'wp': 'C1', 'disp': '新寫'},
    {'id': 'ps-08', 'path': 'parsers/oasis.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-03', 'cm-11'], 'wp': 'A2b', 'disp': '沿用'},
    {'id': 'ps-09', 'path': 'parsers/tile.py', 'layer': 'parsers', 'deps': ['cm-09', 'cm-11'], 'wp': 'A2b', 'disp': ''},
]
