# 新遊戲解析流程

從スーパー三國志II、天翔記、項劉記三款整理出來的做法。新的一款照這裡的順序做，各步驟的範本程式寫在每節最後。

## 0. 選版本、分診

- 有日版就用日版，Rev 0 當預設，`--rom` 也要能吃 Rev 1；美版只用來對照英文名稱
- 先跑分診，知道是 LoROM 或 HiROM、有沒有 KOEI LZ、文字是不是 Shift-JIS：

```bash
.venv/bin/python tools/triage.py "roms/<遊戲>.zip"
.venv/bin/python tools/koei_lz.py "roms/<遊戲>.zip"     # LZ 表、解壓程式位置、指標表
```

## 1. 共用工具

| 工具 | 用途 |
|------|------|
| `tools/mesen.py` | ctypes 呼叫 MesenCore，無頭執行 Lua |
| `tools/drive.py` | 用按鍵序列操作遊戲，截圖（`@tag`）、dump WRAM／VRAM／CGRAM／OAM／SRAM；`--reads` 追蹤某段位址被哪個 PC 讀了 |
| `tools/koei_lz.py` | KOEI LZ 解壓（`decompress`），`find_tables` 用內容找解壓表，`find_pointer_tables` 找串流指標表 |
| `tools/triage.py` | 所有 ROM 的標頭、LZ、Shift-JIS 字數一覽 |
| `tools/kaodata.py` | kaodata/1 的寫入、讀取、參考渲染、checksums |
| `tools/parts_sheet.py` | 組合臉零件總覽圖 |

分析中的暫存檔（dump、截圖、追蹤用 Lua）放 scratchpad，不進 repo。

## 2. 步驟

### 2.1 找到能操作的按鍵序列

先用 `drive.py` 一路加 `@tag` 截圖，摸出標題 → 新遊戲 → 劇本 → 君主 → 第一回合的序列，記下每個畫面的幀數。這是後面所有追蹤與驗證的基礎。

- 開場動畫常常不能跳過（項劉記選完劇本後要等約 6500 幀）；按太早會被吃掉，或選到別的項目
- 序列寫在遊戲的 `docs/ROM_FORMAT.md` §1「操作」

### 2.2 文字編碼

- Shift-JIS：直接在 ROM 裡搜尋已知人名（天翔記）
- 自訂編碼：從畫面上的字反查。先用 `--reads` 在顯示文字的那幾幀追蹤 ROM 讀取，找到字型（1bpp 16×16 或 8×8），再找讀取文字的程式
  - 三國志II：自訂漢字碼，用 PC 版人名對出碼表，再用 ROM 字形核對
  - 項劉記：字型照 JIS X 0208 排的子集，用系統字型逐字形 DP 對齊，再人工修正。對照表放 `data/charset.txt`，`tools/charset_sheet.py` 產生核對圖

### 2.3 人物、地點

- 用已知人名或地名的編碼搜尋 ROM，找出固定長度的表（看相鄰兩筆的間距）
- 光榮的移植版先拿 FC 版（`~/works/famicom-re`）或 PC 版的表到 ROM 裡搜尋，三國志II 的劇本、州、戰場和 FC 版逐 byte 相同
- 能力值等欄位要和遊戲畫面逐項對照（至少 3–5 人，挑數值彼此不同的）

### 2.4 劇本資料

劇本的狀態通常是一塊 WRAM，從 ROM 複製或解壓而來：

1. 用 `drive.py` dump 各劇本開局的 WRAM
2. 在 ROM（以及所有 LZ entry）裡搜尋 WRAM 的片段，找出來源（項劉記是 5 段直接複製）
3. 用 `--reads` 在載入那幾幀確認讀取來源
4. 欄位對照遊戲畫面

### 2.5 頭像

- 打開有頭像的畫面，在 VRAM dump 裡找頭像 tile（三款都是 40×48、4bpp、5×6 個 tile、逐列排列）
- 用 `--reads` 找出載入頭像的程式，在它的入口 exec callback 讀引數（stack 或暫存器），確認人物 → 頭像號的關係
- 調色盤：在 CGRAM dump 裡找，再到 ROM 搜尋那 32 bytes
- 組合臉（天翔記、三國志II）：零件表與組法要從程式解出來

### 2.6 大地圖、戰術地圖

- 回合畫面 dump VRAM，從 PPU 暫存器（或 tilemap 內容）判斷哪個 BG 是地形
- 在 ROM／LZ entry 裡搜尋 tilemap 片段
- 戰術地圖：開一場戰鬥，同樣方法。用 `--reads` 追蹤所有 LZ 指標表的讀取，看戰鬥載入了哪幾個 entry
  - 天翔記：野戰地圖在第二張 LZ 表（`0x10DEA0`），全日本切成 30 × 11 張，可以拼成一整張（`tenshouki/docs/ROM_FORMAT.md` §9）。找排列寬度的方法：試各種寬度，算相鄰地圖接邊處海／陸一致的比例
  - 驗證範本：`tenshouki/verify_field_maps.py`，存 savestate 後改 ROM 裡的指標表，把任意地圖換進戰場

