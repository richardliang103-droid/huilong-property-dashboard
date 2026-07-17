# 迴龍房屋監控 Dashboard

公開、唯讀的迴龍站周邊房屋監控頁面。

## 資料來源

- 本機 Excel：`~/Library/CloudStorage/SynologyDrive-Hermes/Houses/迴龍物件追蹤.xlsx`
- `data/properties.json` 只放前端展示所需欄位，不上傳 Excel 原檔。
- 目前資料由房屋監控爬蟲匯出，包含信義房屋與永慶房屋。

## 本機更新資料

在房屋監控流程完成後重新匯出：

```bash
source ~/.hermes/venvs/web-clipper/bin/activate
python3 scripts/export_excel.py
```

## 本機預覽

```bash
python3 -m http.server 4173
```

開啟 <http://localhost:4173>。

## 部署

這是純靜態網站，可直接連接 GitHub 後由 Vercel 自動部署。
