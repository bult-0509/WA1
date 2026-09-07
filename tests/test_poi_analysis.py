"""POI坐标、指标和客流关联的关键检查。"""
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src import analysis
from src.poi_processing import GROUPS, normalized_diversity, wgs84_to_gcj02


ROOT = Path(__file__).resolve().parents[1]


class PoiMetrics(unittest.TestCase):
    def test_coordinate_conversion_matches_shanghai_shift(self):
        lon, lat = wgs84_to_gcj02([121.441840], [31.225058])
        self.assertAlmostEqual(float(lon[0]), 121.4464, places=3)
        self.assertAlmostEqual(float(lat[0]), 31.2231, places=3)

    def test_diversity_has_explainable_bounds(self):
        single = np.zeros((1, len(GROUPS))); single[0, 0] = 10
        equal = np.ones((1, len(GROUPS)))
        self.assertAlmostEqual(float(normalized_diversity(single)[0]), 0)
        self.assertAlmostEqual(float(normalized_diversity(equal)[0]), 1)

    def test_poi_flow_analysis_returns_comparisons(self):
        count = 12
        poi = pd.DataFrame({
            'station_id': range(count), 'name': [f'S{x}' for x in range(count)],
            'poi_count_1000m': np.arange(10, 10 + count),
            'diversity': np.linspace(.3, .9, count),
        })
        for index, group in enumerate(GROUPS):
            poi[f'group_{group}'] = np.arange(1 + index, 1 + index + count)
        daily = pd.DataFrame({
            'date': np.repeat(pd.Timestamp('2017-05-01'), count),
            'station_id': range(count), 'inFlow': np.arange(100, 100 + count) * 10,
            'outFlow': np.arange(100, 100 + count) * 8,
        })
        linked, correlations, comparison, composition = analysis.poi_flow_analysis(poi, daily)
        self.assertEqual(len(linked), count)
        self.assertAlmostEqual(correlations.iloc[0]['Spearman相关系数'], 1)
        self.assertEqual(len(comparison), 4)
        self.assertEqual(set(composition['客流组']), {'客流前25%', '客流后25%'})

    def test_bundled_poi_results_are_complete(self):
        station_path = ROOT / 'data/processed/poi_stations.parquet'
        quality_path = ROOT / 'data/processed/poi_quality.json'
        self.assertTrue(station_path.is_file())
        frame = pd.read_parquet(station_path)
        quality = json.loads(quality_path.read_text(encoding='utf-8'))
        self.assertEqual(len(frame), 302)
        self.assertEqual(quality['station_count'], 302)
        self.assertGreater(quality['raw_rows'], 1_000_000)
        self.assertGreaterEqual(int(frame.poi_count_1000m.gt(0).sum()), 300)


if __name__ == '__main__':
    unittest.main()