## 3. 驗證

每項解碼都要有一支用 Mesen 跑遊戲本身程式的驗證腳本。共通寫法：

- 一個 process 只能開一次 Mesen；多輪比對用 savestate 重播
- savestate 只能在 exec callback 裡建立／讀回，掛在 NMI handler（native NMI 向量 `0xFFEA`）上
- 讀回後第一輪不生效，第一項要重複一次再丟掉
- Mesen 的 log 有大約 500 行的上限，大量資料要在 Lua 裡先彙總，或分輪 `breakExecution()` 後由 Python 讀

| 要驗證的 | 範本 |
|----------|------|
| 劇本 WRAM | `kouryuuki/verify_scenarios.py`（WRAM 整塊比對）、`tenshouki/verify_scenarios.py`（逐表、串列另計） |
| 頭像（換引數） | `kouryuuki/verify_faces.py`：在頭像程式入口改 stack 引數 |
| 頭像（換 ROM） | `tenshouki/tools/face_capture.py`：改 ROM 裡某人的頭像碼 |
| 地圖 | `tenshouki/verify_maps.py`、`san2/verify_maps.py` |
| kaodata | `kouryuuki/verify_kaodata_export.py`（單一調色盤）、`tenshouki/verify_kaodata_export.py`（組合臉） |

## 4. 交付清單

- `<game>/rom.py`、`export.py`、`export_kaodata.py`、`verify_*.py`、`README.md`、`docs/ROM_FORMAT.md`（含未解部分）
- 根目錄 `CLAUDE.md` 遊戲表加一列
- 輸出放 `<game>/output/`，CSV 用 UTF-8-BOM；外部資料欄位加 `[EXT]` 並註明出處
- `uvx ruff check --line-length 120`；有 shebang 的腳本 `chmod +x`，`rom.py` 不要
- 暫時解出來的 ROM 刪掉，只留 zip

## 5. 踩過的坑

- macOS 的 `seq 1 0` 會倒數，產生多餘的按鍵；用 Python 組序列
- `rm` 是 trash 的 alias，不吃旗標；要真的刪用 `command rm`
- 不是每個 LZ entry 都是壓縮串流（天翔記 17、18、20、102–105 是未壓縮資料），`koei_lz.decompress` 遇到不合法的複製會丟 `ValueError`
- 天翔記、三國志IV 等遊戲有多張 LZ 指標表；大航海時代II、英傑傳等找得到解壓表、卻找不到 3-byte 指標表，指標格式要另外追

## 6. 分診結果（2026-10-13）

`tools/triage.py` 的結果（日版、Rev 0）：

| 遊戲 | ROM | KOEI LZ 指標表 |
|------|-----|----------------|
| スーパー三國志 | HiROM 1 MB | `0xED802` ×817 |
| 三國志III | HiROM 1.5 MB | `0x7F3A7` ×491 |
| 三國志IV | HiROM 3 MB | 12 張（`0xAE233` ×271 等） |
| 三國志英傑傳 | HiROM 3 MB | 有解壓表，指標表未找到；Shift-JIS 多 |
| 武將風雲錄 | LoROM 1 MB | 無 |
| 信長 全国版 | HiROM 512 KB | `0x3D133` ×193 |
| 信長 霸王傳 | HiROM 2 MB | `0x7BD84` ×810 |
| 大航海時代 | LoROM 1 MB | 有解壓表，指標表未找到 |
| 大航海時代II | HiROM 2 MB | 有解壓表，指標表未找到 |
| 元朝秘史 | HiROM 1.5 MB | `0x8A9DA` ×352 |
| 獨立戰爭 | HiROM 1.25 MB | `0x39649` ×419 |
| 太閤立志傳 | HiROM 1.5 MB | `0x1F2C1` ×448 |
| 歐陸戰線 | HiROM 1.5 MB | `0x14978` ×650 |
| 提督の決断 | LoROM 1.25 MB | `0x4F3EF` ×433 |
| 提督の決断II | HiROM 3 MB | `0x1A9C8E` 等 4 張 |
| 航空霸業（Air Management） | LoROM 1 MB | 無 |
| 航空霸業II | LoROM 1 MB | 有解壓表，指標表未找到 |

只有武將風雲錄、航空霸業 I 沒有這套 LZ（和三國志II 一樣是早期的 LoROM 作品）。
