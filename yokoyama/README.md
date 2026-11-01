# SFC 横山光輝 三国志 解析

エンジェル（バンダイ），1992，SFC（LoROM 1 MB，Rev 0 與 Rev 1）。不是光榮的作品，資料格式全部自成一套（自訂 16-bit 字碼、LZSS、sprite 組合頭像、mode 7 大地圖）。劇本 2（189 年、219 年）、人物 224、國 31、勢力 15 格（189 年 14 個、219 年 3 個）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python yokoyama/export.py [--rom ROM] [--out DIR]       # → yokoyama/output/（CSV、XLSX、PNG）
.venv/bin/python yokoyama/tools/charset_sheet.py                  # → yokoyama/output/charset_sheet.png
.venv/bin/python yokoyama/verify_scenarios.py                     # 約 35 秒
.venv/bin/python yokoyama/verify_persons.py                       # 約 8 分鐘（兩個劇本平行）
.venv/bin/python yokoyama/verify_countries.py                     # 約 1 分鐘
.venv/bin/python yokoyama/verify_faces.py                         # 約 8 分鐘
.venv/bin/python yokoyama/verify_text.py                          # 約 1.5 分鐘
.venv/bin/python yokoyama/verify_maps.py                          # 約 40 秒
.venv/bin/python yokoyama/verify_lz.py                            # 約 1 分鐘
```

- ROM 預設直接讀 `roms/Yokoyama Mitsuteru Sangokushi (Japan).zip`（Rev 0）；`--rom "roms/Yokoyama Mitsuteru Sangokushi (Japan) (Rev 1).zip"` 讀 Rev 1，`--rom` 也接受 .sfc。兩版共用同一份解碼（Rev 1 往後移的表由 `Rom._find` 從程式碼找）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。字型核對圖用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。一個 process 只能開一次 Mesen，兩個劇本開機序列不同的腳本（`verify_persons.py`、`verify_countries.py`）會自己開兩個子程序平行跑（`--scenario 0|1` 只跑一個）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與文字、名表與讀音、劇本載入（人物／配置／國／勢力 → WRAM）、國名／讀音／位置、頭像（部件、metasprite、調色盤）、LZSS、大地圖（mode 7 VRAM、城標記、各月調色盤）、地形格 |
| `data/charset.txt` | 字表：字碼 0x100–0x63F → 字元（16 字一行，`#` 開頭是註解） |
| `tools/sequences.py` | 按鍵序列（劇本選擇、兩劇本第一個月的地圖、情報→武将／国）、游標寫入、攔 `$00:8D60` 字碼與攔劇本載入的 Lua |
| `tools/charset_sheet.py` | 字型核對圖：每個字碼的 ROM 字形與字表的字元並排 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `parts_manifest.py` | portrait-sheet/1 manifest：頭像零件 407 個（11 種各一區，畫在臉框原位置，副名是使用人數，只有 1 人用的寫那個人），交給 simagame |
| `sheet_manifest.py` | portrait-sheet/1 manifest（武將頭像 224 張，兩劇本都不在的任双標 unseen，交給 simagame 做頭像 sheet） |
| `verify_scenarios.py` | 2 劇本 × 3 難易度：劇本載入後 WRAM 人物／國／勢力區塊與 `Rom.scenario_wram` 逐 byte 比對 |
| `verify_persons.py` | 人物 224 × 2 劇本：逐一移進玩家的國，開武將詳細畫面，攔 `$00:8D60` 的字碼 |
| `verify_countries.py` | 國 31 × 2 劇本：游標寫到各國位置，開國的情報畫面，攔字碼 |
| `verify_faces.py` | 頭像 224：武將詳細畫面的 OAM／VRAM／CGRAM 畫出來，和 `Rom.face_rgb` 逐 pixel 比對 |
| `verify_text.py` | 字碼 0x100–0x5FF：換進訊息字串，比對 `$00:8D60` 讀字型的位置 |
| `verify_maps.py` | 大地圖：VRAM 0x0000–0x7FFF（含城標記）、地圖調色盤、視窗調色盤列 |
| `verify_lz.py` | 開機到第一個月地圖之間遊戲解壓的 20 個串流，和 `rom.lz` 比對大小與 checksum |

