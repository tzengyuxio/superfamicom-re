# 新遊戲解析流程

從本專案 20 款作品整理出來的做法。新的一款照這裡的順序做，各步驟的範本程式寫在每節最後。專案的資料夾與工具架構見 [ARCHITECTURE.md](ARCHITECTURE.md)。

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
| `tools/replay.py` | savestate 重播：照按鍵序列玩到某一幀存檔，之後每輪改 PRG ROM／WRAM、按鍵、在指定幀讀記憶體；NMI 掛勾位置從 LoROM／HiROM 表頭的向量算。按鍵序列和 `drive.py` 同語法（含 `*n`），`expand()` 展開、`end_frame()` 算序列結束幀 |
| `tools/printf_trace.py` | 給 `replay.py` 用的 printf／vsprintf 追蹤 Lua：記錄每次呼叫的格式位址、依格式讀出的引數（數字、`%s` 字串與指標）、vsprintf 的輸出；引數在 stack 上的位置由呼叫端指定 |
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

- 一個 process 只能開一次 Mesen；多輪比對用 savestate 重播（`tools/replay.py`）
- savestate 只能在 exec callback 裡建立／讀回，掛在 NMI handler 的第二個指令上（光榮的 NMI handler 第一個指令都是 1 byte 的 SEI，所以是向量 + 1）
- 讀回後第一輪不生效，第一項要重複一次再丟掉
- Mesen 的 log 有大約 500 行的上限，大量資料要在 Lua 裡先彙總，或分輪 `breakExecution()` 後由 Python 讀

| 要驗證的 | 範本 |
|----------|------|
| 劇本 WRAM | `kouryuuki/verify_scenarios.py`（WRAM 整塊比對）、`tenshouki/verify_scenarios.py`（逐表、串列另計） |
| 頭像（換引數） | `kouryuuki/verify_faces.py`：在頭像程式入口改 stack 引數 |
| 頭像（組合臉） | `san3/verify_faces.py`、`san4/verify_faces.py` |
| 戰場地圖 | `tenshouki/verify_field_maps.py`（改 ROM 指標表換圖）、`san4/verify_maps.py`（強制旗標觸發攻城戰） |
| 外部能力值 | `san4/verify_persons.py`：和 kaodata-re 的 ROTK 能力表比對 |
| 頭像（換 ROM） | `tenshouki/tools/face_capture.py`：改 ROM 裡某人的頭像碼 |
| 地圖 | `tenshouki/verify_maps.py`、`san2/verify_maps.py` |
| 畫面數值（C 寫的作品） | `tools/printf_trace.py`：`teitoku2/verify_tables.py`（vsprintf，22 個畫面）、`sangokushi/verify_persons.py`（printf）；較早的寫法 `dokuritsu/verify_persons.py` |
| 畫面文字（逐 tile 比對） | `zenkoku/scenes.py`：用 ROM 字型把畫面 tilemap 轉回文字 |
| 把記錄換進畫面 | `taikou/verify_persons.py`、`europe/verify_cities.py`：顯示前把 WRAM 換成待測記錄，一輪驗多筆 |
| 原版與 Rev 1 共用 | `teitoku/rom.py` 的 `REVISIONS`（移位的格式字串換算表）、`haouden/`、`airmanage/` |
| 國／城數值（WRAM patch） | `genchou/verify_countries.py` |
| kaodata | `kouryuuki/verify_kaodata_export.py`（單一調色盤）、`tenshouki/verify_kaodata_export.py`（組合臉） |

## 4. 交付清單

- `<game>/rom.py`、`export.py`、`export_kaodata.py`、`verify_*.py`、`README.md`、`docs/ROM_FORMAT.md`（含未解部分）
- 根目錄 `CLAUDE.md` 遊戲表加一列
- 輸出放 `<game>/output/`，CSV 用 UTF-8-BOM；外部資料欄位加 `[EXT]` 並註明出處
- `uvx ruff check --line-length 120`；有 shebang 的腳本 `chmod +x`，`rom.py` 不要
- 暫時解出來的 ROM 刪掉，只留 zip

## 5. 踩過的坑

