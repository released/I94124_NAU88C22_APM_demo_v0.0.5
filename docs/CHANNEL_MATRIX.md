# 聲道、RAM 與 PDMA buffer matrix

適用：本目錄 v0.0.5 的 I2S/I2C 與 USB-UAC target，16 kHz、16-bit PCM。
本文件說明兩份 NAU88C22 一般專案的聲道契約與傳輸 buffer。

## 1. 訊號與左右聲道

Near 是麥克風送入 APM 前的 PCM，可能同時包含本地人聲、喇叭回音與環境噪音；
「處理前」指 Colsonic APM 前，仍已經過 codec ADC、增益與硬體濾波。
Far 是準備送到 codec DAC 的播放音樂數位參考。Decode 是 APM 的單聲道 AEC/NR 輸出，
沿用原程式命名，與語音辨識文字或音訊檔案解碼無關。

Left/Right 是送給 Host 的兩個觀察 slot，不代表兩支麥克風，也不固定代表 Near/Far。
`u32Decode` 名稱雖包含 Decode，實際存放的是「選好左右聲道的 stereo words」。

## 2. 模式 matrix：Host 最後收到什麼

| 模式 | 左聲道 | 右聲道 | 左聲道 RAM 來源 | 右聲道 RAM 來源 | 切換方式 |
|---|---|---|---|---|---|
| USB 正常 | Near：麥克風處理前 | Decode：AEC/NR 處理後 | `pu16Near[i]` → `u16NearI2STmp[row][i]` | `u16DecodeTmp[i]` | USB record 啟用後固定此格式 |
| I²C/I²S 正常 | Near：麥克風處理前 | Decode：AEC/NR 處理後 | `pu16Near[i]` → `u16NearI2STmp[row][i]` | `u16DecodeTmp[i]` | I²C write `13 01 01`；亦為開機預設 |
| 僅 I²C/I²S 的 bypass | Far：播放音樂參考 | Near：麥克風處理前 | `pu16Far[i]` → `u16FarI2STmp[row][i]` | `pu16Near[i]` → `u16NearI2STmp[row][i]` | I²C write `13 01 00` |

每列都先由 `Colsonic_apm_proc(Near, Far, Decode)` 產生 Decode，再選擇輸出。
bypass 只改 uplink 封裝，APM 仍運算；不是獨立 NR off，也不關閉喇叭播放。
USB 沒有 bypass 分支或 I²C 0x13 入口。

embedded host 正常與 bypass 都固定取 **右聲道語音**：
正常是 Decode，bypass 是 Near。左聲道用於觀察正常的 raw Near 或 bypass 的 Far。
舊版 I²C 正常若取左聲道 Decode，升級後必須改取右聲道。

## 3. 模式 × 輸出 RAM／PDMA matrix

下表的 `q` 是 `u32Decode` write row，`d` 是傳輸 row，兩者各自交替，不能視為同一 index。
`u16DecodeBufRIdx` 在 640 個 stereo words 間前進，每次 callback 消費 32 words。

| 模式／板型 | 封裝 RAM：每 frame 320 words | 後段 RAM：每次 32 words | 直接讀取該 RAM 的傳輸機制 | Host 介面 |
|---|---|---|---|---|
| USB 正常／NAU88C22 | `u32Decode[q][i] = Pack(Near, Decode)` | CPU 將 32 words 搬入 `g_sUacRecord.au8USB_RingBuff`，共 128 bytes | EP2 handler 再以 CPU copy 到 USB endpoint buffer；**沒有 USB PDMA channel** | PC 錄音：L Near / R Decode |
| I²C 正常／NAU88C22 | `u32Decode[q][i] = Pack(Near, Decode)` | `au32SPI_I2S_Tx_Buff[d][0..31]`，不再交換兩半 | PDMA ch7 → SPI2 TX | embedded I²S：L Near / R Decode |
| I²C bypass／NAU88C22 | `u32Decode[q][i] = Pack(Far, Near)` | 同一組 `au32SPI_I2S_Tx_Buff` | PDMA ch7 → SPI2 TX | embedded I²S：L Far / R Near |

USB record ring 在 codec RX callback 中填入；這只是 CPU 搬送的執行時機，
不表示 codec RX PDMA 直接將 Decode 搬進 USB。
I²C Host TX 資料不足時補整個 32-word row 為零；USB Decode queue 不足時也向 record ring 補零。
因此剛開機或 underrun 時，Host 可能收到左右都為零，不能據此判斷聲道對調。

