"""按文件顺序取两张大表的前10%行；分块处理OD，小表完整关联。"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'MetroFlow'
OUT = RAW / 'sample'
BAD_DATES = ['2017-05-04', '2017-05-08', '2017-05-09',
             '2017-06-16', '2017-06-27', '2017-06-28']
FLOW = ['inFlow', 'outFlow', 'CinFlow', 'HBOinFlow', 'NHBinFlow',
        'CoutFlow', 'HBOoutFlow', 'NHBoutFlow']
OD_FLOW = ['Flow', 'CFlow', 'HBOFlow', 'NHBFlow']


def row_counts():
    """只扫描字节计行，之后仅解析前10%；文件未变时复用行数。"""
    path = OUT / 'row_counts.json'
    counts = json.loads(path.read_text()) if path.exists() else {}
    for name in ['metroData_InOutFlow.csv', 'metroData_ODFlow.csv']:
        file = RAW / name
        stat = file.stat()
        old = counts.get(name, {})
        if old.get('bytes') == stat.st_size and old.get('mtime_ns') == stat.st_mtime_ns:
            continue
        total, last = 0, b''
        with file.open('rb') as source:
            while block := source.read(16 * 1024 * 1024):
                total += block.count(b'\n')
                last = block[-1:]
        total += int(last != b'\n') - 1
        counts[name] = dict(total_rows=total, sample_rows=total // 10,
                            bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
    path.write_text(json.dumps(counts, indent=2), encoding='utf-8')
    return counts


def save(frame, name):
    frame.to_parquet(OUT / f'{name}.parquet', index=False)


def validate_counts(frame, columns):
    if frame[columns].isna().any().any() or (frame[columns] < 0).any().any():
        raise ValueError('发现缺失或负客流，停止处理。')
    if (frame[columns] % 1 != 0).any().any():
        raise ValueError('客流必须是整数。')


def prepare():
    OUT.mkdir(exist_ok=True)
    counts = row_counts()
    stations = pd.read_csv(RAW / 'stationInfo.csv').rename(columns={'stationID': 'station_id'})
    stations = stations.loc[:, ~stations.columns.str.startswith('Unnamed')]
    calendar = pd.read_csv(RAW / 'MetaData/workday_calendar.csv').rename(columns={'isWorday': 'is_workday'})
    calendar['date'] = pd.to_datetime(calendar.date.astype(str), format='%Y%m%d')
    if stations.station_id.duplicated().any() or calendar.date.duplicated().any():
        raise ValueError('站点或日历主键重复。')
    save(stations, 'stations')
    save(calendar, 'calendar')

    daily = pd.read_csv(RAW / 'MetaData/shanghai_weatherDaily.csv')
    daily['date'] = pd.to_datetime(daily.date.astype(str), format='%Y%m%d')
    weather = pd.read_csv(RAW / 'MetaData/shanghai_weatherHourly.csv')
    weather['time'] = pd.to_datetime(weather.date)
    weather['date'] = weather.time.dt.normalize()
    weather['hour'] = weather.time.dt.hour
    if daily.date.duplicated().any() or weather.time.duplicated().any():
        raise ValueError('天气时间键重复。')
    save(daily, 'weather_daily')
    save(weather, 'weather_hourly')

    print('读取进出站表前10%…', flush=True)
    flow = pd.read_csv(RAW / 'metroData_InOutFlow.csv', skipinitialspace=True,
                       nrows=counts['metroData_InOutFlow.csv']['sample_rows'])
    flow['date'] = pd.to_datetime(flow.date.astype(str), format='%Y%m%d')
    flow = flow.rename(columns={'station': 'station_id'})
    flow['hour'] = flow.startTime // 10000
    validate_counts(flow, FLOW)
    if not flow.station_id.isin(stations.station_id).all() or flow.duplicated(['date', 'timeslot', 'station_id']).any():
        raise ValueError('进出站表含未知站点或重复记录。')
    if not (flow.inFlow == flow[['CinFlow', 'HBOinFlow', 'NHBinFlow']].sum(axis=1)).all() or not (flow.outFlow == flow[['CoutFlow', 'HBOoutFlow', 'NHBoutFlow']].sum(axis=1)).all():
        raise ValueError('进出站分项和与总量不一致。')
    station_days = flow.groupby(['date', 'station_id']).timeslot.nunique()
    complete = station_days.eq(102).groupby('date').sum().eq(len(stations))
    valid_dates = complete[complete].index.difference(pd.to_datetime(BAD_DATES))
    report = dict(sampling='两张大表分别按文件顺序取 floor(总行数/10) 行；小表完整关联',
                  counts=counts, flow_start=str(flow.date.min().date()), flow_end=str(flow.date.max().date()),
                  flow_partial_dates=[str(x.date()) for x in complete[~complete].index],
                  excluded_bad_dates=[x for x in BAD_DATES if pd.Timestamp(x) in flow.date.unique()],
                  valid_dates=[str(x.date()) for x in valid_dates])
    raw_daily = flow.groupby('date', as_index=False)[FLOW].sum()
    raw_daily['included'] = raw_daily.date.isin(valid_dates)
    save(raw_daily, 'sample_daily')
    flow = flow[flow.date.isin(valid_dates)]
    hourly = flow.groupby(['date', 'station_id', 'hour'], as_index=False)[FLOW].sum()
    hourly = hourly.merge(calendar, on='date', validate='many_to_one')
    save(hourly, 'hourly')
    del flow

    print('分块读取OD表前10%…', flush=True)
    parts, first, last, seen = [], None, None, 0
    for chunk in pd.read_csv(RAW / 'metroData_ODFlow.csv', skipinitialspace=True,
                             nrows=counts['metroData_ODFlow.csv']['sample_rows'], chunksize=250_000):
        chunk['date'] = pd.to_datetime(chunk.date.astype(str), format='%Y%m%d')
        if not chunk.date.is_monotonic_increasing or (last is not None and chunk.date.min() < last):
            raise ValueError('OD未按日期排序，不能使用当前截断规则。')
        first = chunk.date.min() if first is None else first
        last = chunk.date.max()
        validate_counts(chunk, OD_FLOW)
        if not chunk.originStation.isin(stations.station_id).all() or not chunk.destinationStation.isin(stations.station_id).all():
            raise ValueError('OD含未知站点。')
        if not chunk.Flow.eq(chunk[['CFlow', 'HBOFlow', 'NHBFlow']].sum(axis=1)).all():
            raise ValueError('OD分项与总量不一致。')
        parts.append(chunk.groupby(['date', 'originStation', 'destinationStation'], as_index=False)[OD_FLOW].sum())
        seen += len(chunk)
        if len(parts) >= 8:
            parts = [pd.concat(parts).groupby(['date', 'originStation', 'destinationStation'], as_index=False)[OD_FLOW].sum()]
        if seen % 2_000_000 == 0:
            print(f'OD已处理 {seen:,} 行', flush=True)
    od = pd.concat(parts).groupby(['date', 'originStation', 'destinationStation'], as_index=False)[OD_FLOW].sum()
    # 稀疏OD没有固定每日行数，保守排除截断所在日，不把未读到的流量当零。
    od = od[(od.date < last) & ~od.date.isin(pd.to_datetime(BAD_DATES))]
    od = od.merge(calendar, on='date', validate='many_to_one')
    save(od, 'od_daily')
    report.update(od_start=str(first.date()), od_end=str(last.date()), od_boundary_excluded=str(last.date()),
                  od_valid_dates=[str(x.date()) for x in sorted(od.date.unique())], od_rows_read=seen)
    network = hourly.groupby('date', as_index=False).inFlow.sum()
    od_total = od.groupby('date', as_index=False).Flow.sum()
    comparison = network.merge(od_total, on='date')
    comparison['difference'] = comparison.Flow - comparison.inFlow
    save(comparison, 'comparison')
    report['common_days'] = len(comparison)
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report