- macOS 的 `seq 1 0` 會倒數，產生多餘的按鍵；用 Python 組序列
- 很多遊戲要按住約 10 幀才有反應：`drive.py` 用 `a:10` 這種寫法
- 按鍵時機受亂數影響：三國志III 選劉備時差 1 幀就會進 AI 戰鬥。序列固定下來後，用截圖確認每一步
- savestate 不能掛在 NMI handler 的第一個指令上（三國志III 要用 `$00:8392`，不能用 `$8391`）；讀回要延到下一次 NMI
- Mesen state 的 `tilemapAddress`、`chrAddress` 是 word 位址，乘 2 才是 byte；mode 7 的矩陣即使在 bgMode 1 也看得到
- `drive.py --reads` 對整個 ROM 追蹤會超過 10 分鐘：先只追蹤指標表本身，或在 `$420B` 下 write callback 記錄 DMA（source、size、VRAM 位址）
- 平常難以觸發的畫面：找到切換用的旗標強制改值（三國志IV 的攻城戰 `$3DAE`）
- C 編譯的遊戲通常有一張共用服務跳轉表（三國志III `$C0:9024`：解壓、DMA、memset），適合下 exec 斷點
- MesenCore 會在 stderr 印大量 `Uninitialized memory read`，用 `grep -v Uninit` 過濾；這訊息也可能黏在 log 的同一行，解析時用包含字串比對，不要只看行首
- 同一個 Python process 開第二次 Mesen 會 segfault；需要多次時改用子程序
- 同一次 NMI callback 裡先 `createSavestate` 再 `loadSavestate`，有時會報 "must be called inside an exec memory operation callback"；改到下一次 NMI 再讀回
- `drive.py --reads` 的位址或幀範圍太大時，有時一行都不輸出；先縮小範圍
- 重播腳本的 NMI 位址不要寫死，從 ROM 的 NMI 向量算（霸王傳原版 `$00:848D`、Rev 1 `$00:8491`）；Rev 1 的電腦走法也不同，savestate 幀數要分版本
- `Mesen.log()` 預設緩衝 4 MB，大量 hex 會被截斷（`fromhex` 出錯）；用 `m.log(1 << 26)`
- 光榮 p-code 遊戲的檔案 handle（`$7E:1E00` 一帶每筆 14 bytes，服務 1A／1C／1E 開檔、seek、讀取）：記錄 seek 位置就能定位資料表（大航海時代）
- 組合臉的 tile 表欄位可能是 LE16，當成 byte 讀會全錯（大航海時代，Mesen 驗證抓出來的）
- 重播時每輪都讀大量 VRAM 很慢；CHR 只在少數幾輪讀
- 要看電腦之間的戰鬥：玩家 0 人、他國合戰選「見る」，不用操作就會進戰場（霸王傳）
- 鏡頭停在地圖角落時，畫面上只有部分格子落在地圖內；比對 tilemap 要只看地圖內的格子（英傑傳 `verify_maps.py`）
- 光榮 p-code 遊戲（武將風雲錄）的表用相對檔案開頭的偏移（例如 `hdata+4`），直接搜 CPU 位址找不到
- 自訂 2-byte 字碼裡低位 byte 為 00 的字寫不進字串，武將風雲錄用跳脫碼 `85F0/85F1/85F2` 代表 `8200/8300/8400`；其他光榮作品可能也有
- 在 worktree 裡跑 ruff，import 排序的判定可能和主 repo 不同；合併後要在主 repo 再跑一次
- 看起來像代碼的值（例如寶物持有者 0、600）不要直接當人物編號；意思不明就輸出原始值
- `rm` 是 trash 的 alias，不吃旗標；要真的刪用 `command rm`
- 不是每個 LZ entry 都是壓縮串流（天翔記 17、18、20、102–105 是未壓縮資料），`koei_lz.decompress` 遇到不合法的複製會丟 `ValueError`
- 天翔記、三國志IV 等遊戲有多張 LZ 指標表；大航海時代II、英傑傳等找得到解壓表、卻找不到 3-byte 指標表，指標格式要另外追
- 開機或開新局時，常把 ROM 裡一整塊初始資料原封複製到 WRAM（大航海時代II `0x8780D` → `$7E:2000`、獨立戰爭 6 塊）：在選角畫面 dump WRAM 和 ROM 比對，0 byte 差異就能一次定位人物、勢力、地點等表
- 要走到目標畫面可以直接改 WRAM（大航海時代II 把船寫進主角的開始艦隊才能出海，艦隊 1 而不是 0）
- 動畫或時段會換調色盤；驗證地圖時接受一組變體，不要只比一列
- C 寫的作品（獨立戰爭 `$C1:430F`）在 vprintf 掛 exec callback，讀格式指標和 va 引數，就拿得到畫面上每個數字與字串的來源；再改 immediate 換人，一次驗完全部人物，比截圖辨識可靠
- 畫面上的半形數字和等級字有固定的 tile 編號，直接讀 tilemap 就能驗證欄位，不需要 OCR（元朝秘史）
- 畫面數值通常在畫面第一次畫出時就固定，WRAM patch 要在那之前做（元朝秘史的國資訊要在「戦闘を見ますか」之前改）
- bank `$C0` 的程式要掛 exec callback，得在 `$00`、`$40`、`$80`、`$C0` 四個 bank 都註冊；`--reads` 也可能因為走別的 mirror bank 而追不到
- `replay.py`：存檔幀之後的開機按鍵會被丟掉（讀回後改用每輪的 `steps`），存檔點要在最後一個按鍵之後；`EXTRA_RESET` 被丟掉的第一輪也會呼叫，每輪的參數用 `wram` patch 傳，不要在 Lua 裡數呼叫次數
- 需要不同開機序列時，用子程序呼叫自己（`genchou/verify_faces.py --scene`），因為一個 process 只能開一次 Mesen
- 改版 ROM 夾在程式碼間的格式字串會移位；攔 printf 比對格式位址時要依版本換算（`teitoku/rom.py` 的 `REVISIONS`）
- 程式可能在 `$00`／`$80`、`$04`／`$84` 等鏡像 bank 兩邊執行，exec callback 要兩邊都掛
- LZ 串流不一定都在指標表裡，程式也會直接用位址讀（スーパー三國志 `0x2C00`、`0x74D7`）
- 頭像是 sprite 還是 BG、用哪組調色盤，只看 VRAM 判斷不出來；用截圖逐 pixel 確認（スーパー三國志原本誤用 BG 調色盤）
- 比對畫面數值要用同一時點的 WRAM dump，不要用 ROM 的劇本映像：開局後遊戲會改值（提督の決断II 的予備兵力）
- 驗證腳本加 `--dump`／`--load`，可以不跑模擬器重做比對（`teitoku2/verify_tables.py`）
- 改變數讓遊戲自己載入（戰場目標國的指標、建地圖前改支配勢力），比改 ROM 指標可靠，也驗得到執行時才加上的東西（スーパー三國志的城）
- PRG patch 可以借 ROM 的 0xFF 填充區放 stub，把現有的呼叫改道去呼叫遊戲自己的函式（航空霸業II 開國家代表視窗）
- KOEI 的 MVN 複製例程可能放在 WRAM（全国版 `$00:006C`），讀取追蹤看到的 PC 會在 bank `$00`
- 同一組按鍵在 `drive.py` 不同次執行，電腦對戰的事件可能不同；在 `replay.py` 的 savestate 之後則固定
- `drive.py` 的 `@tag` 會多算 1 幀；`replay.py` 略過 `@tag`
- 不要用 `until ! pgrep -f <名稱>` 等背景程式：`bash -c` 的指令列本身含那個名稱，pgrep 會比對到自己而永遠等不完

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
| 航空霸業II | LoROM 1 MB | 有解壓表；資料在 `0x6000` 的檔案表（196 個檔），不是指標表 |

只有武將風雲錄、航空霸業 I 沒有這套 LZ（和三國志II 一樣是早期的 LoROM 作品）。

以上 17 款都已解析完成（各遊戲的資料夾見根目錄 `CLAUDE.md`）。