## 4. 訊號來源 RAM matrix

以下 `g_sDataManager.` 前綴省略，指各 target 的獨立 instance。

| 資料 | 最早對應的 PDMA buffer | CPU 累積／計算 RAM | 發布給 APM 的項目 | 生產者 → 消費者 |
|---|---|---|---|---|
| Near | `au32I2S_Rx_Buff[2][32]`，取每 word 低 16 bits | `u16NearI2STmp[2][320]` | `pu16Near` 指向已完成 row | codec RX callback → main APM／左聲道或 bypass 右聲道 |
| Far | `au32I2S_Tx_Buff[2][32]`，取準備播放 word 的低 16 bits | `u16FarI2STmp[2][320]` | `pu16Far` 指向已完成 row | codec TX callback → main APM／bypass 左聲道 |
| Decode | 無直接對應的 PDMA buffer | `u16DecodeTmp[320]` | APM 第三個參數 | main APM → main 正常右聲道封裝 |
| Stereo uplink | I²C 後段為 `au32SPI_I2S_Tx_Buff`；USB 無對應 PDMA | `u32Decode[2][320]` | `u16DecodeAvalCnt`／read index／write row | main → I²C Host TX callback 或 USB codec RX callback |

Far 取自 codec TX refill 後的內容，已反映該處的補零；I²C target 的 speaker mute 也會反映到 Far。
它不是第二支麥克風，也不是從 codec ADC 右聲道回錄的 analog loopback。
若 Host 播不同內容的 stereo，而 AEC 只取左聲道 Far，右邊喇叭的獨立聲音沒有完整參考；
驗證時先用左右相同的 mono 音樂，並確認實際喇叭路徑。

## 5. Active buffer 容量與單位 matrix

| Buffer | C 型別／維度 | Bytes | 16 kHz 對應時間 | 硬體 PDMA 是否直接讀寫 |
|---|---|---:|---|---|
| codec RX `au32I2S_Rx_Buff` | `uint32_t [2][32]` | 256 | 每 row 2 ms；總容量 4 ms | 是，ch0 寫入 |
| codec TX `au32I2S_Tx_Buff` | `uint32_t [2][32]` | 256 | 每 row 2 ms；總容量 4 ms | 是，ch1 讀取 |
| I²C Host RX `au32SPI_I2S_Rx_Buff` | `uint32_t [2][32]` | 256 | 每 row 2 ms | 是，ch6 寫入 |
| I²C Host TX `au32SPI_I2S_Tx_Buff` | `uint32_t [2][32]` | 256 | 每 row 2 ms | 是，ch7 讀取 |
| Near `u16NearI2STmp` | `uint16_t [2][320]` | 1280 | 每 row 20 ms；總容量 40 ms | 否，CPU 從 codec RX 累積 |
| Far `u16FarI2STmp` | `uint16_t [2][320]` | 1280 | 每 row 20 ms；總容量 40 ms | 否，CPU 從 codec TX 累積 |
| Decode `u16DecodeTmp` | `uint16_t [320]` | 640 | 單聲道 20 ms | 否，APM 寫入 |
| Stereo `u32Decode` | `uint32_t [2][320]` | 2560 | 640 stereo frames，共 40 ms | 否，先經 CPU 搬入後段 buffer |
| USB playback `g_sUacPlayback.au32USB_RingBuff` | `uint32_t [240]` | 960 | 15 ms | 否，EP3 → CPU → codec TX |
| USB record `g_sUacRecord.au8USB_RingBuff` | `uint8_t [2560]` | 2560 | 40 ms，並非 80 ms | 否，CPU → EP2 |

1 stereo word = 左 16 bits + 右 16 bits = 4 bytes。
APM 一次 320 個**單聲道 samples**，封裝後則是 320 個 **stereo words**。
10 次 32-word callback 才累積一個 20 ms APM frame。
以上容量不是系統總 RAM 用量；另有 87,040-byte APM pool、其他 state、stack、descriptor 與未啟用分支的欄位。

Counter 單位：`u16DecodeAvalCnt` 與 I²C Host RX count 用 stereo words；
USB playback count 也用 stereo words；USB record count 用 bytes。
不能將 USB record 的 128-byte 增量誤寫成 128 samples。

## 6. PDMA channel 與 descriptor matrix

