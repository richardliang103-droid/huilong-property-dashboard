# 迴龍房屋監控 Dashboard

公開、唯讀的迴龍站周邊房屋監控頁面。

## 資料來源

- 本機 Excel：`~/Library/CloudStorage/SynologyDrive-Hermes/Houses/迴龍物件追蹤.xlsx`
- `data/properties.json` 只放前端展示所需欄位，不上傳 Excel 原檔。
- 目前資料由房屋監控爬蟲匯出，包含信義房屋、永慶房屋與台灣房屋。
- 匯出時會保守群組跨仲介的同戶刊登；原始 Excel 不會被改寫。只有同社區訊號、同樓層、同建坪，且權狀拆分或地址／開價／屋齡交叉吻合的刊登才會合併為「高度可能同戶」。

## 本機更新資料

在房屋監控流程完成後重新匯出。若 Excel 資料未變動，匯出器不會建立新的 Git 提交或觸發 Vercel 部署：

```bash
source ~/.hermes/venvs/web-clipper/bin/activate
python3 scripts/export_excel.py
```

匯出的卡片會保留各仲介的原始連結與判定理由；欄位不足、證據不夠的物件維持分開，不會因為標題或格局相似而合併。

## 本機預覽

```bash
python3 -m http.server 4173
```

開啟 <http://localhost:4173>。

## 部署

這是純靜態網站，可直接連接 GitHub 後由 Vercel 自動部署。
