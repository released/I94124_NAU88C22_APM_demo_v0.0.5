# GoldWave 與 embedded I²S 驗證

依據 [CHANNEL_MATRIX.md](CHANNEL_MATRIX.md)：
正常 USB 與 I²C/I²S 均為左 Near、右 Decode；只有 I²C/I²S bypass 為左 Far、右 Near。
本文件說明訊號觀察方法與判讀範圍。

## PC／USB 接法與錄音

1. 燒錄對應板型的 USB-UAC target，PC 接 MCU 的 USB 音訊介面。
2. 將音樂播放裝置及 GoldWave 錄音裝置選為同一塊 MCU 的 UAC。
   錄音採 16 kHz、16-bit、**stereo**，保留兩個聲道，不要 downmix 成 mono。
3. 音樂必須經 MCU → codec DAC → 喇叭，才能讓目前的 Far 路徑取得相同數位參考。
   單由 PC 內建喇叭播放、沒有送進 MCU，不能用這套 Far 驗證 AEC。
4. 初次測試用左右相同的 mono 音樂，因目前 Far 只取 codec TX 的低 16 bits。
   錄音端關閉可關閉的自動增益、降噪、音效及監聽迴送，保持兩聲道相同 gain。
5. 固定 mic／喇叭距離、播放音量與 codec 設定。先確認 raw Near 無 clipping；
   飽和的麥克風資料不能靠 AEC 恢復。不同板型的 analog gain 不同，需各自建立基準。
6. 同時錄到兩聲道後，GoldWave 左聲道看處理前 Near，右聲道看 AEC/NR 後 Decode。
   保存原始 stereo WAV，再複製供分開聆聽／分析，避免覆寫原錄音。

GoldWave 看到的是韌體送出的兩個觀察訊號，不是 Far 在左、Near 在右的固定定義。

## 測試 matrix

| 場景 | 喇叭播放 | 本地講話 | 左 Near 觀察 | 右 Decode 觀察 | 判讀目的 |
|---|---|---|---|---|---|
| 安靜基準 | 無 | 無 | codec／環境底噪、是否削波 | 處理後底噪 | 建立 noise floor，不能只憑音量定義 NR 強度 |
| 背景噪音 | 無 | 無，另有可重現噪音源 | 同一噪音條件 | 噪音殘留與音色 | 看 NR 影響；目前不是獨立關閉 AEC 的測試 |
| 只有人聲 | 無 | 有 | 原始語音 | 語音清晰度、失真、斷字 | 確認語音保留 |
| 只有音樂 | 有 | 無 | 喇叭回音 | 回音殘留、收斂過程 | 確認 AEC 對播放回音的抑制 |
| 音樂加人聲／雙講 | 有 | 有 | 語音、回音與噪音混合 | 人聲保留、回音殘留與抽吸感 | 驗證實際使用情境 |
| 播放停止／重新開始 | 切換 | 可重現的固定語音 | 原始變化 | 瞬態、恢復與異音 | 看狀態切換 |

不要只用「右邊比較小聲」當通過條件：它也可能是語音一起被壓低。
Near 與 Decode 的相同 sample index 不保證聲學對齊，library 內部 delay 未知；
比較波形／能量前需估計 delay，不能直接相減或要求兩者相等。
AEC 與 NR 在同一 library 處理，這份比較反映整體效果，不直接分離兩者貢獻。

建議每次記錄：板型、target、library/data hash、音量、mic／speaker 距離、測試素材、
GoldWave 格式、左右聲道、clipping／中斷現象，以及對應錄音檔名。
ERLE、SNR 與可接受延遲需由對應場景及對齊後的量測定義。

## embedded I²S 對照驗證

| 操作 | I²C write bytes | 預期 embedded 左／右 | 必查 buffer |
|---|---|---|---|
| 啟動 | `12 01 01` | 依目前模式；開機預設正常 | codec RX/TX 與 Host RX/TX 持續更新 |
| 正常 | `13 01 01` | Near／Decode | `u32Decode` → `au32SPI_I2S_Tx_Buff` |
| bypass | `13 01 00` | Far／Near | 同一 TX 路徑，右側改成 raw mic |
| 恢復正常 | `13 01 01` | Near／Decode | 確認沒有再次交換左右 |
| 停止 | `12 01 00` | 停止 streaming | 確認 clock/data 停止方式與接收端相容 |

I²C 7-bit slave 主位址 0x15，封包格式為 command／length／data。
embedded MCU 固定接收右聲道作語音；左聲道保留作 debug。
切換時 queue 內可能仍有舊模式資料，應待新模式穩定後擷取比較；目前沒有 frame-boundary
切換標記，不能宣稱命令一到所有 buffer 立即改變。

先用邏輯分析儀確認 16 kHz LRCK、16-bit stereo、I²S data delay、左右 slot，
並以已知不同辨識碼核對 RAM 與接收端；不能把 CPU little-endian byte order 當 I²S serial bit order。
NAU88C22 Host 是 SPI2（PDMA RX ch6／TX ch7）。MCU 為 I²S master，embedded receiver 配合 slave。
Host test 驗證軟體封裝；實體聲道與時序由板上量測判定。

