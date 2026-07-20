import json
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / 'Library/CloudStorage/SynologyDrive-Hermes/Houses/迴龍物件追蹤.xlsx'
STATUS_SOURCE = Path.home() / '.hermes/profiles/argus/data/huilong_watch_status.json'
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


def read_source_health():
    try:
        data = json.loads(STATUS_SOURCE.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('sources'), dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None

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
        'source_health': read_source_health(),
    }
    workbook.close()

    # Avoid a daily Git commit and Vercel deployment when the workbook data is
    # identical. Preserve the previous timestamp so the JSON remains unchanged.
    if DEST.exists():
        try:
            previous = json.loads(DEST.read_text(encoding='utf-8'))
            if all(previous.get(key) == payload.get(key) for key in ('source', 'active', 'removed', 'price_changes', 'source_health')):
                payload['generated_at'] = previous.get('generated_at', payload['generated_at'])
        except (json.JSONDecodeError, OSError):
            pass

    DEST.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if DEST.exists() and DEST.read_text(encoding='utf-8') == serialized:
        print('dashboard data unchanged')
        return
    DEST.write_text(serialized, encoding='utf-8')
    print(f"exported active={len(payload['active'])} removed={len(payload['removed'])} price_changes={len(payload['price_changes'])}")

if __name__ == '__main__':
    main()
