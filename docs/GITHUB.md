# 原始碼同步

目的 repository 為 `released/I94124_NAU88C22_APM_demo_v0.0.5`，分支為 `main`。設定檔為根目錄 `github_repository.json`，重複更新入口為 `github_push.bat`；需要 Git、GitHub CLI、Python 3 與既有 GitHub 登入。

```bat
github_push.bat -CheckOnly
github_push.bat -Message "Update audio documentation"
```

- `-CheckOnly` 列出候選變更與檔案雜湊摘要，不改 index、建立 commit 或 push。遠端尚未建立時仍可預覽本機範圍。
- 更新模式檢查目的地、可見性、分支、歷史與遠端 ancestry，列出變更後要求輸入 repository 全名確認。
- 確認後只 stage 列出的檔案；若檔案在預覽後改變，或已有 staged work，會停止。
- 初次更新支援已確認的空遠端；後續更新不會自動 pull、merge 或 force push。
- 無變更時不建立重複 commit；push 後核對遠端 SHA。此入口不建立 repository、不建置韌體、不清除檔案。

## 原始碼範圍

| 納入 | 保留本機 |
|---|---|
| 兩份一般專案、所需 SDK、英文原始碼註解 | 原始錄音、截圖、原理圖、工程紀錄 |
| 各自的 Colsonic library／profile、SDK binary、共用 Keil `.uvoptx` | 未選用的 library 變體與個人 `.uvguix` 狀態 |
| README、完整流程、matrix 與操作文件 | 獨立診斷專案及其量測工具／保存映像 |
| Build／verify、相關測試原始碼、同步入口 | Compiler 輸出、IDE 個人狀態、Nu-Link 設定 |
| 第三方原始聲明與相依檔資訊 | 產生的 firmware BIN／HEX／AXF |

Public 韌體範圍需有對應版本與介面的實板驗收。上傳工具以本機驗收紀錄的來源摘要核對範圍；後續韌體變更需重新核對驗收。該紀錄保留本機，不包含在公開 checkout。

交付方式與 v0.0.2a 相同：必要的 library、profile、SDK 與 Keil 專案設定一併提供，完整 checkout 不需再另補相依 binary。

```powershell
python -B .\scripts\check_build_delivery.py --publication
```

上傳預覽及更新模式均檢查 build inputs，必要檔案被忽略、遺失或 binary 雜湊不同時會停止。只有明確列出的 binary／共用 options 可以納入，其他產物仍排除。

相依檔版本與原始聲明見[第三方組件](../THIRD_PARTY_NOTICES.md)。