descriptor 固定位址是控制結構的位址，**不是 PCM buffer 的位址**。
每個 descriptor 16 bytes，每組兩個 descriptor 共 32 bytes。
實際 PCM buffers 在 `g_sDataManager` 內，位址依 target link map 決定。

| 路徑／啟用範圍 | PDMA ch | 方向 | 直接 RAM buffer | descriptor 名稱／起址 |
|---|---:|---|---|---|
| codec RX／所有 target | 0 | I2S0 RXFIFO → RAM | `au32I2S_Rx_Buff` | `DMA_I2S0RXDESC[2]`／0x20000120 |
| codec TX／所有 target | 1 | RAM → I2S0 TXFIFO | `au32I2S_Tx_Buff` | `DMA_I2S0TXDESC[2]`／0x20000100 |
| C22 I²C Host RX | 6 | SPI2 RX → RAM | `au32SPI_I2S_Rx_Buff` | `DMA_SPI2I2SRXDESC[2]`／0x200001A0 |
| C22 I²C Host TX | 7 | RAM → SPI2 TX | `au32SPI_I2S_Tx_Buff` | `DMA_SPI2I2STXDESC[2]`／0x20000180 |
| USB EP2／EP3／EP4 | 無 | USB peripheral ↔ CPU copy | USB endpoint buffer 與 rings | 無 PDMA descriptor |

每 row 使用 `PDMA_WIDTH_32`、TXCNT=31，代表 32 次 32-bit transfer，共 128 bytes。
TX callback 填的是剛完成、下一輪才送出的 row；RX callback 讀的是剛接收完成的 row。
兩 row 輪替時，完成後通常只有另一 row 的 2 ms 可以處理，不能把 4 ms 容量當作 4 ms deadline。
DMIC／DPWM 與另一組 SPI 的宣告，不代表目前 target 有啟用。

## 7. 封裝與 Host 解讀 matrix

共同 helper：[audio_channel.h](../SampleCode/Template/audio_channel.h) 的 `Audio_PackStereo(left,right)`：
`(uint32_t)left | ((uint32_t)right << 16)`。
先轉 unsigned 32-bit 再 shift，保留負 PCM 的原始 16-bit bit pattern。

| 範例 | 左 16 bits | 右 16 bits | RAM 32-bit word | USB little-endian bytes |
|---|---|---|---|---|
| 正常：Near=0x1111，Decode=0x3333 | 0x1111 | 0x3333 | 0x33331111 | 11 11 33 33 |
| bypass：Far=0x2222，Near=0x1111 | 0x2222 | 0x1111 | 0x11112222 | 22 22 11 11 |

I²S 依 serial LRCK/frame 格式傳送，不使用上表的 USB byte order 解讀。
軟體契約是低半 word 對應左、高半 word 對應右；上板仍須用已知辨識碼／tone，
核對 I²S LRCK 極性、接收端 slot 與左右順序。未完成此量測前，不宣稱實體已驗證。

## 8. 現有時序限制與驗證

目前 I²C 由 NearReady 觸發，USB 由 RX callback 檢查 NearReady/FarReady，
兩者都沒有 frame sequence/ownership 保證；main 與 IRQ 的 count 也有競態與滿載邊界風險。
聲道封裝不保證已完成時間對齊；相關交接條件見 [共用流程](FLOW.md)。

`tests/RUN_CHANNEL_TESTS.ps1` 會擷取實際 Work_Handle，
驗證 320 samples 封裝、signed PCM bits、兩個 row、I²C bypass 與 USB 無 bypass。
APM 在 host test 中使用 deterministic stub；測試不驗證真實 AEC/NR、IRQ 競態或實體 I²S。
實板驗收流程見 [GOLDWAVE_TEST.md](GOLDWAVE_TEST.md)。

原始碼索引：
[I²C state](../SampleCode/Template/Colsonic_16k_I2S_I2C/Util/data_handler.h)、
[I²C callbacks](../SampleCode/Template/Colsonic_16k_I2S_I2C/Util/pdma_handler.c)、
[I²C descriptors](../SampleCode/Template/Colsonic_16k_I2S_I2C/Util/pdma_init.c)、
[USB state](../SampleCode/Template/Colsonic_16k_USB_UAC/Util/data_handler.h)、
[USB callbacks](../SampleCode/Template/Colsonic_16k_USB_UAC/Util/pdma_handler.c)、
[USB endpoints](../SampleCode/Template/Colsonic_16k_USB_UAC/Util/AudioClass.c)。

