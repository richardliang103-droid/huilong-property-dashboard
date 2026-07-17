import json
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / 'Library/CloudStorage/SynologyDrive-Hermes/Houses/迴龍物件追蹤.xlsx'
DEST = ROOT / 'data/properties.json'

def clean(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value

def read_sheet(ws):
    headers = [cell.value for cell in ws[1]]
    rows = []
    for values in ws.iter_rows(min_row=2, values_only=True):
        if not any(value is not None for value in values):
            continue
        rows.append({header: clean(values[i]) for i, header in enumerate(headers) if header})
    return rows

def main():
    if not SOURCE.exists():
        raise SystemExit(f'Excel not found: {SOURCE}')
    workbook = load_workbook(SOURCE, data_only=True)
    payload = {
        'generated_at': datetime.now().isoformat(),
        'source': '本機迴龍物件追蹤.xlsx',
        'active': read_sheet(workbook['架上']),
        'removed': read_sheet(workbook['已下架']),
        'price_changes': read_sheet(workbook['價格變動']),
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"exported active={len(payload['active'])} removed={len(payload['removed'])} price_changes={len(payload['price_changes'])}")

if __name__ == '__main__':
    main()
