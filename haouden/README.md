# SFC 信長の野望・覇王伝 解析

KOEI，1993，SFC（HiROM 2 MB）。3 個劇本（1551、1568、1582 年），人物 Id 0–819（實際 817 人）、110 城、64 國。文字是遊戲自己的 2-byte 字碼（`0x8140 + 字號`，1808 字）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python haouden/export.py [--rom ROM] [--out DIR]          # → haouden/output/（CSV、XLSX、PNG），約 10 秒
.venv/bin/python haouden/export_kaodata.py --out <kaodata>/data-local/nobu5-sfc
.venv/bin/python haouden/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu5-sfc
.venv/bin/python haouden/verify_scenarios.py                 # 約 20 秒
.venv/bin/python haouden/verify_faces.py [--quick]           # 約 10 分鐘（--quick 約 2 分鐘）
.venv/bin/python haouden/verify_maps.py                      # 約 20 秒
.venv/bin/python haouden/verify_battle_maps.py [--quick]     # 約 9 分鐘（--quick 約 2 分鐘）
```

- ROM 預設直接讀 `roms/Nobunaga no Yabou - Haouden (Japan).zip`，`--rom` 也接受 .sfc 與 Rev 1（`roms/Nobunaga no Yabou - Haouden (Japan) (Rev 1).zip`），匯出與全部驗證腳本都支援兩版。Rev 1 搬動了大部分的表，偏移分版本放在 `rom.OFFSETS`，由解壓表的位置自動判斷；兩版解出來的資料除了劇本 1 的 34 人的人物 +27（未解欄位）以外完全相同。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0xA0D9`，Rev 1 `0xA0D3`）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore），savestate 重播用 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：解壓縮、字型與文字、劇本（人物、城、大名）、後登場人物、各名稱表、頭像（專屬＋組合）、大地圖、城的地圖位置、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `nobu5-sfc`（348 張專屬頭像＋6 組組合臉） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 3 劇本開局 WRAM（大名、人物、城、共用區）與 ROM 劇本映像逐 byte 比對 |
| `verify_faces.py` | 927 個頭像碼逐一換進主畫面城資訊欄的頭像呼叫，比對遊戲寫進 VRAM 的 tile 與調色盤 |
| `verify_maps.py` | 大地圖：遊戲解壓到 WRAM 的地圖、BG2 tilemap、tile、調色盤 |
| `verify_battle_maps.py` | 143 張戰場：把戰場載入程式讀的地圖編號換掉，比對遊戲組出的兩層 BG tilemap、tile、調色盤 |
| `data/charset.txt` | 1808 個字形 → 字元（每行 32 字） |

