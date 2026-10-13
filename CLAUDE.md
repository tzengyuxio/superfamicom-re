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
| `daikoukai/` | スーパー大航海時代 (KOEI, LoROM)：資料表與文字和 FC 版相同、人物 41 人、女性 20 人、港口 70、名稱表、頭像（含組合臉，kaodata `daikoukai-sfc`）、世界地圖（4 緯度組）、港町圖，全部有 Mesen 驗證；海戰畫面未解 |
| `daikoukai2/` | 大航海時代II (KOEI, HiROM)：自訂字型 1631 字、開機初始狀態區塊、人物 120 人、6 主角開始設定、船種／交易品／道具／發見物、港 130、頭像（含組合臉，kaodata `daikoukai2-sfc`）、世界地圖（2160×1080 格），全部有 Mesen 驗證；海戰畫面、VIP／女性／艦隊多數欄位未解 |
| `genchou/` | スーパー蒼き狼と白き牝鹿・元朝秘史 (KOEI, HiROM)：自訂字型 2046 字、4 劇本人物／國／王家／女性、兵科／交易品等表、頭像（含組合臉，kaodata `genchou-sfc`）、大地圖（モンゴル與世界）、47 張戰場地圖（和 FC 版相同），全部有 Mesen 驗證；事件與城內地圖未解 |
| `dokuritsu/` | 独立戦争 Liberty or Death (KOEI, HiROM)：文字編碼（漢字只對出 10 字）、人物 250 人、1775 年劇本人物／地點／陣營、53 地點與 15 州、頭像（含組合臉，kaodata `dokuritsu-sfc`）、大地圖 3 區、53 張 HEX 戰場，全部有 Mesen 驗證；漢字字型、大地圖擁有者上色未解 |
| `bushou/` | スーパー信長の野望・武将風雲録 (KOEI, 1992, LoROM)：自訂字碼與字型、武將 2 劇本、48 國、大名、茶器、頭像（含組合臉，kaodata `bushou-sfc`）、大地圖、48 張野戰地圖，全部有 Mesen 驗證；城地圖畫面未解 |

- ROM 都放 `roms/`（zip，不進版控），程式預設直接讀 zip。分析時可暫時把 ROM 解出來，做完要刪掉，只留 zip 作為來源

## 開發慣例

- Python 一律用 `.venv/bin/python`；lint 用 `uvx ruff check --line-length 120`
- 新遊戲：開新資料夾，`README.md` 寫指令／檔案／進度，`docs/` 寫 ROM 格式（含尚未解開的部分）；步驟、範本與分診結果見 `docs/PLAYBOOK.md`
- 共用工具在 `tools/`：`drive.py`（按鍵序列、截圖、dump、ROM 讀取追蹤）、`replay.py`（savestate 重播，驗證腳本共用）、`koei_lz.py`（KOEI LZ 解壓與找表，三國志II、武將風雲錄、航空霸業以外的作品都用它）、`triage.py`（ROM 分診）、`kaodata.py`
- 每款遊戲提供：人物資料、頭像（含 kaodata 資料集與驗證）、地點資料、大地圖、戰術地圖，以及分析或攻略用得到的表
- 外部資料（不是 ROM 解析出來的）欄位名加 `[EXT]` 前綴，並註明出處
- 輸出 CSV 用 UTF-8-BOM（Excel 相容）；匯出結果放各遊戲的 `output/`（不進版控）
- 解碼要有獨立驗證（模擬器跑遊戲本身的程式、截圖或 Mesen 紀錄）
- 模擬器：`tools/mesen.py` 用 ctypes 呼叫 Mesen 2 的 MesenCore（無頭、跑 Lua）。一個 process 只能開一次 Mesen，多輪比對用 savestate 重播；savestate 只能在 exec callback 裡建立／讀回（用 NMI handler），讀回後第一輪不生效，要多跑一輪丟掉
- 光榮的移植版先比對 FC 版（`~/works/famicom-re`）的已知資料表：SFC 三國志II 的劇本、州、戰場等表和 FC 版逐 byte 相同，直接拿 FC ROM 的表去 SFC ROM 裡搜尋就能定位
