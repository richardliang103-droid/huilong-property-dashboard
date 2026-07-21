import unittest

from export_excel import deduplicate_active, listing_sources


def listing(listing_id, **overrides):
    item = {
        'id': listing_id,
        '社區名稱': '捷運上郡',
        '格局': '3房2廳2衛1室',
        '建坪': 51.01,
        '主建坪': 27.73,
        '陽台坪': 2.23,
        '雨遮坪': 0.38,
        '公設坪': 12.16,
        '車位坪': 8.51,
        '車位型': '坡道平面',
        '總價(萬)': 2598,
        '樓層': '13/15',
        '屋齡(年)': 16,
        '地址': '新北市新莊區中正路',
        '來源網站': '信義房屋',
        '來源連結': f'https://example.test/{listing_id}',
        '標題': '捷運上郡高樓三房車位',
    }
    item.update(overrides)
    return item


class DeduplicateActiveTests(unittest.TestCase):
    def test_groups_the_three_huilong_cross_broker_listings(self):
        sinyi = listing('sinyi')
        yungching = listing('yungching', 社區名稱='住宅大樓', 格局='4房2廳2衛', 標題='捷運上郡四房車位', 公設坪=12.2, 來源網站='永慶房屋')
        hbhousing = listing('hbhousing', 社區名稱='近公園', 格局='4房2廳2衛', 標題='捷運上郡送家電家具', 主建坪=0, 陽台坪=0, 雨遮坪=0, 公設坪=0, 車位坪=0, 車位型=None, 來源網站='住商不動產')

        rows, audit = deduplicate_active([sinyi, yungching, hbhousing])

        self.assertEqual(audit['raw_active_count'], 3)
        self.assertEqual(audit['unique_active_count'], 1)
        self.assertEqual(rows[0]['同戶判定'], '高度可能同戶')
        self.assertEqual(rows[0]['來源網站'], '信義房屋/永慶房屋/住商不動產')
        self.assertEqual(len(rows[0]['來源物件']), 3)

    def test_different_floor_is_never_merged(self):
        rows, audit = deduplicate_active([listing('thirteen'), listing('twelve', 樓層='12/15')])

        self.assertEqual(len(rows), 2)
        self.assertEqual(audit['merged_group_count'], 0)

    def test_sparse_listing_needs_address_price_and_age_to_merge(self):
        rich = listing('rich')
        sparse = listing('sparse', 社區名稱='近公園', 標題='捷運上郡四房車位', 主建坪=0, 陽台坪=0, 雨遮坪=0, 公設坪=0, 車位坪=0, **{'總價(萬)': 2600})

        rows, _ = deduplicate_active([rich, sparse])

        self.assertEqual(len(rows), 2)

    def test_multiple_source_names_do_not_reuse_one_brokers_url(self):
        item = listing('combined', 來源網站='信義房屋/永慶房屋', 來源連結='https://www.sinyi.com.tw/buy/house/3992KB')

        sources = listing_sources(item)

        self.assertEqual(sources[0]['網站'], '信義房屋')
        self.assertEqual(sources[0]['連結'], 'https://www.sinyi.com.tw/buy/house/3992KB')
        self.assertEqual(sources[1]['網站'], '永慶房屋')
        self.assertIsNone(sources[1]['連結'])


if __name__ == '__main__':
    unittest.main()
