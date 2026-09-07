"""页面使用的三个统计函数。"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, pointbiserialr


def daily_flow(hourly):
    return hourly.groupby(['date', 'is_workday'], as_index=False)[['inFlow', 'outFlow']].sum()


def direction_index(inflow, outflow):
    denominator = inflow + outflow
    return (inflow - outflow) / denominator.replace(0, np.nan)


def weather_correlations(joined):
    rows = []
    for day, group in joined.groupby('is_workday'):
        for field, method in [('temperature_2m_mean', 'Pearson'), ('rain_sum', '点二列相关')]:
            pairs = group[[field, 'inFlow']].dropna()
            x = pairs[field] if method == 'Pearson' else (pairs[field] > 5).astype(int)
            reason, r, p = '', np.nan, np.nan
            if len(pairs) < 3:
                reason = '少于3天，不计算'
            elif x.nunique() < 2 or pairs.inFlow.nunique() < 2:
                reason = '变量无变化，无法计算'
            else:
                result = pearsonr(x, pairs.inFlow) if method == 'Pearson' else pointbiserialr(x, pairs.inFlow)
                r, p = float(result.statistic), float(result.pvalue)
            rows.append({'日类型': '工作日' if day else '非工作日', '因素': '日均温度' if method == 'Pearson' else '日降雨>5mm',
                         '方法': method, '相关系数': r, 'p值': p, '天数': len(pairs), '说明': reason})
    return pd.DataFrame(rows)
