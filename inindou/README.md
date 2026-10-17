# スーパー伊忍道 打倒信長（SFC，中文名超級伊忍道）

KOEI，LoROM 1.25 MB（標頭 `SUPER ININDOU`，SRAM 8 KB），p-code 引擎、無壓縮（地圖用簡單 RLE）。
ROM：`roms/Super Inindou - Datou Nobunaga (Japan).zip`；美版 `roms/Inindo - Way of the Ninja (USA).zip` 只用來對照英文名稱。
格式細節見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

光榮的 RPG：人物（主角、同伴候選、忍者／僧／陰陽師／武士）、16 大名與 103 武將、30 國、術、物品、敵人。
SFC 版沒有人物頭像，狀態畫面顯示的是職業圖示，所以不出 kaodata 資料集。

## 指令

```sh
.venv/bin/python inindou/export.py                 # CSV（UTF-8-BOM）＋ inindou.xlsx ＋ PNG → inindou/output/
.venv/bin/python inindou/verify_state.py           # 以下都要 Mesen 2，時間見驗證結果
.venv/bin/python inindou/verify_persons.py
.venv/bin/python inindou/verify_items.py
.venv/bin/python inindou/verify_spells.py
.venv/bin/python inindou/verify_maps.py
```

## 檔案

| 檔案 | 內容 |
|------|------|
| `rom.py` | ROM 解析：檔案表、字碼（含跳脫碼）、人物、人物初始狀態、職業、武將、國（相鄰、初始狀態、駐留武將）、術、物品、敵人、敵特殊能力、地名、職業圖示、地點地圖（RLE、町的 metatile／圖塊）；美版英文名對照 |
| `scenes.py` | 按鍵序列（開機→命名→第一張地圖、欄位選單→情報→人物選択→能力／道具／術）與讀畫面文字的 `ScreenReader`（VRAM 視窗層 tile 對 ROM 字型） |
| `export.py` | 匯出 CSV、xlsx、PNG |
| `verify_state.py` | sdata = 開新遊戲複製到 WRAM `$7E:EFF0` 的初始狀態 |
| `verify_persons.py` | 105 人的姓名、職業、狀態數值、性別、職業圖示（VRAM）與調色盤（CGRAM），也驗證字碼→字形 |
| `verify_items.py` | 138 個物品名 |
| `verify_spells.py` | 42 個術名（忍術／仙術／妖術） |
| `verify_maps.py` | 48 張地點地圖由遊戲自己解壓的結果；開始的村的 BG2 tilemap、圖塊、調色盤 |
| `data/charset.txt` | 字型 1518 字 → 字元（碼 0x8132 + g） |
| `docs/ROM_FORMAT.md` | 格式、未解 |

## 輸出（`inindou/output/`，不進版控）

`files.csv`（67 個檔）、`persons.csv`（105 人，含 63 筆初始狀態與美版英文名）、`jobs.csv`（17）、`generals.csv`（103，含所在國、城主、所屬大名）、
`provinces.csv`（30 國：相鄰、大名、城主、金米兵、駐留武將）、`spells.csv`（42）、`items.csv`（138）、`enemies.csv`（180，136 筆有美版英文名）、
`enemy_skills.csv`（14）、`places.csv`（地名 18）、`maps.csv`（48 張地點地圖）、`map_cells.csv`（各圖每格的格碼）、`inindou.xlsx`（以上各一頁）、
`icons/`（16 張職業圖示）、`maps/`（地圖 0–37 用町的圖塊畫成 PNG，`map34_start.png` 是開新遊戲的村）、`font.png`。

## 進度

