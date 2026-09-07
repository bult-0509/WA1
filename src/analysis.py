"""统一统计口径：全网用进站人次，日均按有效日期计算。"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .data_processing import FLOW

DAY_NAMES = {0: '非工作日', 1: '工作日'}
FLOW_NAMES = {'inFlow': '进站', 'outFlow': '出站', 'totalFlow': '进出总量'}
TYPE_NAMES = {'C': '通勤', 'HBO': '居家其他', 'NHB': '非居家'}


def filter_data(frame, dates, day_type='全部', stations=None, valid_only=True):
    start, end = map(pd.Timestamp, dates)
    if start > end:
        raise ValueError('开始日期不能晚于结束日期。')
    mask = frame.date.between(start, end)
    if valid_only and 'is_valid' in frame:
        mask &= frame.is_valid
    if day_type != '全部':
        mask &= frame.is_workday.eq(1 if day_type == '工作日' else 0)
    if stations:
        mask &= frame.station_id.isin(stations)
    return frame.loc[mask].copy()


def direction_values(frame, direction):
    return frame.inFlow + frame.outFlow if direction == 'totalFlow' else frame[direction]


def daily_series(hourly, direction='inFlow'):
    f = hourly.assign(value=direction_values(hourly, direction))
    return f.groupby(['date', 'is_workday'], as_index=False).value.sum()


def hourly_profile(hourly, direction='inFlow'):
    f = hourly.assign(value=direction_values(hourly, direction))
    daily = f.groupby(['date', 'is_workday', 'hour'], as_index=False).value.sum()
    result = daily.groupby(['is_workday', 'hour'], as_index=False).agg(value=('value', 'mean'), days=('date', 'nunique'))
    result['日类型'] = result.is_workday.map(DAY_NAMES)
    return result


def station_ranking(daily, direction='inFlow'):
    if daily.empty:
        return pd.DataFrame(columns=['station_id', 'value', 'days'])
    # 各站采用共同有效日期，避免按不同分母排序。
    station_count = daily.station_id.nunique()
    good = daily.groupby('date').station_id.nunique().eq(station_count)
    f = daily[daily.date.isin(good[good].index)].copy()
    f['value'] = direction_values(f, direction)
    return f.groupby('station_id', as_index=False).agg(value=('value', 'mean'), days=('date', 'nunique')).sort_values('value', ascending=False)


def balance(inflow, outflow):
    denom = np.asarray(inflow, dtype=float) + np.asarray(outflow, dtype=float)
    numerator = np.asarray(inflow, dtype=float) - np.asarray(outflow, dtype=float)
    return np.divide(numerator, denom, out=np.full_like(denom, np.nan), where=denom != 0)


def peak_direction(hourly):
    rows = []
    for name, start, end in [('早高峰 07–09时', 7, 9), ('晚高峰 17–19时', 17, 19)]:
        f = hourly[hourly.hour.between(start, end, inclusive='left')]
        daily = f.groupby(['date', 'station_id'])[['inFlow', 'outFlow']].sum()
        group = daily.groupby('station_id').mean().reset_index()
        group['时段'] = name
        group['方向指数'] = balance(group.inFlow, group.outFlow)
        rows.append(group)
    return pd.concat(rows, ignore_index=True)


def trip_composition(hourly, direction='inFlow'):
    suffix = 'inFlow' if direction == 'inFlow' else 'outFlow'
    total = hourly[suffix].sum()
    return pd.DataFrame([{'出行类型': name, '人次': int(hourly[f'{prefix}{suffix}'].sum()),
                          '占比': float(hourly[f'{prefix}{suffix}'].sum() / total) if total else np.nan}
                         for prefix, name in TYPE_NAMES.items()])


def weather_analysis(network, weather):
    n = network[network.is_valid].drop(columns='is_valid')
    w = weather[weather.is_valid].drop(columns='is_valid')
    joined = n.merge(w, on='date', how='inner', validate='one_to_one')
    joined['日类型'] = joined.is_workday.map(DAY_NAMES)
    joined['降雨情况'] = np.where(joined.rain > 0, '有雨', '无雨')
    rows = []
    for day, g in joined.groupby('is_workday'):
        for field, label in [('temperature_2m', '日均温度'), ('rain', '日雨量')]:
            pairs = g[[field, 'inFlow']].dropna()
            rho = float(spearmanr(pairs[field], pairs.inFlow).statistic) if len(pairs) >= 3 and pairs.nunique().min() > 1 else np.nan
            rows.append({'日类型': DAY_NAMES[day], '因素': label, '相关系数': rho, '有效天数': len(pairs)})
    return joined, pd.DataFrame(rows, columns=['日类型', '因素', '相关系数', '有效天数'])


def _spearman(x, y):
    pairs = pd.DataFrame({'x': x, 'y': y}).dropna()
    if len(pairs) < 3 or pairs.nunique().min() < 2:
        return np.nan
    return float(spearmanr(pairs.x, pairs.y).statistic)


def bootstrap_spearman_interval(x, y, repetitions=600, seed=2026):
    """用站点重复抽样估计Spearman相关系数的95%区间。"""
    pairs = pd.DataFrame({'x': x, 'y': y}).dropna().to_numpy(float)
    if len(pairs) < 10 or np.unique(pairs[:, 0]).size < 2 or np.unique(pairs[:, 1]).size < 2:
        return np.nan, np.nan
    random = np.random.default_rng(seed)
    values = []
    for _ in range(repetitions):
        sample = pairs[random.integers(0, len(pairs), len(pairs))]
        if np.unique(sample[:, 0]).size > 1 and np.unique(sample[:, 1]).size > 1:
            values.append(spearmanr(sample[:, 0], sample[:, 1]).statistic)
    return tuple(float(x) for x in np.quantile(values, [.025, .975])) if values else (np.nan, np.nan)


def poi_flow_analysis(poi_stations, station_daily, direction='inFlow'):
    """关联固定POI站点圈与当前筛选范围内的站点日均客流。"""
    ranking = station_ranking(station_daily, direction).rename(columns={'value': 'flow'})
    frame = poi_stations.merge(ranking, on='station_id', how='inner', validate='one_to_one')
    frame['flow_percentile'] = frame.flow.rank(pct=True, method='average')
    frame['poi_percentile'] = frame.poi_count_1000m.rank(pct=True, method='average')
    frame['rank_gap'] = frame.flow_percentile - frame.poi_percentile
    frame['density_group'] = pd.qcut(
        frame.poi_count_1000m.rank(method='first'), 4,
        labels=['低密度', '中低密度', '中高密度', '高密度'])

    correlation_rows = []
    for field, label in [('poi_count_1000m', '1公里功能POI数'), ('diversity', '功能多样性')]:
        rho = _spearman(frame[field], frame.flow)
        low, high = bootstrap_spearman_interval(frame[field], frame.flow)
        correlation_rows.append({'指标': label, 'Spearman相关系数': rho,
                                 '95%区间下限': low, '95%区间上限': high, '站点数': len(frame)})
    correlations = pd.DataFrame(correlation_rows)

    density_order = ['低密度', '中低密度', '中高密度', '高密度']
    density_comparison = (frame.groupby('density_group', observed=True)
        .agg(站点数=('station_id', 'size'), 客流中位数=('flow', 'median'), 客流均值=('flow', 'mean'),
             POI中位数=('poi_count_1000m', 'median'), 多样性中位数=('diversity', 'median'))
        .reindex(density_order).reset_index())

    group_columns = [column for column in frame if column.startswith('group_')]
    traffic_rank = frame.flow.rank(pct=True, method='average')
    composition_rows = []
    for label, mask in [('客流后25%', traffic_rank <= .25), ('客流前25%', traffic_rank > .75)]:
        totals = frame.loc[mask, group_columns].sum()
        denominator = totals.sum()
        for column, count in totals.items():
            composition_rows.append({'客流组': label, '功能组': column.removeprefix('group_'),
                                     'POI计数': int(count), '占比': float(count / denominator) if denominator else np.nan})
    composition = pd.DataFrame(composition_rows)
    if len(composition):
        shares = composition.pivot(index='功能组', columns='客流组', values='占比').fillna(0)
        difference = (shares.get('客流前25%', 0) - shares.get('客流后25%', 0)).rename('占比差').reset_index()
        composition = composition.merge(difference, on='功能组', how='left')
    return frame, correlations, density_comparison, composition
