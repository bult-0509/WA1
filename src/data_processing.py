"""数据读取、质量检查和汇总。保留异常日原值，正常分析通过is_valid排除。"""
from pathlib import Path
import ast
import json
import numpy as np
import pandas as pd

FLOW = ['inFlow', 'outFlow', 'CinFlow', 'HBOinFlow', 'NHBinFlow',
        'CoutFlow', 'HBOoutFlow', 'NHBoutFlow']
BAD_DATES = pd.to_datetime(['2017-05-04', '2017-05-08', '2017-05-09',
                            '2017-06-16', '2017-06-27', '2017-06-28'])
REQUIRED = ['date', 'timeslot', 'startTime', 'endTime', 'station'] + FLOW


def check_unique(frame, key, label):
    if frame[key].isna().any() or frame[key].duplicated().any():
        raise ValueError(f'{label}的{key}缺失或重复，请先修正辅助数据。')


def read_auxiliary(raw_dir):
    raw_dir = Path(raw_dir)
    stations = pd.read_csv(raw_dir / 'stationInfo.csv')
    stations = stations.loc[:, ~stations.columns.str.startswith('Unnamed')]
    stations = stations.rename(columns={'stationID': 'station_id'})
    stations['station_id'] = stations.station_id.astype('int64')
    check_unique(stations, 'station_id', '站点表')
    known = set(stations.station_id)
    def neighbours(value):
        values = ast.literal_eval(value) if isinstance(value, str) else value
        if not isinstance(values, list) or any(not isinstance(x, int) or x not in known for x in values):
            raise ValueError('邻接站点列表包含未知站点或格式错误。')
        return json.dumps(values)
    stations['neighbour'] = stations.neighbour.map(neighbours)
    if not stations.lon.between(-180, 180).all() or not stations.lat.between(-90, 90).all():
        raise ValueError('站点经纬度超出有效范围。')
    calendar = pd.read_csv(raw_dir / 'MetaData/workday_calendar.csv', dtype={'date': str})
    calendar['date'] = pd.to_datetime(calendar.date, format='%Y%m%d')
    calendar = calendar.rename(columns={'isWorday': 'is_workday'})
    check_unique(calendar, 'date', '日历')
    if not calendar.is_workday.isin([0, 1]).all():
        raise ValueError('日历工作日标记应为0或1。')
    weather = pd.read_csv(raw_dir / 'MetaData/shanghai_weatherHourly.csv', dtype={'date': str})
    weather['time'] = pd.to_datetime(weather.date, format='%Y%m%d %H:%M:%S')
    check_unique(weather, 'time', '小时天气')
    weather['date'] = weather.time.dt.normalize()
    return stations, calendar, weather


def aggregate_weather(weather):
    cols = ['temperature_2m', 'apparent_temperature', 'rain', 'wind_speed_10m']
    weather = weather.copy()
    weather[cols] = weather[cols].apply(pd.to_numeric, errors='coerce')
    weather['valid'] = weather[cols].notna().all(axis=1) & (weather.rain >= 0)
    daily = weather.groupby('date').agg(
        temperature_2m=('temperature_2m', 'mean'),
        apparent_temperature=('apparent_temperature', 'mean'),
        rain=('rain', 'sum'), wind_speed_10m=('wind_speed_10m', 'mean'),
        hours=('time', 'nunique'), valid_hours=('valid', 'sum')).reset_index()
    daily['is_valid'] = daily.hours.eq(24) & daily.valid_hours.eq(24)
    daily.loc[~daily.is_valid, cols] = np.nan
    return daily


def clean_flow(frame, station_ids):
    """异常记录不补0；重复冲突保留供汇总标记，正常分析必须排除受影响日期。"""
    f = frame.copy()
    f.columns = f.columns.str.strip()
    missing = set(REQUIRED) - set(f.columns)
    if missing:
        raise ValueError(f'客流文件缺少列：{sorted(missing)}')
    original_rows = len(f)
    missing_cells = int(f[REQUIRED].isna().sum().sum())
    duplicate_rows = int(f.duplicated().sum())
    f = f.drop_duplicates().copy()
    f['date'] = pd.to_datetime(f.date.astype(str), format='%Y%m%d', errors='coerce')
    f['station_id'] = pd.to_numeric(f.station, errors='coerce')
    f[FLOW] = f[FLOW].apply(pd.to_numeric, errors='coerce')
    start = f.startTime.astype(str).str.zfill(6)
    end = f.endTime.astype(str).str.zfill(6)
    stamp = pd.to_datetime(f.date.dt.strftime('%Y%m%d') + start, format='%Y%m%d%H%M%S', errors='coerce')
    finish = pd.to_datetime(f.date.dt.strftime('%Y%m%d') + end, format='%Y%m%d%H%M%S', errors='coerce')
    f['hour'] = stamp.dt.hour
    f['start'] = stamp
    slot = pd.to_numeric(f.timeslot, errors='coerce')
    expected = (f.date - pd.Timestamp('2017-05-01')).dt.days * 102 + (stamp.dt.hour - 6) * 6 + stamp.dt.minute // 10
    interval_ok = (finish - stamp).eq(pd.Timedelta(minutes=10)) & stamp.dt.hour.between(6, 22) & stamp.dt.minute.mod(10).eq(0) & stamp.dt.second.eq(0) & slot.eq(expected)
    count_ok = f[FLOW].notna().all(axis=1) & f[FLOW].ge(0).all(axis=1) & f[FLOW].mod(1).eq(0).all(axis=1)
    parts_ok = f.inFlow.eq(f[['CinFlow', 'HBOinFlow', 'NHBinFlow']].sum(axis=1, min_count=3)) & f.outFlow.eq(f[['CoutFlow', 'HBOoutFlow', 'NHBoutFlow']].sum(axis=1, min_count=3))
    key_conflict = f.duplicated(['date', 'start', 'station_id'], keep=False)
    known = f.station_id.isin(station_ids)
    valid_dates = f.date.between('2017-05-01', '2017-08-31')
    f['row_valid'] = interval_ok & count_ok & parts_ok & ~key_conflict & known & valid_dates
    f['known_bad_day'] = f.date.isin(BAD_DATES)
    report = dict(raw_rows=original_rows, columns=len(frame.columns), missing_cells=missing_cells,
                  exact_duplicates_removed=duplicate_rows, conflicting_rows=int(key_conflict.sum()),
                  invalid_time_rows=int((~interval_ok).sum()), invalid_count_rows=int((~count_ok).sum()),
                  component_mismatch_rows=int((~parts_ok).sum()), unknown_station_rows=int((~known).sum()),
                  invalid_rows=int((~f.row_valid).sum()), zero_in_out_rows=int((f.inFlow.eq(0) & f.outFlow.eq(0)).sum()))
    return f, report


