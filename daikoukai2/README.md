# SFC 大航海時代II 解析

KOEI，1993，SFC（HiROM 2 MB，無 header）。沒有劇本，遊戲開始時從 6 位主角（人物 0–5）擇一。文字是半形假名（JIS X 0201，平假名／片假名用 ESC 切換）加上 2-byte 字型碼（1631 字，`data/charset.txt`）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python daikoukai2/export.py [--rom ROM] [--out DIR]          # → daikoukai2/output/（CSV、XLSX、PNG），約 3 秒
.venv/bin/python daikoukai2/export_kaodata.py --out <kaodata>/data-local/daikoukai2-sfc
.venv/bin/python daikoukai2/verify_kaodata_export.py --dataset <kaodata>/data-local/daikoukai2-sfc
.venv/bin/python daikoukai2/verify_scenarios.py              # 約 25 秒
.venv/bin/python daikoukai2/verify_persons.py [--quick]      # 約 3 分鐘
.venv/bin/python daikoukai2/verify_faces.py [--quick]        # 約 4 分鐘
.venv/bin/python daikoukai2/verify_maps.py                   # 約 2 分鐘
.venv/bin/python daikoukai2/tools/session.py ROM OUT "steps" [--state IN.mss] [--save]   # 手動操作／截圖／dump
```

- ROM 預設直接讀 `roms/Daikoukai Jidai II (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0xA0EF`，派遣服務 0x4C）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字與字型、初始狀態區塊、人物、VIP、女性、艦隊、船種、港與港的狀態、道具、發見物、字串表、頭像（專屬＋組合臉）、世界地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `daikoukai2-sfc`（專屬頭像 128 張＋組合臉 7 包） |
| `verify_kaodata_export.py` | 資料集用參考渲染器（`tools/kaodata.py`）畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 初始狀態區塊（選主角畫面的 WRAM）與 ROM 逐 byte 比對；6 位主角的開始設定 |
| `verify_persons.py` | 120 人逐一寫進ジョアン的紀錄，打開「人物情報」畫面讀回能力、年齡、等級、經驗、頭像、名字與國籍 |
| `verify_faces.py` | 128 張專屬頭像＋62 種組合臉碼逐一換進ジョアン的頭像欄，比對遊戲寫進 VRAM 的 tile 與調色盤 |
| `verify_maps.py` | 出港後往 5 個方向航行，比對 BG2 tilemap、tile、調色盤、遊戲解壓的地圖區塊；130 港的座標落在港口圖示上 |
| `tools/replay.py` | 驗證用：開機玩到某處後建 savestate，每回合讀回 savestate、寫 WRAM、按鍵，回傳 WRAM／VRAM／CGRAM／OAM |
| `tools/session.py` | 按鍵序列語法（`a:10 w40 up+a`）與單次操作／截圖的命令列工具 |
| `data/charset.txt` | 字型碼 `0x8140–0x879E` 對應的字（1631 字） |

## 輸出（`daikoukai2/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 120 人：姓名、類別（主角 0–5／仲間 6–68／劇情人物 69–78／提督 79–119，依編號範圍）、7 項能力（統率力 航海術 知識 直感 勇気 剣技 魅力）、年齡、航海／戰鬥等級與經驗、國籍、頭像碼、母港（推測）、未解欄位 |
| `heroes.csv` | 6 位主角：能力、國籍、開始艦隊 |
| `vips.csv` | 20 位 VIP（王、商人等）：名前、頭像（推測）、所在港（推測）、未解欄位 |
| `women.csv` | 30 位女性：名前、年齡（推測）、所在港（推測） |
| `fleets.csv`、`fleet_ships.csv` | 71 艦隊：提督、母港、啟用、座標、未解欄位；419 艘船的 9 byte 原始值與船種（推測） |
| `ship_types.csv` | 25 船種：名稱、編號、規格 12 byte（意義大多未解） |
| `ports.csv` | 130 港（交易港 100、補給港 30）：座標（地圖格）、國籍；交易港的經濟／工業／各國占有率（推測）、地域、販售道具（推測） |
| `goods.csv` | 46 種交易品與分類 |
| `items.csv` | 100 種道具：分類、價格（推測）、說明 |
| `discoveries.csv` | 100 個發見物：名稱、說明 |
| `strings.csv` | 其他字串表（國名、砲、階級、技能、木材、船首像、爵位、名字池、建築等 321 筆） |
| `daikoukai2.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/`、`packs/` | 每人頭像（`000_ジョアン・フェレロ.png`，組合臉已組好）；專屬頭像 000–127；7 包組合臉原圖 |
| `world_map.png` | 世界地圖 2160 × 1080（每格一點，取 tile 平均色） |
| `world_map_ports.png` | 放大 2 倍並標上 130 港（紅＝交易港、黃＝補給港） |
| `world_map_mediterranean.png` | 地中海一帶（格 x 40–480、y 150–450）原尺寸 tile 渲染 |
| `font.png` | 1631 字的字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）、文字編碼、字型 1631 字
- ✓ 初始狀態區塊：開機時整塊複製到 WRAM（人物、VIP、女性、艦隊、船種、港、港的狀態都在裡面）
- ✓ 人物 120 人：姓名、7 項能力、年齡、等級、經驗、國籍、頭像碼
- ✓ 6 位主角的開始設定（母港、開始艦隊）
- ✓ 頭像：專屬 128 張＋組合臉 7 包（上半臉、下半臉、部件 A、部件 B）；kaodata 資料集 `daikoukai2-sfc`
- ✓ 世界地圖：90 × 45 區塊 × 12 × 12 metatile、tile 編號規則（海岸遮罩、緯度帶）、tile 與調色盤；130 港的座標
- ✓ 船種名稱、交易品、道具、發見物、各種字串表
- … 推測：VIP／女性的欄位、港的經濟／工業／占有率、道具價格、船的 9 byte 中的船種
- … 未解：海戰畫面（戰術地圖）、地圖調色盤組的選擇規則、船種規格、交易品價格、多個未知欄位（ROM_FORMAT.md §12）

## 驗證

| 腳本 | 內容 | 結果（實測） | 耗時 |
|------|------|------|------|
| `verify_scenarios.py` | 選主角畫面 WRAM `$7E:2000–$8EEE` 與 ROM `0x8780D` 逐 byte 比對；6 位主角各選一次，看 `$7E:25FB`（主角）、`$7E:2016`（母港）、開始艦隊的啟用旗標、人物紀錄 | 0 byte 不同；6/6 OK（母港 リスボン セビリア ロンドン アムステルダム ジェノヴァ イスタンブール） | 23 秒 |
| `verify_persons.py` | 120 人各自寫進 `$7E:25FC`，開「人物情報」，從 BG3 數字 tile 讀回 7 能力、年齡、等級、經驗；頭像 VRAM／CGRAM；名字與國籍的假名 tile 一對一；海賊的國籍是 2 個漢字，比對字形 | 能力／年齡／等級經驗／頭像 各 120/120、海賊 17/17、名字與國籍 77 字 ↔ 77 tile 一對一、ALL OK | 2 分 42 秒 |
| `verify_faces.py` | 頭像碼寫進ジョアン的 +26，開「人物情報」，比對 VRAM `0x3800` 的 960 bytes 與 CGRAM 調色盤 10 | 專屬 128/128、組合 62/62（人物用到的 54 種＋每包各 1 種合成碼）、ALL OK | 3 分 47 秒 |
| `verify_maps.py` | 在ジョアン的艦隊放一艘船，出港後往左／下／上／左下／左上航行 1500 frame；比對 BG2 tilemap（對 `Rom.map_tile`）、VRAM tile、CGRAM 調色盤 2–5、遊戲解壓的每個區塊；港座標 | tilemap 896/896 × 5 回合、tile OK、調色盤 OK、區塊 30/30（13 個含陸地）、港 130/130、ALL OK | 1 分 38 秒 |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_rgb` 逐 pixel 比對、checksums | 人物 120/120、專屬 128/128、checksums OK | 0.3 秒 |

`verify_persons.py` 的海賊數字依實際人物數計算（國籍 6 的人數）。人物基本表、船種名、港名等都由遊戲本身的程式顯示或使用；未經畫面驗證的欄位在 CSV 欄名標「推測」或「未解」。