## 輸出（`haouden/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 817 人（Id 0–819，139、140、456 未用）：姓名（含改名後的其他名）、生年、政治 戦闘 智謀 采配 野望、初登場、登場劇本、頭像碼與來源 |
| `person_scenarios.csv` | 3 劇本開局的人物（412／459／413）：WRAM 位址、年齢、能力、忠誠、知行、身分（大名／城主／家臣）、所在城、大名家、未解欄位 |
| `future_persons.csv` | 3 劇本之後才登場的人物（283／133／59）：登場年、登場城、能力、未解欄位 |
| `castles.csv` | 3 劇本 × 110 城：國、大名家、城主、武將數、本城旗標（推測）、規模、防、貫、人、商、練、治、兵、銭、糧、鉄砲、馬、大地圖位置（格）、戰場圖、無城戰場的城類 |
| `daimyo.csv` | 3 劇本的大名（48／43／27）：當主、所轄城、貢献、家紋（推測）、未解欄位 |
| `provinces.csv`、`titles.csv`、`treasures.csv`、`princesses.csv`、`terrains.csv` | 64 國、226 官位、120 家宝、93 姫、15 種地形的名稱 |
| `historic_battles.csv` | 15 場合戦：名稱、對應的城、戰場圖編號 111–125 |
| `battle_maps.csv` | 143 張戰場：種類（城 0–109、特殊 110、合戦 111–125、無城地形 126–142）、對應的城或合戦 |
| `haouden.xlsx` | 以上各表（需 openpyxl） |
| `faces/` | 927 個頭像碼的頭像（`048_龍造寺隆信.png`，組合臉已組好；人物 Id = 頭像碼） |
| `map.png`、`map_castles.png` | 大地圖 1536 × 512；放大 2 倍並標上 110 城的 Id 與名稱 |
| `battle/` | 143 張戰場地圖（640 × 376，調色盤組 0） |
| `font.png` | 1808 字的字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`，810 個 LZ 項目）、字型 1808 字與字碼表（`data/charset.txt`，含「長宗我部」「香宗我部」的 3 字合字）
- ✓ 名稱表：國 64、官位 226、家宝 120、合戦 15、能力名 8、姫 93、地形 15
- ✓ 3 劇本：劇本映像（`$7E:2000` 起 0x6303 bytes）＋共用區的 ROM 來源（WRAM 完全一致，開局才設定的欄位另計）
- ✓ 人物：姓名、生年、五項能力、忠誠、知行、所在城、人物 Id、所屬串列（城主→家臣）；気合（開局時才設定）
- ✓ 後登場人物：登場年、登場城、姓名、生年、能力、人物 Id（結構解開，模擬器只驗證了開局的部分）
- ✓ 110 城：名稱、國、大名、城主串列、規模、本城旗標、防、貫、人、商、練、治、兵、銭、糧、鉄砲、馬；大地圖位置
- ✓ 大名：當主、所轄城、貢献
- ✓ 頭像：專屬 348 張＋組合臉 6 組 × 5 部位 × 5 款；頭像碼 0–928（920、921 遊戲本身不處理）；kaodata 資料集 `nobu5-sfc`
- ✓ 大地圖：96 × 32 格（16 × 16 tile）、tile、調色盤 2–3（含水面動畫）、110 城的圖示位置
- ✓ 戰場地圖：143 張的六角格（40 × 23）、metatile 表、翻轉、上緣半格、tile、3 組調色盤；城戰場、合戦、無城地形圖的選用程式
- … 未解：大名關係欄（友好度）、家紋、多個人物／城／大名欄位、共用區與 misc 區內容、戰場地形碼與移動、部隊配置、地圖 110 與 129–130 的選用、調色盤組 1–2 的使用時機（[docs/ROM_FORMAT.md](docs/ROM_FORMAT.md) §11）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 3 劇本選完劇本後（選大名畫面）WRAM `$7E:2000–$7E:872F` 與劇本映像＋共用區逐 byte 比對；再用同一套程式從 WRAM 解碼，比對姓名、Id、生年、能力、所在城、城的欄位、大名 | 相同 byte 25449／25421／25502（共 26416）；不同之處全在開局設定的欄位（人物 +30 低 4 位元＝気合、大名 +35／+37、城 +35、共用區 0x180 以後），其他 0 byte；WRAM 解碼人物 412/412、459/459、413/413，城 110/110 × 3，大名 48/48、43/43、27/27 相同；18 秒。Rev 1 結果相同（18 秒） |
| `verify_faces.py` | 以龍造寺隆信開局，主畫面城資訊欄呼叫 `$C1:187F` 的引數（`$C1:8185` 讀人物 +31）換成每個頭像碼，比對 VRAM `0x2400` 的 960 bytes 與 CGRAM 調色盤 15；未改動時 = 龍造寺隆信（頭像碼 48） | 未改動 OK；專屬頭像 348/348、組合臉 579/579、ALL OK（704 秒，和另一個 Mesen 工作同時跑）；`--quick` 44/44、72/72，105 秒。Rev 1 `--quick` 結果相同（105 秒） |
| `verify_maps.py` | 第一回合主畫面：WRAM `$7F:E800` 的地圖與 LZ 項目 15、VRAM BG2 tilemap 的非空格、VRAM `0x8400` 的 tile 與 LZ 項目 14、CGRAM 調色盤 2–3 | WRAM 2902/3072 格相同（其餘 170 格是依城主重畫的城圖示）；BG2 tilemap 257/272（其餘 15 格是城圖示）；tile 相同；調色盤相同（水面動畫幀）；21 秒。Rev 1 結果相同（21 秒） |
| `verify_battle_maps.py` | 0 人玩家、他国合戦「見る」開局，電腦第一場合戦（地圖 134）載入前存 savestate；把載入程式讀 `$7E:8733` 的 3 處換成每個地圖編號，比對 WRAM `$7F:0000`（地面）與 `$7F:20D0`（覆蓋層）每一格的 2 × 2 tilemap；未改動時另比對 VRAM `0x8200` 的 tile 與 CGRAM 調色盤 2–4 是 3 組之一 | 未改動：地圖 134、地面 940/940 格、tile = LZ 項目 441、調色盤 = 組 0；143/143 張：地面 134420/134420 格、覆蓋層 134420/134420 格；528 秒；ALL OK。`--quick`（18 張）16920/16920、16920/16920，120 秒。Rev 1 `--quick`：電腦的第一場是地圖 131、調色盤組 2，18/18 張全同，121 秒 |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_pixels` 逐 pixel 比對、checksums | 人物 817/817、專屬頭像 348/348、checksums OK；1.1 秒 |

欄位意義另外對照遊戲畫面（Mesen 截圖）：松浦隆信的人物畫面（能力、忠誠、知行）、日之岳與原的城畫面（規模、防、貫、人、商、練、治、兵、銭、糧、鉄砲、馬）、勢力畫面的貢献。
