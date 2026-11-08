# Colsonic_ns_set 與一般專案設定

## 現行設定

| 一般專案 | 呼叫位置 | NS 值 | Startup stack |
|---|---|---|---|
| USB UAC | `Colsonic_Init()` | `0.85f` | 4 KB |
| I2C/I2S | `Colsonic_Init()`、`Stop_Audio()` | `0.85f` | 4 KB |

- `Colsonic_apm_init()` 完成後套用 NS preset；I2C 的 Stop 路徑重新初始化 APM 時會重新套用相同數值。
- USB 正常上行為左 Near、右 Decode；I2C 正常模式相同，bypass 為左 Far、右 Near。
- 原有 UART command／tuning 保留；一般專案的編譯清單不包含 AudioDiag 的 RAM 擷取與額外計時來源。
- 修改位置為 [USB misc.c](../SampleCode/Template/Colsonic_16k_USB_UAC/Util/misc.c) 與 [I2C misc.c](../SampleCode/Template/Colsonic_16k_I2S_I2C/Util/misc.c)。
- Stack 位於各一般專案 `KEIL/startup_I94100.s` 的 `Stack_Size`，值為 `0x00001000`。

## API 語意與證據範圍

供應商 Application 的 header 宣告 `uint32_t Colsonic_ns_set(float percent)`，範例在 APM 初始化後傳入 `0.1`，未完整說明參數的聲學尺度。

針對本專案所用 v0.0.5 binary 的靜態觀察：

- 一般有限輸入的接受範圍為 `0 < percent <= 1`；超出範圍會回傳 `1`。
- `0` 不是這支函式接受的關閉值。
- 成功或無需更新時回傳 `0`；內部會比較目前值，差異較小時可能維持既有狀態。
- 相關條件分支使用非線性係數；`0.85f` 不代表固定降噪百分比、衰減 dB，效果也不能由 `0.75f` 與 `1.0f` 線性推估。
- 上述結果限定於目前 binary，不能當成所有版本的正式 API 規格。有效值、動態更新條件與 thread-safety 仍以供應商規格為準。

移除 setter 會保留初始化載入的參數，不能據此視為關閉 NS。I2C command `0x13` 則選擇上行訊號；bypass 仍會執行 APM，與 NS preset 為不同功能。

## 調整方向

| 方向 | 對目前 v0.0.5 binary 的意義 | 聲學取捨 |
|---|---|---|
| 往 `1.0f` 增加 | 在相關抑制分支中加強衰減 | 背景可能更低；現場語音也可能過度削弱 |
| 降低數值 | 在該分支中減少衰減 | 保留較多語音細節；背景殘留也可能增加 |
| 維持 `0.85f` | 兩份一般專案採用的 preset | 仍需依實際播放、增益與雙講條件評估效果 |

- 此方向來自本 binary 的靜態分析及對應使用條件，並非供應商對所有版本的聲學保證。
- 相關分支使用非線性係數，不能將 `0.85f` 解讀成 85% 降噪，或從數值推算固定 dB。
- API 會同時影響混合訊號中的語音與背景，沒有「只壓背景、人聲完全不變」的保證。
- Far 缺少實際播放參考、Near／Far 配對時序或雙講行為異常，不能單靠增加 NS 值解決。
- GUI 的 Pre-NS／Post-AEC Performance 參數與本 setter 的尺度、路徑不同，不能直接換算。現有 UART handler 也沒有將 GUI 參數轉成此 setter 呼叫。

## 修改位置

1. 同步修改 USB `Colsonic_Init()`、I2C `Colsonic_Init()` 與 I2C `Stop_Audio()` 三處的 `Colsonic_ns_set()` 參數。
2. 保留「先 `Colsonic_apm_init()`、再設定 preset」的順序；只改開機值會讓 I2C Stop 重設後回到另一個值。
3. 同步調整 `scripts/verify_apm_settings.py` 的預期值／float literal 檢查，再 Rebuild 與核對兩份映像。
4. 固定板卡、錄音與播放路徑、音量、麥克風／喇叭位置，以背景單獨播放、現場人聲及雙講三組情境比較。

這是韌體 preset；現有 I2C command 沒有提供任意 float 調整入口。動態更新的執行緒安全與可用時機尚無完整供應商規格，不在 IRQ 中任意加入呼叫。

## 建置與核對

從專案根目錄執行：

```powershell
.\BUILD.ps1 -Target All
.\VERIFY.ps1 -Target All
```

- `BUILD.ps1` 重建兩份一般專案並執行驗證，正式產物位於各自 `KEIL/obj/`。
- `VERIFY.ps1` 檢查來源 preset、反組譯中的實際傳參與 BIN 的 float literal，涵蓋 USB 初始化及 I2C 初始化／Stop 重設三個呼叫點。
- 同時檢查 linker map 的 4096-byte stack、library／profile 雜湊、Flash／RAM 範圍與 HEX，以及一般映像未連入 AudioDiag 符號。
- 一般專案不連入獨立 AudioDiag 的 RAM 擷取或額外 PDMA 計時來源。

## 聲學驗證

- 背景抑制、人聲保留與雙講表現取決於實際聲學條件，不能從 preset 或編譯結果單獨推定。
- A/B 比較固定板卡、播放路徑、錄音軟體、格式、音量與麥克風／喇叭位置，記錄背景單獨播放及現場人聲加入的時間。
- Near／Decode 的音量差是混合訊號變化，不能直接當成 AEC-only ERLE 或純人聲衰減量。
- Far 參考、Near／Far 時序與 PDMA 狀態需要對應的訊號／RAM 證據；建置與靜態檢查不代替實板驗證。
