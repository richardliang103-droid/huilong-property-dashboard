import json
import re
from datetime import datetime
from itertools import combinations
from pathlib import Path
from urllib.parse import urlparse
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


GENERIC_COMMUNITIES = {'住宅', '住宅大樓', '大樓', '近公園', '近捷運', '未知'}
AREA_FIELDS = ('主建坪', '陽台坪', '雨遮坪', '公設坪', '車位坪')


def normalized_text(value):
    """Normalise public-listing text without using it as a sole identifier."""
    if value is None:
        return ''
    return re.sub(r'[\s\u200b\-－_,，.。()（）]', '', str(value)).replace('臺', '台').lower()


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def close(left, right, tolerance=0.1):
    left, right = number(left), number(right)
    return left is not None and right is not None and abs(left - right) <= tolerance


def known_community(item):
    community = normalized_text(item.get('社區名稱'))
    return community if community and community not in {normalized_text(value) for value in GENERIC_COMMUNITIES} else ''


def source_names(item):
    return [name.strip() for name in str(item.get('來源網站') or '').split('/') if name.strip()]


def source_name_from_url(url):
    host = urlparse(str(url or '')).netloc.lower()
    if 'sinyi.com.tw' in host:
        return '信義房屋'
    if 'yungching.com.tw' in host:
        return '永慶房屋'
    if 'hbhousing.com.tw' in host:
        return '住商不動產'
    if 'twhg.com.tw' in host:
        return '台灣房屋'
    if 'u-trust.com.tw' in host:
        return '有巢氏房屋'
    return None


def listing_sources(item):
    """Preserve every original source URL when a card represents multiple ads."""
    sources = item.get('來源物件')
    if isinstance(sources, list):
        return sources
    names = source_names(item)
    # Older Excel rows sometimes state that an ad was seen on several sites
    # but retain only one URL. Preserve the source without a URL as an explicit
    # non-clickable record; never assign one broker's URL to another broker.
    if len(names) > 1:
        url = item.get('來源連結')
        known_source = source_name_from_url(url)
        records = []
        if known_source and known_source in names:
            records.append({'網站': known_source, '連結': url, '標題': item.get('標題')})
        for source in names:
            if source != known_source:
                records.append({'網站': source, '連結': None, '標題': item.get('標題'), '狀態': '網址未保存'})
        return records or [{'網站': '/'.join(names), '連結': url, '標題': item.get('標題')}]
    return [{
        '網站': source,
        '連結': item.get('來源連結'),
        '標題': item.get('標題'),
    } for source in names] or [{
        '網站': item.get('來源網站') or '未知來源',
        '連結': item.get('來源連結'),
        '標題': item.get('標題'),
    }]


def source_quality(item):
    """Prefer the record with the most useful registered-property fields."""
    fields = ('社區名稱', '地址', '主建坪', '陽台坪', '雨遮坪', '公設坪', '車位坪', '車位型', '座向')
    score = sum(bool(item.get(field)) for field in fields)
    return score + (2 if known_community(item) else 0)


def comparison(left, right):
    """Return high-confidence same-home evidence, or ``None``.

    A public listing commonly hides the door number, so the rule deliberately
    requires the same floor, building area, a community signal and either two
    registered-area components or matching address/price/age.  This catches
    cross-broker duplicates while keeping lookalikes out of the dashboard.
    """
    if normalized_text(left.get('樓層')) != normalized_text(right.get('樓層')):
        return None
    if not close(left.get('建坪'), right.get('建坪'), 0.1):
        return None

    left_community, right_community = known_community(left), known_community(right)
    left_title, right_title = normalized_text(left.get('標題')), normalized_text(right.get('標題'))
    community_matched = bool(
        left_community and right_community and left_community == right_community
    ) or bool(left_community and left_community in right_title) or bool(
        right_community and right_community in left_title
    )
    if not community_matched:
        return None

    reasons = ['同樓層', '建坪一致', '社區名稱或標題一致']
    score = 56
    component_matches = 0
    for field in AREA_FIELDS:
        # Zero often means the source did not publish the field, not 0 坪.
        if number(left.get(field)) and number(right.get(field)) and close(left.get(field), right.get(field), 0.1):
            component_matches += 1
            score += 5
            reasons.append(f'{field}一致')
    if normalized_text(left.get('地址')) and normalized_text(left.get('地址')) == normalized_text(right.get('地址')):
        score += 8
        reasons.append('地址路段一致')
    if close(left.get('總價(萬)'), right.get('總價(萬)'), 1):
        score += 5
        reasons.append('開價一致')
    if close(left.get('屋齡(年)'), right.get('屋齡(年)'), 1):
        score += 3
        reasons.append('屋齡一致')
    if normalized_text(left.get('車位型')) and normalized_text(left.get('車位型')) == normalized_text(right.get('車位型')):
        score += 5
        reasons.append('車位型一致')

    # Public sources with sparse area data can still be grouped only when the
    # independent address, price and age signals all agree.
    sparse_but_decisive = all(reason in reasons for reason in ('地址路段一致', '開價一致', '屋齡一致'))
    if score < 70 or (component_matches < 2 and not sparse_but_decisive):
        return None
    return {'score': score, 'reasons': reasons}


