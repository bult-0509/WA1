"""2017上海POI的分块清洗、坐标统一与站点圈汇总。"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree


EARTH_RADIUS_M = 6_371_008.8
POI_COLUMNS = [
    '来源分类', 'NAME', 'ADDRESS', 'TELEPHONE', 'PROVINCE', 'CITY', 'COUNTY',
    'CODE', 'LON', 'LAT', 'TYPECODE', 'BASETYPE', 'SUBTYPE', 'CATEGORY',
]

# 地名、道路和室内设施点更接近地图标注，不代表可独立到访的城市功能。
EXCLUDED_BASE_TYPES = {'地名地址信息', '通行设施', '室内设施', '道路附属设施'}
GROUP_MAP = {
    '餐饮服务': '餐饮',
    '购物服务': '购物',
    '生活服务': '生活服务',
    '公司企业': '就业金融',
    '金融保险服务': '就业金融',
    '商务住宅': '居住商务',
    '科教文化服务': '科教医疗',
    '医疗保健服务': '科教医疗',
    '体育休闲服务': '休闲文旅',
    '住宿服务': '休闲文旅',
    '风景名胜': '休闲文旅',
    '事件活动': '休闲文旅',
    '交通设施服务': '交通服务',
    '汽车服务': '交通服务',
    '汽车维修': '交通服务',
    '汽车销售': '交通服务',
    '摩托车服务': '交通服务',
    '政府机构及社会团体': '公共服务',
    '公共设施': '公共服务',
}
GROUPS = list(dict.fromkeys(GROUP_MAP.values()))


def _transform_lat(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    result = -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * np.sqrt(np.abs(x))
    result += (20 * np.sin(6 * x * np.pi) + 20 * np.sin(2 * x * np.pi)) * 2 / 3
    result += (20 * np.sin(y * np.pi) + 40 * np.sin(y / 3 * np.pi)) * 2 / 3
    result += (160 * np.sin(y / 12 * np.pi) + 320 * np.sin(y * np.pi / 30)) * 2 / 3
    return result


def _transform_lon(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    result = 300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * np.sqrt(np.abs(x))
    result += (20 * np.sin(6 * x * np.pi) + 20 * np.sin(2 * x * np.pi)) * 2 / 3
    result += (20 * np.sin(x * np.pi) + 40 * np.sin(x / 3 * np.pi)) * 2 / 3
    result += (150 * np.sin(x / 12 * np.pi) + 300 * np.sin(x / 30 * np.pi)) * 2 / 3
    return result


def wgs84_to_gcj02(lon, lat):
    """把发布方WGS84站点坐标转换到POI采用的GCJ-02坐标。"""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    x, y = lon - 105, lat - 35
    dlat, dlon = _transform_lat(x, y), _transform_lon(x, y)
    radlat = lat / 180 * np.pi
    magic = 1 - .00669342162296594323 * np.sin(radlat) ** 2
    sqrt_magic = np.sqrt(magic)
    dlat = dlat * 180 / ((6_378_245 * (1 - .00669342162296594323)) / (magic * sqrt_magic) * np.pi)
    dlon = dlon * 180 / (6_378_245 / sqrt_magic * np.cos(radlat) * np.pi)
    converted_lon, converted_lat = lon + dlon, lat + dlat
    outside = (lon < 72.004) | (lon > 137.8347) | (lat < .8293) | (lat > 55.8271)
    return np.where(outside, lon, converted_lon), np.where(outside, lat, converted_lat)


def normalized_diversity(counts: np.ndarray) -> np.ndarray:
    """归一化Shannon多样性，0表示单一，1表示九类完全均衡。"""
    counts = np.asarray(counts, dtype=float)
    totals = counts.sum(axis=1, keepdims=True)
    shares = np.divide(counts, totals, out=np.zeros_like(counts), where=totals > 0)
    log_shares = np.zeros_like(shares)
    np.log(shares, out=log_shares, where=shares > 0)
    entropy = -(shares * log_shares).sum(axis=1)
    return entropy / math.log(counts.shape[1])


def _query_counts(tree: BallTree, station_radians: np.ndarray, radius_m: int) -> list[np.ndarray]:
    return tree.query_radius(station_radians, r=radius_m / EARTH_RADIUS_M, return_distance=False)


def prepare_poi(source: Path, stations_path: Path, output_dir: Path, chunksize: int = 150_000) -> dict:
    source, stations_path, output_dir = Path(source), Path(stations_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stations = pd.read_parquet(stations_path).sort_values('station_id').reset_index(drop=True)
    station_lon_gcj, station_lat_gcj = wgs84_to_gcj02(stations.lon, stations.lat)
    station_radians = np.radians(np.column_stack([station_lat_gcj, station_lon_gcj]))
    group_counts = {500: np.zeros((len(stations), len(GROUPS)), dtype=np.int64),
                    1000: np.zeros((len(stations), len(GROUPS)), dtype=np.int64)}
    all_counts = {500: np.zeros(len(stations), dtype=np.int64),
                  1000: np.zeros(len(stations), dtype=np.int64)}
    city_counts: Counter[tuple[str, str, str]] = Counter()
    base_counts: Counter[str] = Counter()
    missing = Counter()
    seen_hashes: set[int] = set()
    raw_rows = duplicates = invalid_coordinates = outside_bounds = functional_rows = 0
    subway_points: list[np.ndarray] = []

    for chunk in pd.read_csv(source, usecols=POI_COLUMNS, dtype='string', chunksize=chunksize,
                             encoding='utf-8-sig', low_memory=False):
        raw_rows += len(chunk)
        missing.update(chunk.isna().sum().to_dict())
        key = chunk[['NAME', 'ADDRESS', 'LON', 'LAT', 'CATEGORY']].fillna('').apply(lambda c: c.str.strip())
        hashes = pd.util.hash_pandas_object(key, index=False).astype('uint64')
        keep = np.ones(len(chunk), dtype=bool)
        for index, value in enumerate(hashes):
            item = int(value)
            if item in seen_hashes:
                keep[index] = False
                duplicates += 1
            else:
                seen_hashes.add(item)
        chunk = chunk.loc[keep].copy()
        lon = pd.to_numeric(chunk.LON, errors='coerce')
        lat = pd.to_numeric(chunk.LAT, errors='coerce')
        valid = lon.notna() & lat.notna() & lon.between(-180, 180) & lat.between(-90, 90)
        invalid_coordinates += int((~valid).sum())
        shanghai = valid & lon.between(120.8, 122.2) & lat.between(30.6, 31.9)
        outside_bounds += int((valid & ~shanghai).sum())
        chunk = chunk.loc[shanghai].copy()
        chunk['LON'] = lon.loc[shanghai].astype(float)
        chunk['LAT'] = lat.loc[shanghai].astype(float)

        all_tree = BallTree(np.radians(chunk[['LAT', 'LON']].to_numpy()), metric='haversine')
        for radius in (500, 1000):
            neighbours = _query_counts(all_tree, station_radians, radius)
            all_counts[radius] += np.fromiter((len(x) for x in neighbours), dtype=np.int64)

        subway = chunk.loc[chunk.CATEGORY.eq('地铁站'), ['LAT', 'LON']]
        if len(subway):
            subway_points.append(subway.to_numpy(float))

        functional = chunk[~chunk.BASETYPE.isin(EXCLUDED_BASE_TYPES)].copy()
        if functional.empty:
            continue
        functional['analysis_group'] = functional.BASETYPE.map(GROUP_MAP).fillna('其他')
        functional_rows += len(functional)
        for row in functional[['COUNTY', 'BASETYPE', 'analysis_group']].itertuples(index=False, name=None):
            city_counts[tuple(str(x).strip() for x in row)] += 1
        base_counts.update(functional.BASETYPE)

        functional_tree = BallTree(np.radians(functional[['LAT', 'LON']].to_numpy()), metric='haversine')
        codes = pd.Categorical(functional.analysis_group, categories=GROUPS).codes
        for radius in (500, 1000):
            neighbours = _query_counts(functional_tree, station_radians, radius)
            for station_index, indices in enumerate(neighbours):
                if len(indices):
                    group_counts[radius][station_index] += np.bincount(codes[indices], minlength=len(GROUPS))

    result = stations[['station_id', 'name', 'lon', 'lat']].copy()
    result['poi_count_500m'] = group_counts[500].sum(axis=1)
    result['poi_count_1000m'] = group_counts[1000].sum(axis=1)
    result['all_poi_count_500m'] = all_counts[500]
    result['all_poi_count_1000m'] = all_counts[1000]
    result['poi_density_1000m'] = result.poi_count_1000m / math.pi
    result['inner_share'] = np.divide(result.poi_count_500m, result.poi_count_1000m,
                                      out=np.zeros(len(result), dtype=float), where=result.poi_count_1000m > 0)
    result['diversity'] = normalized_diversity(group_counts[1000])
    for index, group in enumerate(GROUPS):
        result[f'group_{group}'] = group_counts[1000][:, index]
    dominant = np.argmax(group_counts[1000], axis=1)
    result['dominant_group'] = [GROUPS[x] for x in dominant]
    result['dominant_share'] = np.divide(group_counts[1000].max(axis=1), result.poi_count_1000m,
                                         out=np.zeros(len(result), dtype=float), where=result.poi_count_1000m > 0)
    result.to_parquet(output_dir / 'poi_stations.parquet', index=False)

    city = pd.DataFrame([{'district': key[0], 'base_type': key[1], 'analysis_group': key[2], 'count': value}
                         for key, value in city_counts.items()])
    city.sort_values(['district', 'count'], ascending=[True, False]).to_parquet(output_dir / 'poi_city.parquet', index=False)

    subway = np.vstack(subway_points)
    subway_tree = BallTree(np.radians(subway), metric='haversine')
    before = subway_tree.query(np.radians(stations[['lat', 'lon']].to_numpy()), k=1)[0][:, 0] * EARTH_RADIUS_M
    after = subway_tree.query(station_radians, k=1)[0][:, 0] * EARTH_RADIUS_M
    quality = {
        'source_file': source.name,
        'source_bytes': source.stat().st_size,
        'raw_rows': raw_rows,
        'columns': len(POI_COLUMNS),
        'candidate_duplicates_removed': duplicates,
        'unique_valid_rows': raw_rows - duplicates - invalid_coordinates - outside_bounds,
        'functional_rows': functional_rows,
        'excluded_base_types': sorted(EXCLUDED_BASE_TYPES),
        'base_type_count': len(base_counts),
        'analysis_groups': GROUPS,
        'missing_cells': dict(missing),
        'invalid_coordinates': invalid_coordinates,
        'outside_shanghai_bounds': outside_bounds,
        'station_catchment_radius_m': [500, 1000],
        'coordinate_note': 'POI按高德分类与坐标特征视为GCJ-02；MetroFlow站点WGS84坐标先转换为GCJ-02。',
        'subway_reference_points': len(subway),
        'median_nearest_subway_m_before_conversion': round(float(np.median(before)), 1),
        'median_nearest_subway_m_after_conversion': round(float(np.median(after)), 1),
        'stations_within_300m_after_conversion': int((after <= 300).sum()),
        'station_count': len(stations),
        'stations_with_functional_poi_1000m': int(result.poi_count_1000m.gt(0).sum()),
        'uncovered_station_names': result.loc[result.poi_count_1000m.eq(0), 'name'].tolist(),
        'catchment_overlap_note': '各站1公里圆形范围可能重叠，跨站合计会重复计算POI。',
    }
    (output_dir / 'poi_quality.json').write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')
    return quality