## 輸出（`yokoyama/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 人物 224：姓名、讀音、頭像部件 11 個、兩劇本的配置 |
| `scenario_persons.csv` | 2 劇本 × 224：配置（種類、國、關係人物、登場年、原始值）、開局所屬勢力、体力 攻撃力 兵法力 政治力 忠誠度 人徳 経験値 レベル 統率力 兵数 士気 機動力、武器力 騎 弓 歩、部隊攻撃力、原始 14 bytes |
| `countries.csv` | 國 31：國名、讀音、地圖位置（地形格座標） |
| `scenario_countries.csv` | 2 劇本 × 31：勢力、太守、金、米、民、収穫高、産業値、統治度、防災値、税率、城塞値、原始 16 bytes |
| `factions.csv` | 各劇本存在的勢力：君主、國數、國 |
| `terrain.csv` | 地形 8 種：名稱、移動等級、格數 |
| `yokoyama.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 224 人的頭像 48 × 64（`161_田豊.png`，透明背景）與總覽 |
| `map.png` | 大地圖 1024 × 1024（bank `$19`，不含城標記；1 月、縮小顯示時的調色盤加視窗色） |
| `map_189.png`、`map_219.png` | 兩劇本開局的城標記與城框 |
| `terrain.png` | 64 × 64 地形格依種類上色疊在地圖上 |
| `charset_sheet.png` | 字型核對圖（`tools/charset_sheet.py`） |

## 進度

- ✓ 字碼：16-bit、16 × 16 全形 1024 字與 8 × 16 半形 256 字、控制碼 F1–F9；字表人工判讀（Rev 1 的 0x342 褚）
- ✓ 名表 224（姓、第二字、名、讀音）
- ✓ 劇本 2：載入程式（`$01:D4A9`）的人物 224 × 14、配置 224 × 5、國 31 × 16、勢力君主 15，WRAM 紀錄格式；難易度 1 的金米 × 1.6
- ✓ 人物 14 bytes 全部欄位（含武器力的 3 個 2-bit）
- ✓ 國 16 bytes 全部欄位；國名、讀音、地圖位置
- ✓ 勢力君主；玩家勢力 `$0448`
- ✓ 頭像：11 部件 → sprite 緩衝、metasprite 0（4 人另有附加 sprite）、調色盤
- ✓ LZSS（`$01:F8FE`）
- ✓ 大地圖：mode 7 bank `$19`、城標記與城框、月份調色盤、視窗調色盤
- △ 地形格 64 × 64、名稱、移動等級：從程式碼與地圖對照解出，沒有模擬器驗證
- ✗ 沒有獨立的戰術地圖（部隊在放大的大地圖上交戰）；沒有相鄰表（行軍走地形格）
- … 未解：配置種類 1–5 的觸發條件與 +4、難易度 3 的君主升級、WRAM 執行期欄位（同盟、政策、控）、訊息字串表與事件、可選君主表、戰鬥規則（ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果（Rev 0） |
|------|------|------|
| `verify_scenarios.py` | 劇本選擇畫面存 savestate；6 輪（2 劇本 × 難易度 1–3），載入程式到 `Rom.loader_done`（Rev 0 `$01:D612`）時 dump WRAM `$0800–$1E15`，人物 224 × 22、國 31 × 21、勢力 15 × 5 與 `Rom.scenario_wram(劇本, 難易度)` 逐 byte 比對 | 6/6 輪：人物 4928/4928、國 651/651、勢力 75/75 bytes 相同，OK（33 秒） |
| `verify_persons.py` | 兩劇本各到「どの国の武将を」存 savestate；每輪先寫回開局狀態（電腦勢力已行動過），把人物 p 移進玩家的國（冀州／洛陽，原有武將移出），開武將詳細畫面，攔 `$00:8D60` 的字碼：姓名、所屬君主、讀音、レベル、経験値、体力 攻撃力 政治力 兵法力 忠誠度 人徳 兵数 統率力 士気 機動力、部隊攻撃力 = 攻撃力 + 士気、武器力 騎 弓 歩 | 189 年 224/224、219 年 224/224，OK（499 秒）。不寫回開局狀態時 189 年 214/224（其他武將的忠誠度已被電腦勢力改過） |
| `verify_countries.py` | 兩劇本各到「どの国の情報を」存 savestate；每輪寫回開局狀態、游標寫到國 c 的位置，開國的情報畫面，攔字碼：國名、君主、讀音、太守、金、産業値、米、収穫高、民、統治度、城塞値、防災値、税率、武将數、兵士數 | 189 年 19/19、219 年 28/28（沒有勢力的 12／3 國不開畫面，也確認沒有輸出），OK（54 秒） |
| `verify_faces.py` | 用 `verify_persons.py` 的 189 年輪次讀 OAM、VRAM 0x0000–0x0FFF、CGRAM 0x100–0x13F，依 OAM 畫出 (104, 31) 的 48 × 64 範圍 | 224/224 人逐 pixel 相同（含 4 人的附加 sprite），OK（493 秒） |
| `verify_text.py` | 80 輪把訊息 `$1F:CE06` 換成 16 個待測字碼，開武將列表，攔 `$00:8D60` 與讀字型的 `$00:8DC0`／`$00:8DEF` 的 X | 字碼 0x100–0x5FF 1280/1280 讀在 `$03:8000 + 32 (code − 0x200)`／`$04:8800 + 16 (code − 0x100)`，OK（92 秒） |
| `verify_maps.py` | 劇本選擇存 savestate；2 輪各到第一個月的地圖：VRAM 0x0000–0x7FFF 與 `Rom.map_vram`；`$05:81B1` 設完時的 CGRAM 影子與 `Rom.map_cgram(月, 縮放)`；畫面 CGRAM 第 5、14、15 列（顏色 1–15）與視窗調色盤 | 2/2 劇本：VRAM 32768/32768、調色盤 512/512、視窗列 90/90 bytes 相同，OK（38 秒） |
| `verify_lz.py` | 開機（第 20 幀存 savestate）到兩劇本第一個月的地圖，攔 `$01:F8FE` 的來源與返回時 `$7E:8000` 的大小、checksum | 20/20 個串流相同，OK（52 秒） |

Rev 1（`--rom "roms/Yokoyama Mitsuteru Sangokushi (Japan) (Rev 1).zip"`）全部腳本也通過：劇本 6/6 輪 bytes 全同、人物 224/224 × 2 劇本、國 19/19 與 28/28、頭像 224/224、字碼 1280/1280、大地圖 2/2、LZ 20/20（解壓程式在 `$01:F903`）。Rev 1 的資料差異（許褚的字形、張嶷的讀音、典韋的登用者）見 ROM_FORMAT.md §9。

另外對照遊戲畫面：冀州的國情報（金 1008 米 1152 民 670000 …）與田豊、審配、曹操的武將詳細畫面截圖，和解碼值相同。