| 項目 | 解碼 | 驗證 |
|------|------|------|
| 檔案系統（67 檔） | ✓ | 間接（各表的位置都由遊戲讀取確認） |
| 文字編碼／字型 1518 字、跳脫碼 89F0–89F5 | ✓（字形→字元靠字型比對＋人工） | ✓ 碼→字形（`verify_persons.py` 等讀畫面）；「般若王」畫面確認跳脫碼 |
| 人物 105 人（姓名、職業） | ✓（b12 b13 b15 未解） | ✓ `verify_persons.py` |
| 人物初始狀態 63 筆（体力、気力、経験値、レベル、知力、力、素早さ、運、性別） | ✓（+13 +14 +28–30、術遮罩位元未解；裝備推定） | ✓ `verify_persons.py` |
| 職業 17 種、職業圖示 16 張＋調色盤 | ✓（調色盤選擇規則未解，依實測） | ✓ VRAM＋CGRAM（`verify_persons.py`） |
| 初始狀態區塊 sdata（道具袋、主角名、國、武將鏈） | ✓ | ✓ `verify_state.py` |
| 術 42 個（名、推定消費気力） | ✓（b8 b9 未解） | ✓ 名稱 `verify_spells.py` |
| 物品 138 個（名、價格） | ✓（種類、旗標未解） | ✓ 名稱 `verify_items.py` |
| 武將 103 人、16 大名、各國駐留武將 | ✓（兩值、大名表值未解） | 只驗區塊位置（`verify_state.py`），名稱沒在畫面上驗 |
| 國 30（名、相鄰、大名、城主、金米兵） | ✓（多個欄位未解） | 同上 |
| 敵人 180、敵特殊能力 14 | 名稱 ✓（23 bytes 欄位未解） | 未驗（遭遇在模擬器裡難觸發）；美版英文名依資料比對 |
| 地名 18 | ✓ | 未驗 |
| 地點地圖 48 張（RLE） | ✓ | ✓ 48/48 由遊戲解壓比對（`verify_maps.py`） |
| 地點地圖的圖塊 | 町 ✓（地圖 0–37；38–47 未解） | ✓ 開始的村（地圖 34）tilemap／圖塊／調色盤；其他推定 |
| 大地圖（日本全圖）、戰鬥畫面（戰術地圖）、劇情文字 | 未解 | — |

### 驗證方式

- 共同做法（`tools/replay.py`）：開新遊戲到第一張地圖存 savestate，每一輪改 WRAM（或 PRG ROM）後按選單，在指定幀讀 VRAM／CGRAM／WRAM。
  畫面文字用 `scenes.ScreenReader` 讀：視窗層（BG1 tilemap VRAM 0、tile 0x8000）的 8×8 tile 取出字色 15，2×2 拼成 16×16 與 ROM 字型逐字比對，
  所以名稱的比對是「ROM 字碼 − 0x8132 = 畫面上的字形號」。
- `verify_state.py`：讀 WRAM `$7E:EFF0` 0xFE0 bytes 與 sdata 比，只允許主角名與 0–2、0x1A、0xBB4 不同。
- `verify_persons.py`：105 輪，把主角的狀態記錄（`$7E:F0B8`）換成人物 n 的初始記錄（63–104 沒有記錄，用主角的記錄改 +0），開能力畫面讀姓名、職業、
  性別與 9 個數值，並比對 VRAM `0xB600` 的職業圖示與 CGRAM 調色盤 0。
- `verify_items.py`：10 輪，主角道具袋 15 格填物品號，讀道具一覧每列兩個名稱。
- `verify_spells.py`：3 輪，主角記錄換成忍者（主角）、天海（僧）、土御門晴友（陰陽師）並把術遮罩設 FF，讀術畫面三欄。
- `verify_maps.py`：savestate 取在命名畫面最後一個 YES 之前；48 輪各把地圖表第 34 項改指向地圖 m，讓遊戲自己的 `$7E:72A3` 解壓，讀 WRAM `$7F:B000` 比對；
  原樣那一輪另外比對 BG2 tilemap 的 400 個字（含遊戲填的邊框）、VRAM `0x4400` 圖塊、CGRAM 調色盤 2。

### 驗證結果（實際輸出）

| 腳本 | 時間 | 結果 |
|------|------|------|
| `verify_state.py` | 8 s | sdata 4059/4064 bytes 相同，只差 0–2、0x1A、0xBB4（主角名已換成 ああ）；ALL OK |
| `verify_persons.py` | 326 s | name+job 105/105、values 105/105、icon 105/105、palette 105/105；ALL OK |
| `verify_items.py` | 38 s | items 138/138；ALL OK |
| `verify_spells.py` | 20 s | spells 42/42；ALL OK |
| `verify_maps.py` | 61 s | cells 48/48、tilemap 400/400、圖塊與調色盤 OK；ALL OK |
