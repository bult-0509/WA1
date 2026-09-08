"""用相对小时曲线分组，评价只描述本批站点，不代表未来预测能力。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from threadpoolctl import threadpool_limits
from .data_processing import FLOW


def make_features(hourly):
    valid = hourly.loc[hourly.is_valid]
    means = valid.groupby(['station_id', 'is_workday', 'hour'])[['inFlow', 'outFlow']].mean()
    order = pd.MultiIndex.from_product([[0, 1], range(6, 23), ['inFlow', 'outFlow']])
    wide = means.stack().unstack([1, 2, 3]).reindex(columns=order)
    complete = wide.notna().all(axis=1)
    for day in [0, 1]:
        cols = [c for c in wide.columns if c[0] == day]
        total = wide[cols].sum(axis=1)
        complete &= total.gt(0)
        wide[cols] = wide[cols].div(total.replace(0, np.nan), axis=0)
    return wide.loc[complete].astype(float), wide.index[~complete].tolist()


def train(data_dir):
    data_dir = Path(data_dir)
    out = data_dir / 'clusters'
    out.mkdir(exist_ok=True)
    h = pd.read_parquet(data_dir / 'station_hourly.parquet')
    X, excluded = make_features(h)
    if len(X) < 3:
        raise ValueError('有效站点过少，无法进行聚类评价。')
    rows, fitted = [], {}
    # 限制线程避免小样本聚类启动过多线程；不改变统计方法。
    with threadpool_limits(limits=1):
        for k in range(2, min(5, len(X) - 1) + 1):
            model = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X)
            labels = model.labels_
            score = float(silhouette_score(X, labels)) if 1 < len(set(labels)) < len(X) else None
            rows.append({'groups': k, 'silhouette': score})
            fitted[k] = model
    valid_rows = [r for r in rows if r['silhouette'] is not None]
    if not valid_rows:
        raise ValueError('所有候选分组均无法计算轮廓系数。')
    best = sorted(valid_rows, key=lambda r: (-r['silhouette'], r['groups']))[0]
    k = best['groups']
    labels = pd.DataFrame({'station_id': X.index, 'cluster': fitted[k].labels_ + 1})
    labels['center_distance'] = np.linalg.norm(X.to_numpy() - fitted[k].cluster_centers_[fitted[k].labels_], axis=1)
    labels.to_csv(out / 'labels.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(rows).to_csv(out / 'evaluation.csv', index=False, encoding='utf-8-sig')
    profile = []
    for group, members in labels.groupby('cluster'):
        center = X.loc[members.station_id].mean()
        for (day, hour, flow), value in center.items():
            profile.append(dict(cluster=int(group), is_workday=int(day), hour=int(hour), direction=flow, proportion=float(value)))
    pd.DataFrame(profile).to_csv(out / 'profiles.csv', index=False, encoding='utf-8-sig')
    meta = dict(groups=k, silhouette=best['silhouette'], features=68, stations=len(X), excluded_station_ids=excluded,
                random_state=42, n_init=10, start='2017-05-01', end='2017-08-31',
                note='四个月有效数据的探索性内部评价；没有独立测试或未来预测验证。')
    (out / '说明.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return meta
