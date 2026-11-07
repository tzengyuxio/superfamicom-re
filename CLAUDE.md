# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

超任（SFC/SNES）遊戲的 ROM 逆向工程專案：解析人物資料、頭像、地點、地圖等遊戲內容，並輸出 kaodata 統一格式資料集。FC 版的對應專案是 `~/works/famicom-re`（GitHub `tzengyuxio/famicom-re`，原名 fc-sangokushi），做法與慣例沿用它。

每款遊戲各放一個子資料夾，分析結果記在該資料夾的 `README.md` 與 `docs/`：

| 資料夾 | 遊戲 |
|--------|------|
| `san2/` | スーパー三國志II (KOEI, 1991, LoROM)：人物、6 劇本配置、41 州、相鄰、字型與漢字、頭像（kaodata `san2-sfc`）、大地圖、41 張戰場，全部有 Mesen 驗證 |
| `tenshouki/` | 信長の野望・天翔記 (KOEI, 1996, HiROM)：人物 700 人、2 劇本人物／城／軍団、頭像（kaodata `nobu6-sfc`）、大地圖、野戰地圖 330 張（拼成全日本戰場圖），全部有 Mesen 驗證；攻城戰地圖未解 |
| `kouryuuki/` | 項劉記 (KOEI, HiROM)：自訂字型與文字編碼、人物 92 人、4 劇本人物／地點／軍隊、頭像（kaodata `kouryuuki-sfc`），全部有 Mesen 驗證；大地圖渲染與戰術地圖未解 |
| `san3/` | 三國志III (KOEI, 1992, HiROM)：自訂字型、人物 532 人、6 劇本人物／州／勢力／寶物、頭像（含組合臉，kaodata `san3-sfc`）、大地圖、46 州戰場資料，全部有 Mesen 驗證；戰場的等角渲染未解 |
| `san4/` | 三國志IV (KOEI, 1994, HiROM)：Shift-JIS＋外字、人物 462 人、6 劇本人物／都市／勢力、頭像（含組合臉，kaodata `san4-sfc`）、大地圖（mode 7）、88 張戰場（野戰 45、攻城 43），全部有 Mesen 驗證 |
| `eiketsu/` | 三國志英傑伝 (KOEI, 1995, HiROM)：Shift-JIS＋外字 37 字、人物 384 人、勢力／兵種／地形／道具、頭像 240 張（kaodata `eiketsu-sfc`）、大地圖與地點、58 張戰場地圖，全部有 Mesen 驗證；劇本腳本未解 |
| `haouden/` | 信長の野望・覇王伝 (KOEI, 1993, HiROM，原版與 Rev 1)：自訂字碼 1808 字、3 劇本人物／城／大名、名稱表、頭像（含組合臉，kaodata `nobu5-sfc`）、大地圖、143 張戰場地圖，全部有 Mesen 驗證 |
| `daikoukai/` | スーパー大航海時代 (KOEI, LoROM)：資料表與文字和 FC 版相同、人物 41 人、女性 20 人、港口 70、名稱表、頭像（含組合臉，kaodata `koukai-sfc`）、世界地圖（4 緯度組）、港町圖，全部有 Mesen 驗證；海戰畫面未解 |
| `daikoukai2/` | 大航海時代II (KOEI, HiROM)：自訂字型 1631 字、開機初始狀態區塊、人物 120 人、6 主角開始設定、船種／交易品／道具／發見物、港 130、頭像（含組合臉，kaodata `koukai2-sfc`）、世界地圖（2160×1080 格），全部有 Mesen 驗證；海戰畫面、VIP／女性／艦隊多數欄位未解 |
| `genchou/` | スーパー蒼き狼と白き牝鹿・元朝秘史 (KOEI, HiROM)：自訂字型 2046 字、4 劇本人物／國／王家／女性、兵科／交易品等表、頭像（含組合臉，kaodata `genchou-sfc`）、大地圖（モンゴル與世界）、47 張戰場地圖（和 FC 版相同），全部有 Mesen 驗證；事件與城內地圖未解 |
| `dokuritsu/` | 独立戦争 Liberty or Death (KOEI, HiROM)：文字編碼（漢字只對出 10 字）、人物 250 人、1775 年劇本人物／地點／陣營、53 地點與 15 州、頭像（含組合臉，kaodata `liberty-sfc`）、大地圖 3 區、53 張 HEX 戰場，全部有 Mesen 驗證；漢字字型、大地圖擁有者上色未解 |
| `europe/` | ヨーロッパ戦線 Europe Sensen (KOEI, 1992, HiROM)：自訂字型 652 字、6 劇本將領／都市、將領 94 人＋領袖 6 人與經歷、都市 94、兵器 158 種、頭像（kaodata `europe-sfc`）、歐洲地圖、6 張戰場地圖，全部有 Mesen 驗證；部隊編制、勝利條件未解 |
| `taikou/` | 太閤立志伝 (KOEI, 1993, HiROM)：自訂字型 2048 字、人物 713 筆、勢力 20、城 125、頭像（含組合臉，kaodata `taikoh-sfc`）、日本地圖、19 張戰場，全部有 Mesen 驗證；戰場選圖規則、多個人物／城欄位未解 |
| `airmanage/` | エアーマネージメント 大空に賭ける／航空霸業 (KOEI, LoROM，原版與 Rev 1，無壓縮，p-code)：Shift-JIS 字型 690 字、22 都市與距離表、2 劇本、20 機種、5 製造商、頭像 33 張（kaodata `air-sfc`）、世界地圖，全部有 Mesen 驗證；沒有戰鬥（無戰術地圖），營收模擬、事件、片頭地球未解 |
| `airmanage2/` | エアーマネージメントII 航空王をめざせ／航空霸業II (KOEI, LoROM，196 個具名檔，C 編譯)：Shift-JIS 字型 713 字、89 都市、57 國、7 地區、32 家預設航空公司、4 劇本開局狀態、55 筆世界事件、53 機種、12 製造商、頭像 35 張（kaodata `air2-sfc`）、世界地圖與 7 張地區地圖，全部有 Mesen 驗證；沒有戰鬥（無戰術地圖），都市記錄多數欄位、國家表與開局複製表的意義未解 |
| `teitoku/` | 提督の決断 (KOEI, 1992, LoROM，原版與 Rev 1)：自訂字碼 1036 字、9 劇本（劇本 2–9 是修補）、艦船 270 艘、基地 50、艦隊 32、提督 40 人、他國 13、頭像 54 張（kaodata `tk-sfc`）、艦船圖 101 級、太平洋大地圖與世界地圖，全部有 Mesen 驗證；戰鬥畫面（戰術地圖）、艦船能力值名稱、部分場景圖未解 |
| `teitoku2/` | 提督の決断II (KOEI, HiROM，原版與 Rev 1)：自訂字碼 1216 字、10 劇本、艦型 152／潜水艦型 28／航空機 60／戦車 10、艦船 255、艦隊 39、基地 70、拠点 100、陸戦隊 40、提督 60＋將軍 30、頭像 104 張（kaodata `tk2-sfc`）、太平洋大地圖（海陸位圖），全部有 Mesen 驗證；大地圖圖塊渲染、戰術地圖、航空隊／師団與基地的對應未解 |
| `zenkoku/` | スーパー信長の野望・全国版 (KOEI, HiROM 512 KB)：自訂字型 636 字、4 劇本（17 國 1、50 國 3）、大名 53、人物 68、國 50／17 與相鄰（和 FC 版相同）、頭像 73 張（含姫 5，kaodata `nobu2-sfc`）、大地圖（依擁有者上色）、50 張戰場地圖，全部有 Mesen 驗證；半形字碼表、事件圖、多個 WRAM 表未解 |
| `sangokushi/` | スーパー三國志 (KOEI, HiROM 1 MB)：自訂字型 921 字、5 劇本人物／國／勢力（數量與 FC 版相同）、人物 255、國 58、州 15、頭像（肖像 128＋組合臉，kaodata `san1-sfc`）、大地圖與勢力上色、58 張戰場（含城位置表），全部有 Mesen 驗證；國與勢力多個欄位、開局時的調整、戰鬥流程未解 |
| `bushou/` | スーパー信長の野望・武将風雲録 (KOEI, 1992, LoROM)：自訂字碼與字型、武將 2 劇本、48 國、大名、茶器、頭像（含組合臉，kaodata `nobu4-sfc`）、大地圖、48 張野戰地圖，全部有 Mesen 驗證；城地圖畫面未解 |
| `royal/` | スーパーロイヤルブラッド (KOEI, 1992, LoROM 1 MB，美版 Gemfire)：資料表和 FC 版相同（半形片假名）、人物 64、4 劇本人物／家／領地、可選当主表、相談役 4（含名字）、部隊 23、頭像 68 張（kaodata `royal-sfc`）、戰略地圖與家標記、30 張戰場，全部有 Mesen 驗證；劇本標頭、部隊頭像、漢字文字未解 |
| `inindou/` | スーパー伊忍道 打倒信長 (KOEI, LoROM 1.25 MB，p-code，無壓縮)：自訂字型 1518 字（含跳脫碼）、人物 105 人與初始狀態 63 筆、職業 17、16 大名與武將 103、30 國（相鄰、初始狀態、駐留武將）、術 42、物品 138、敵人 180（美版英文名對照）、職業圖示 16 張（SFC 版沒有人物頭像，不出 kaodata）、地點地圖 48 張（町圖塊畫出 0–37），全部有 Mesen 驗證；大地圖、戰鬥畫面、劇情文字、地圖 38–47 圖塊未解 |
| `topman2/` | トップマネジメントII (KOEI, LoROM 1.5 MB，C 編譯，249 個具名檔)：Shift-JIS 文字、都道府縣 47（5 時期人口、JAPANS 填色段）、6 劇本＋FREE 3 種長度、3 公司與本社候補 15 對、產品 3／難度 5／產業 4／新聞 26、頭像 96 張（会長 12、社長 3、秘書 9、部長 72，kaodata `topman2-sfc`）、日本地圖 JAPANL，全部有 Mesen 驗證（JAPANS 只從檔案解出）；沒有戰鬥（無戰術地圖），JAPANS 的遊戲畫面、市場模擬、產品能力值、部長檔 SHABU／BAIBU 的部門未解 |
| `leading/` | リーディングカンパニー (KOEI, LoROM 1 MB，254 個具名檔，C 編譯)：協議會 4、廠商 12、2 劇本開局狀態（協議會／廠商／產品／機能／8×8 市場格）、產品記錄主要欄位、等級 8、機能 9、販促 12、頭像 44 張（kaodata `leading-sfc`）、主畫面街區地圖與建物，全部有 Mesen 驗證；沒有具名人物與戰鬥（無戰術地圖），`$5401`／`$6E05` 等表、產品多數欄位與定價、建物選擇規則未解 |
| `winning/` | ウイニングポスト (KOEI, 1993, HiROM 2 MB，原版與 Rev 1)：自訂字型 2368 字、人名 256、馬主 41、調教師 30、騎手 70、現役馬 381／種牡馬 50／繁殖牝馬 170 與馬名編碼、比賽 232 與日程 384 格、競馬場 8、頭像 208 張（含組合臉，kaodata `winning-sfc`），全部有 Mesen 驗證；沒有戰術地圖，馬的能力欄、血統表、騎手資料欄未解 |
| `mahjong/` | スーパー麻雀大会 (KOEI, LoROM 512 KB，Rev 0)：台詞字型 212 碼（只有假名）、對手 21 人（名字只有圖）、頭像 147 張（每人說話 3 格、笑、泣、驚、怒 56×56，kaodata `mahjong-sfc`）、台詞 21×133 行與 66 個情境、役名 52，全部有 Mesen 驗證；沒有地圖；打牌參數與情境的意義、飜數表、規則設定、大会未解 |
| `winning2/` | ウイニングポスト2 (KOEI, 1995, HiROM 3 MB，含プログラム'96 原版與 Rev 1，C 編譯)：自訂字型 3276 字、現役馬 120／種牡馬 147／繁殖牝馬 140／幼駒 80、騎手 110／調教師 20／馬主 29／秘書 6、牧場 24、比賽 1147 與日程 96 天 × 3 格 × 10 場、頭像 208（kaodata `winning2-sfc`）；'96 版的表位址、字表、比賽 1162、新頭像 27 與選臉規則，全部有 Mesen 驗證；沒有戰術地圖，馬的能力欄、多數人物欄位、初始區塊 `$687C` 未解 |
| `mahjong2/` | 麻雀大会II (KOEI, LoROM 1 MB)：台詞字型 212 碼（和前作相同，0D＝G）、對手 26 人（名字只有圖，24–26 只在大会）、打牌參數、7 雀荘與固定キャラ、規則 44 項（標準與各雀荘固定規則、前提關係）、頭像 234 張（每人 9 張：說話 3 格、笑、困、哭、不滿、怒 56×56、驚，kaodata `mahjong2-sfc`）、台詞 26×344 行與 103 個情境、役名等 65 個、系統訊息 71 則（含人物紹介），全部有 Mesen 驗證；沒有地圖；參數與情境的意義、飜數表、大会、玩家頭像未解 |
| `yokoyama/` | 横山光輝 三国志 (Angel, 1992, LoROM 1 MB，原版與 Rev 1，非光榮，不出 kaodata)：自訂 16-bit 字碼 1280 字、人物 224、2 劇本（189／219）人物／配置／國 31／勢力、頭像 224 張（sprite 組合）、大地圖（mode 7）與地形格，全部有 Mesen 驗證（地形格除外）；沒有戰術地圖（在大地圖上交戰），配置觸發條件、訊息表、戰鬥規則未解 |
| `yokoyama2/` | 横山光輝 三国志2 (Angel, 1993, LoROM FastROM 1.5 MB，非光榮，不出 kaodata)：前作引擎重新組譯、自訂 16-bit 字碼 1280 字、人物 229（名表 239）、3 劇本（189／200／215）人物／配置／國 35／勢力、難易度金米表、頭像 229 張（sprite 組合，5 人有專用 metasprite）、大地圖（mode 7，LZ＋交錯，砦與行軍部隊），全部有 Mesen 驗證；戰鬥與地形表未找到，配置種類 1–5、訊息表、國標記圖形未解 |
| `tenbu/` | 三国志正史 天舞スピリッツ (WOLF TEAM／TELENET JAPAN, LoROM SlowROM 1.5 MB，非光榮，不出 kaodata；游標操作)：SJIS＋字表 1113 字（自訂 92）、LZSS、4 劇本人物 600／勢力 15／郡国 126、郡国欄位（人口 兵 金 糧 士 規模 太）、官職 48、頭像 250、地域拡大図 270×230 chip、中国全土図，全部有 Mesen 驗證；勢力上色、相鄰、戰鬥、人物／郡国多個欄位未解 |
| `chrono/` | クロノ・トリガー (Square, 1995, HiROM 4 MB，非光榮，不出 kaodata；只做音樂)：曲目表 `$C7:0D18` 80 首、Akao 樂譜（循環點、tempo、驅動漏步造成的變慢）、SPC／OGG／MP3，曲名對 Zophar 美版 SPC；SPC ✅ emu+modified，循環長度 31 首 ✅ emu、35 首 🟡；場景與其他資料未做 |

## 開發慣例

- Python 一律用 `.venv/bin/python`；lint 用 `uvx ruff check --line-length 120`
- 新遊戲：開新資料夾，`README.md` 寫指令／檔案／進度，`docs/` 寫 ROM 格式（含尚未解開的部分）；步驟、範本與分診結果見 `docs/PLAYBOOK.md`；資料夾結構與共用／專用工具一覽見 `docs/ARCHITECTURE.md`
- 共用工具在 `tools/`：`paths.py`（ROM 所在的 `_original/sfc/`），`spc.py`（SPC700 狀態傾印 Lua、SPC 檔、libgme 渲染、OGG＋MP3），`drive.py`（按鍵序列、截圖、dump、ROM 讀取追蹤、DMA 記錄）、`replay.py`（savestate 重播，驗證腳本共用；按鍵序列的 `*n`、`expand`、`end_frame`）、`printf_trace.py`（printf／vsprintf 追蹤）、`koei_lz.py`（KOEI LZ 解壓與找表，三國志II、武將風雲錄、航空霸業以外的作品都用它）、`triage.py`（ROM 分診）、`kaodata.py`
- 每款遊戲提供：人物資料、頭像（含 kaodata 資料集與驗證）、地點資料、大地圖、戰術地圖，以及分析或攻略用得到的表
- `output/` 用 `scripts/rebuild.py <遊戲>`（或 `--all`，約 3 分鐘）重建，步驟見 `docs/ARCHITECTURE.md`「重跑 `output/`」
- 外部資料（不是 ROM 解析出來的）欄位名加 `[EXT]` 前綴
- 輸出 CSV 用 UTF-8-BOM（Excel 相容）
- 模擬器：`tools/mesen.py` 用 ctypes 呼叫 Mesen 2 的 MesenCore（無頭、跑 Lua）。一個 process 只能開一次 Mesen，多輪比對用 savestate 重播；savestate 只能在 exec callback 裡建立／讀回（用 NMI handler），讀回後第一輪不生效，要多跑一輪丟掉
- 光榮的移植版先比對 FC 版（`~/works/famicom-re`）的已知資料表：SFC 三國志II 的劇本、州、戰場等表和 FC 版逐 byte 相同，直接拿 FC ROM 的表去 SFC ROM 裡搜尋就能定位

## RE 共通語言

@~/.claude/re-common.md

本 repo 路徑 ↔ 共通層名：

| 層名 | 本 repo 路徑 |
|------|--------------|
| original | `~/game-library/_original/sfc/`（No-Intro 命名的 zip，只有這一份，`SHA1SUMS.txt` 記 hash），程式經 `tools/paths.py` 直接讀 zip（`GAME_LIBRARY` 可換位置）；新 ROM 用 `scripts/add_rom.py` 放進去；分析時暫時解出的 .sfc 寫在 scratch，用完即刪 |
| references | 沒有固定位置；外部資料抄錄成 `<遊戲>/data/` 的對照表（如 `genchou/data/name_zh.json`），欄位加 `[EXT]` 並註明出處 |
| captures | `<遊戲>/captures/screenshots/`（不進版控；例：横山光輝 三国志各代的標題畫面 `title*.png`，Claude 用 `tools/drive.py` 擷取）；`tools/drive.py` 其他的截圖、傾印寫到命令列指定的前綴，savestate 只在 Mesen process 內（`tools/replay.py`），用按鍵序列（各遊戲的 `tools/sequences.py` 等）重建，不留檔 |
| extracted | `<遊戲>/output/` 裡的 CSV、XLSX、單張頭像（`faces/`）、字型圖等（不進版控） |
| generated | `<遊戲>/output/` 裡的總覽與拼圖（`faces.png`、`map*.png`、拼好的戰場總圖等，不進版控） |
| runtime | 沒有固定位置；`tools/mesen.py` 每個 process 用暫存資料夾當 Mesen home，MesenCore 在 `~/Library/Application Support/Mesen2/` |
| export | 交給 kaodata 的資料集：`<遊戲>/export_kaodata.py --out ~/works/kaodata/data-local/<dataset id>`（`output/` 不放 export）；非光榮作品沒有 export |
| docs | `docs/`（共用：PLAYBOOK、ARCHITECTURE）、`<遊戲>/README.md` 與 `<遊戲>/docs/`、人工校對的對照表 `<遊戲>/data/` |
| tools | `tools/`（共用）、`<遊戲>/*.py`（解碼、匯出、驗證）、`<遊戲>/tools/`（遊戲專用）；scratch 級的探測腳本放 `scratch/<遊戲>/`（不進版控，每輪收尾整理，見 `docs/PLAYBOOK.md`） |