def prepare(raw_dir, output_dir):
    raw_dir, out = Path(raw_dir), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stations, calendar, weather = read_auxiliary(raw_dir)
    frame = pd.read_csv(raw_dir / 'metroData_InOutFlow.csv', skipinitialspace=True,
                        dtype={'date': str, 'startTime': str, 'endTime': str})
    f, report = clean_flow(frame, set(stations.station_id))
    del frame
    # 无法定位日期或站点的记录不进入分组；它们仍计入质量报告。
    usable = f.dropna(subset=['date', 'station_id', 'hour']).copy()
    grouped = usable.groupby(['date', 'station_id', 'hour'], observed=True)
    hourly = grouped[FLOW].sum(min_count=1)
    hourly['slot_count'] = grouped.start.nunique()
    hourly['row_count'] = grouped.size()
    hourly['all_valid'] = grouped.row_valid.all()
    hourly = hourly.reset_index()
    hourly['is_valid'] = hourly.slot_count.eq(6) & hourly.row_count.eq(6) & hourly.all_valid & ~hourly.date.isin(BAD_DATES)
    hourly['quality_reason'] = np.select([hourly.date.isin(BAD_DATES), ~hourly.is_valid], ['原始计数缺损日', '记录不完整或格式异常'], default='')
    hourly = hourly.merge(calendar, on='date', how='left', validate='many_to_one')
    if hourly.is_workday.isna().any():
        raise ValueError('部分客流日期无法关联工作日历。')
    daily_group = hourly.groupby(['date', 'station_id'], observed=True)
    daily = daily_group[FLOW].sum(min_count=1)
    daily['valid_slot_count'] = daily_group.slot_count.sum()
    daily['hour_count'] = daily_group.hour.nunique()
    daily['is_valid'] = daily_group.is_valid.all() & daily_group.hour.nunique().eq(17)
    daily = daily.reset_index().merge(calendar, on='date', validate='many_to_one')
    daily['quality_reason'] = np.select([daily.date.isin(BAD_DATES), ~daily.is_valid], ['原始计数缺损日', '记录不完整或格式异常'], default='')
    ng = daily.groupby('date')
    network = ng[FLOW].sum(min_count=1)
    network['valid_station_count'] = ng.is_valid.sum()
    network['station_count'] = ng.station_id.nunique()
    network['is_valid'] = network.valid_station_count.eq(len(stations)) & network.station_count.eq(len(stations))
    network = network.reset_index().merge(calendar, on='date', validate='one_to_one')
    # 统一采用全网完整日期，让站点排名与时序的日均分母可以直接比较。
    full_days = network.loc[network.is_valid, 'date']
    hourly['is_valid'] &= hourly.date.isin(full_days)
    daily['is_valid'] &= daily.date.isin(full_days)
    for name, table in [('station_hourly', hourly), ('station_daily', daily), ('network_daily', network), ('stations', stations), ('calendar', calendar), ('weather_daily', aggregate_weather(weather))]:
        table.to_parquet(out / f'{name}.parquet', index=False, compression='zstd')
    abnormal = network.loc[network.date.isin(BAD_DATES), ['date', 'inFlow', 'outFlow']].copy()
    abnormal['date'] = abnormal.date.dt.strftime('%Y-%m-%d')
    report.update(stations=len(stations), days=int(network.date.nunique()), valid_days=len(full_days),
                  hourly_rows=len(hourly), daily_rows=len(daily), excluded_days=abnormal.to_dict('records'),
                  source='https://doi.org/10.6084/m9.figshare.28844942', license='CC BY 4.0',
                  date_start='2017-05-01', date_end='2017-08-31',
                  input_directory=raw_dir.name,
                  input_files=['metroData_InOutFlow.csv', 'stationInfo.csv',
                               'MetaData/workday_calendar.csv', 'MetaData/shanghai_weatherHourly.csv'])
    (out / 'quality.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
