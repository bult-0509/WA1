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
