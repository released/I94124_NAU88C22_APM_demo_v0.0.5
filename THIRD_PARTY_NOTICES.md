# 第三方組件與建置相依檔

| 組件 | 位置與用途 | 原始聲明 |
|---|---|---|
| Nuvoton I94100 BSP | 根目錄 `Library/` 及 USB 範例的 `Library/`，提供 peripheral driver、device header 與啟動支援 | 保留各檔案原始 copyright 與使用條件 |
| Arm CMSIS | 兩份 SDK 的 `Library/CMSIS/` | 依各檔案原始 license／SPDX；例如 [core_cm4.h](Library/CMSIS/Include/core_cm4.h) 標示 Apache-2.0 |
| Colsonic APM | 各範例的 `Colsonic/`，包含封閉 AEC/NR library、header 與 profile 配套 | Sample package 未附獨立的 Colsonic redistribution license；各檔案依其原始聲明 |

- 本 repository 未對第三方組件另行授權；各檔案原始聲明持續適用。
- Colsonic library／profile 隨範例成套提供；本 repository 不替第三方組件另行授予使用或再散布權利。
- Compiler、Keil device pack 與供應商工具依各自條款取得，不隨 repository 提供。

## Colsonic 配套位置與版本

兩份一般專案已在以下目錄包含同一組相符檔案，保留完整 checkout 即可使用：

- `SampleCode/Template/Colsonic_16k_USB_UAC/Colsonic/`
- `SampleCode/Template/Colsonic_16k_I2S_I2C/Colsonic/`

| 檔案 | Bytes | SHA-256 |
|---|---:|---|
| `colsonic_apm_v0.0.5_20260213_0_0.lib` | 525132 | `4505a89e1d13d924057dcd8c660337c7ac8bae8dd9f07bcdd10057308dc9342e` |
| `colsonicdata.bin` | 728 | `ec533a82819a0940c44b879bd0a16485a5d4699065f9781f192600dad2b62af6` |

- Library、profile、header 與 memory pool 需成套使用；同名檔案不代表內容相同。
- `VERIFY.ps1` 依 SHA-256 檢查兩份相依檔；缺少檔案或內容不同時會停止。
- Repository 提供實際 library／profile，沒有用 stub 演算法替代。
- USB SDK 保留與 v0.0.2a 相同的 `Library/CMSIS/Lib/ARM/arm_cortexM4lf_math.lib`；目前兩份 project 的顯式 library link 指向上表 Colsonic library。