def deduplicate_active(rows):
    """Return UI records plus an audit summary without changing the workbook."""
    comparisons_map = {}
    for left_index, right_index in combinations(range(len(rows)), 2):
        result = comparison(rows[left_index], rows[right_index])
        if result:
            comparisons_map[(left_index, right_index)] = result

    # Complete-link grouping prevents a weak A~B~C chain from merging A and C.
    # A single well-described record may additionally act as an anchor for
    # sparse broker records, but only when it independently matches every
    # member of the proposed group.
    groups = [{index} for index in range(len(rows))]
    for (left_index, right_index), _ in sorted(comparisons_map.items(), key=lambda item: item[1]['score'], reverse=True):
        left_group = next(group for group in groups if left_index in group)
        right_group = next(group for group in groups if right_index in group)
        if left_group is right_group:
            continue
        proposed = left_group | right_group
        complete_link = all(comparisons_map.get(tuple(sorted((left, right)))) for left in left_group for right in right_group)
        anchored = any(
            source_quality(rows[anchor]) >= 7 and all(
                anchor == other or comparisons_map.get(tuple(sorted((anchor, other))))
                for other in proposed
            )
            for anchor in proposed
        )
        if complete_link or anchored:
            groups.remove(left_group)
            groups.remove(right_group)
            groups.append(left_group | right_group)

    deduplicated = []
    for group in sorted(groups, key=lambda item: min(item)):
        members = [rows[index] for index in sorted(group)]
        primary = dict(max(members, key=source_quality))
        if len(members) == 1:
            primary['來源物件'] = listing_sources(primary)
            primary['同戶判定'] = None
            primary['同戶比對理由'] = []
            deduplicated.append(primary)
            continue

        pair_evidence = [
            comparisons_map[tuple(sorted(pair))]
            for pair in combinations(sorted(group), 2)
            if tuple(sorted(pair)) in comparisons_map
        ]
        names = []
        for member in members:
            for name in source_names(member):
                if name not in names:
                    names.append(name)
        primary['來源網站'] = '/'.join(names)
        primary['來源物件'] = [source for member in members for source in listing_sources(member)]
        primary['同戶判定'] = '高度可能同戶'
        primary['同戶比對理由'] = sorted({reason for evidence in pair_evidence for reason in evidence['reasons']})
        primary['重複刊登數'] = len(members)
        primary['首次出現'] = min(str(member.get('首次出現') or '') for member in members) or None
        primary['最後更新'] = max(str(member.get('最後更新') or '') for member in members) or None
        deduplicated.append(primary)

    return deduplicated, {
        'raw_active_count': len(rows),
        'unique_active_count': len(deduplicated),
        'merged_listing_count': len(rows) - len(deduplicated),
        'merged_group_count': sum(len(group) > 1 for group in groups),
    }

def main():
    if not SOURCE.exists():
        raise SystemExit(f'Excel not found: {SOURCE}')
    workbook = load_workbook(SOURCE, data_only=True)
    active, deduplication = deduplicate_active(read_sheet(workbook['架上']))
    payload = {
        'generated_at': datetime.now().isoformat(),
        'source': '本機迴龍物件追蹤.xlsx',
        'active': active,
        'removed': read_sheet(workbook['已下架']),
        'price_changes': read_sheet(workbook['價格變動']),
        'source_health': read_source_health(),
        'deduplication': deduplication,
    }
    workbook.close()

    # Avoid a daily Git commit and Vercel deployment when the workbook data is
    # identical. Preserve the previous timestamp so the JSON remains unchanged.
    if DEST.exists():
        try:
            previous = json.loads(DEST.read_text(encoding='utf-8'))
            if all(previous.get(key) == payload.get(key) for key in ('source', 'active', 'removed', 'price_changes', 'source_health', 'deduplication')):
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
