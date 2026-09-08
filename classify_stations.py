# -*- coding: utf-8 -*-
"""
classify_stations.py — 根据站点 500m 范围内的 POI 设施分布, 将上海地铁站划分为功能区。

站区类型 (6 类 + 兜底): 旅游区 / 交通枢纽 / 商务办公区 / 商业区 / 文教区 / 居住区 / 其他

判定逻辑 (与"分布靠后即为该类"的思路一致, 阈值完全由数据决定):
    1. 统计每个站 500m 半径内各类设施的数量 (设施大类 → 站区类型的映射见 GROUP_RULES)。
    2. 对每一类设施, 取全站分布的前 TOP_RATIO (默认 25%) 作为命中阈值:
       例: 公交站 500m 内最少 0 个、最多 10 个, 那么 8/9/10 个这类分布靠后的站
       就会被判为"交通枢纽"型。若前 25% 分位恰为 0 (设施很稀有, 如风景名胜),
       则自动降为"只要有 1 个就算命中"。
    3. 命中 1 类 → 直接为该类型。命中多类 (如人民广场: 商场和公交站都多):
       - 默认 tie-break="dominance": 取"超出阈值倍数 = 计数/阈值"最大的一类
         (即在该类设施里站得越靠前越有代表性);
       - 倍数并列/纯优先级模式 (tie-break="priority"): 按 PRIORITY 列表顺序取靠前者。
    4. 六类全部没命中 → 兜底: 取"超出阈值倍数"最高的类型 (每个站都有归属);
       只有六类设施在 500m 内全部为 0 的站才叫"其他"。
    5. (可选) 早高峰 7:00-9:00 客流修正 (默认关闭): 净流出 > 0 → 偏向居住区,
       净流出 < 0 → 偏向商务办公区。注意: 实测早高峰净流出为正的站不一定是居住区
       (人民广场/豫园这类换乘与景点站也如此), 所以默认关闭, 需要时用 --od refine 开启。

输入:
    stationInfo.csv            站点表 (stationID, name, lon, lat)           302 站
    2017上海市POI_全部.csv     全量设施 POI (LON, LAT, BASETYPE, SUBTYPE)   约 162 万条
    (可选) analysis_output/station_timeslot.parquet 或 metroData_ODFlow.csv
           (早高峰客流, 仅用于居住区/商务办公区的二次区分; 文件不存在则自动跳过)

输出:
    analysis_output/station_type_result.csv  每站一行: 各类设施 500m 计数、命中标记、最终类型
    控制台: 每类设施的分布/阈值/命中站数、最终类型统计与示例站点

依赖: pandas, numpy (无第三方扩展依赖)
运行: python classify_stations.py                    # 全量数据, 约 1~2 分钟
      python classify_stations.py --sample 200000    # 调试: 只取前 20 万条 POI 快速试跑
      python classify_stations.py --tie-break priority   # 多类型时纯按固定优先级
      python classify_stations.py --od refine        # 开启早高峰客流修正(默认关闭)
"""

from pathlib import Path
import argparse
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# 1. 可调参数
# ---------------------------------------------------------------------------
# 站区类型 → 设施大类(BASETYPE) 映射; EXCLUDE_SUBTYPE 为需要剔除的二级类。
# 想要加/减类型, 改这里即可, 其余逻辑自动适配。
GROUP_RULES = {
    "商业区":     {"BASETYPE": ["购物服务", "餐饮服务"]},                      # 商场/专卖店/超市/餐厅
    "居住区":     {"BASETYPE": ["商务住宅", "生活服务"]},                      # 住宅小区 + 美容美发/洗衣等居住配套
    "旅游区":     {"BASETYPE": ["风景名胜"]},                                  # 景区/公园/广场 (全上海仅 5.4k 条, 最稀有)
    "交通枢纽":   {"BASETYPE": ["交通设施服务"],                               # 公交站/火车站/机场/长途汽车站/港口/轮渡
                   "EXCLUDE_SUBTYPE": ["停车场", "地铁站", "交通服务相关"]},    # 停车场遍地都是, 会稀释信号
    "商务办公区": {"BASETYPE": ["公司企业", "金融保险服务"]},                  # 公司 + 银行保险 (CBD)
    "文教区":     {"BASETYPE": ["科教文化服务"]},                              # 学校/博物馆/图书馆/美术馆
}

# 多类型命中时的固定优先级 (旅游最稀有、地标性最强 → 居住最普遍、作兜底)。
# 想换顺序直接改这个列表。
PRIORITY = ["旅游区", "交通枢纽", "商务办公区", "商业区", "文教区", "居住区"]

# 站点坐标 WGS84 → GCJ02。spatial_analysis.py 已用 298/302 站名 300m 内匹配验证:
# 站点坐标做 GCJ02 偏移后与 POI 坐标对齐 (POI 按 GCJ02 解释), 500m 统计才准确。
USE_GCJ_SHIFT = True

# 客流修正: 默认关闭 (实测会把人民广场/豫园等站带偏)。"refine" 时优先读
# analysis_output/station_timeslot.parquet, 没有则分块读 metroData_ODFlow.csv (慢)。
OD_REFINE = "off"                # off / refine
OD_OVERRIDE_AMBIGUOUS_ONLY = True  # True: 只修正"居住区+商务办公区"同时命中的模糊站; False: 这两类一律按客流修正
MORNING_WINDOW = (70000, 90000)  # 早高峰 startTime 区间 [07:00:00, 09:00:00)

EARTH_R = 6371008.8              # 地球平均半径(米)


# ---------------------------------------------------------------------------
# 2. 坐标转换 (站点 WGS84 → GCJ02, 与 spatial_analysis.py 一致)
# ---------------------------------------------------------------------------
def gcj(lon, lat):
    """WGS84 → GCJ02 偏移, 输入输出均为 numpy 数组。"""
    x = lon - 105
    y = lat - 35
    a = -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * np.sqrt(np.abs(x))
    a += (20 * np.sin(6 * x * np.pi) + 20 * np.sin(2 * x * np.pi)) * 2 / 3
    a += (20 * np.sin(y * np.pi) + 40 * np.sin(y / 3 * np.pi)) * 2 / 3
    a += (160 * np.sin(y / 12 * np.pi) + 320 * np.sin(y * np.pi / 30)) * 2 / 3
    b = 300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * np.sqrt(np.abs(x))
    b += (20 * np.sin(6 * x * np.pi) + 20 * np.sin(2 * x * np.pi)) * 2 / 3
    b += (20 * np.sin(x * np.pi) + 40 * np.sin(x / 3 * np.pi)) * 2 / 3
    b += (150 * np.sin(x / 12 * np.pi) + 300 * np.sin(x / 30 * np.pi)) * 2 / 3
    rad = lat / 180 * np.pi
    magic = 1 - .006693421622965943 * np.sin(rad) ** 2
    sq = np.sqrt(magic)
    dlon = b * 180 / (6378245 / sq * np.cos(rad) * np.pi)
    dlat = a * 180 / ((6378245 * (1 - .006693421622965943)) / (magic * sq) * np.pi)
    return lon + dlon, lat + dlat


# ---------------------------------------------------------------------------
# 3. 加载 POI 并打上"站区类型"标签
# ---------------------------------------------------------------------------
def load_pois(path, sample=0):
    """读 POI 文件(只要 4 列), 清洗非法坐标, 返回带 group 列的 DataFrame。"""
    pois = pd.read_csv(
        path,
        usecols=["LON", "LAT", "BASETYPE", "SUBTYPE"],
        dtype={"BASETYPE": str, "SUBTYPE": str},
        nrows=sample or None,
    )
    pois = pois.rename(columns={"LON": "lon", "LAT": "lat"})
    pois["lon"] = pd.to_numeric(pois["lon"], errors="coerce")
    pois["lat"] = pd.to_numeric(pois["lat"], errors="coerce")
    pois = pois.dropna(subset=["lon", "lat"])
    # 上海行政范围粗筛, 去掉明显脏数据
    pois = pois[pois["lon"].between(120.5, 122.3) & pois["lat"].between(30.5, 32.1)]
    pois = pois.reset_index(drop=True)

    b = pois["BASETYPE"].fillna("")
    sub = pois["SUBTYPE"].fillna("")
    group = np.full(len(pois), "", dtype=object)
    for g, rule in GROUP_RULES.items():
        mask = b.isin(rule["BASETYPE"]).to_numpy()
        if "EXCLUDE_SUBTYPE" in rule:
            mask = mask & ~sub.isin(rule["EXCLUDE_SUBTYPE"]).to_numpy()
        group[mask] = g
    pois["group"] = group
    return pois


# ---------------------------------------------------------------------------
# 4. 早高峰客流 (居住区 vs 商务办公区的二次修正依据)
# ---------------------------------------------------------------------------
def load_morning_net(mode):
    """
    返回 Series: stationID -> 早高峰(7:00-9:00)净流出(出站-进站)。
    优先读已聚合好的 parquet; 否则分块读 12GB 的 ODFlow.csv (慢但能吃全量数据);
    mode=off 或均不可用时返回 None。
    """
    if mode == "off":
        return None
    lo, hi = MORNING_WINDOW
    pq_file = ROOT / "analysis_output" / "station_timeslot.parquet"
    od_csv = ROOT / "metroData_ODFlow.csv"

    if pq_file.exists():
        df = pd.read_parquet(pq_file, columns=["startTime", "stationID", "Flow_in", "Flow_out"])
        m = df["startTime"].between(lo, hi - 1)
        w = df[m]
        net = (w["Flow_out"] - w["Flow_in"]).groupby(w["stationID"]).sum()
        print(f"客流: 使用 analysis_output/station_timeslot.parquet, 早高峰行数 {len(w):,}")
        return net

    if od_csv.exists():
        print("客流: parquet 不存在, 分块读取 metroData_ODFlow.csv (12GB, 会比较慢)...")
        acc_out = pd.Series(dtype=np.int64)
        acc_in = pd.Series(dtype=np.int64)
        rows = 0
        for c in pd.read_csv(od_csv, chunksize=2_000_000,
                             usecols=["startTime", "originStation", "destinationStation", "Flow"],
                             skipinitialspace=True):
            m = c["startTime"].between(lo, hi - 1)
            w = c[m]
            if len(w):
                rows += len(w)
                acc_out = acc_out.add(w.groupby("originStation")["Flow"].sum(), fill_value=0)
                acc_in = acc_in.add(w.groupby("destinationStation")["Flow"].sum(), fill_value=0)
        print(f"客流: ODFlow.csv 早高峰行数 {rows:,}")
        return acc_out.subtract(acc_in, fill_value=0)

    print("客流: 未找到 parquet 或 ODFlow.csv, 跳过客流修正")
    return None


# ---------------------------------------------------------------------------
# 5. 主流程
# ---------------------------------------------------------------------------
def _haversine_m(lat1, lon1, lat2, lon2):
    """输入均为弧度制 numpy 数组, 返回球面距离(米)。"""
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def count_within_radius(stations, pois, groups, radius):
    """
    纯 numpy 统计每个站 radius 米内的各类设施数 (不依赖 sklearn):
      1) 将 POI 按经度排序;
      2) 每个站用 [lon±Δlon, lat±Δlat] 的包围盒做 searchsorted 粗筛 (包围盒完整包住 500m 圆);
      3) 对粗筛结果用 haversine 精确校验 <= radius, 再按设施组计数。
    """
    plon = pois["lon"].to_numpy()
    plat = pois["lat"].to_numpy()
    pgrp = pois["group"].to_numpy()
    order = np.argsort(plon, kind="stable")
    lon_sorted, lat_sorted, grp_sorted = plon[order], plat[order], pgrp[order]

    # 500m 对应的经纬度跨度 (上海纬度 ~31.2°, 1°经度 ≈ 95.3km, 1°纬度 ≈ 110.9km)
    dlon = radius * 1.001 / (111320 * np.cos(np.radians(31.2)))
    dlat = radius * 1.001 / 110540

    n_st = len(stations)
    counts = np.zeros((n_st, len(groups)), dtype=int)
    slon = stations["poi_lon"].to_numpy()
    slat = stations["poi_lat"].to_numpy()
    for i in range(n_st):
        lo = np.searchsorted(lon_sorted, slon[i] - dlon)
        hi = np.searchsorted(lon_sorted, slon[i] + dlon)
        if lo >= hi:
            continue
        c_lon = lon_sorted[lo:hi]
        c_lat = lat_sorted[lo:hi]
        c_grp = grp_sorted[lo:hi]
        m = (c_lat >= slat[i] - dlat) & (c_lat <= slat[i] + dlat)
        c_lon, c_lat, c_grp = c_lon[m], c_lat[m], c_grp[m]
        if len(c_lon) == 0:
            continue
        d = _haversine_m(np.radians(slat[i]), np.radians(slon[i]),
                         np.radians(c_lat), np.radians(c_lon))
        sel = c_grp[d <= radius]
        sel = sel[sel != ""]          # 剔除未映射到任何站区类型的 POI
        if len(sel):
            for u, cc in zip(*np.unique(sel, return_counts=True)):
                counts[i, groups.index(u)] = cc
    return counts


def main():
    ap = argparse.ArgumentParser(description="按 500m 内 POI 分布给地铁站划分功能区")
    ap.add_argument("--poi", default=str(ROOT / "2017上海市POI_全部.csv"))
    ap.add_argument("--station", default=str(ROOT / "stationInfo.csv"))
    ap.add_argument("--od", default=OD_REFINE, choices=["off", "refine"],
                    help="off=不用客流(默认); refine=用早高峰净流出修正居住区/商务办公区")
    ap.add_argument("--radius", type=float, default=500.0, help="统计半径(米), 默认 500")
    ap.add_argument("--top-ratio", type=float, default=0.20,
                    help="每类设施取分布前多少比例作为命中阈值, 默认 0.20 "
                         "(实测 0.25 时公交站类因同分站多命中膨胀, 0.20 最均衡, 可自行调整)")
    ap.add_argument("--tie-break", default="dominance", choices=["dominance", "priority"],
                    help="多类型命中时: dominance=取超出阈值倍数最大者(默认), priority=纯按固定优先级")
    ap.add_argument("--sample", type=int, default=0, help="调试用: 只读前 N 条 POI, 0=全量")
    args = ap.parse_args()

    t0 = time.time()

    # ---- 站点 ----
    stations = pd.read_csv(args.station)
    stations = stations.sort_values("stationID").reset_index(drop=True)
    n_st = len(stations)
    if USE_GCJ_SHIFT:
        gx, gy = gcj(stations["lon"].to_numpy(), stations["lat"].to_numpy())
        stations["poi_lon"], stations["poi_lat"] = gx, gy
    else:
        stations["poi_lon"], stations["poi_lat"] = stations["lon"], stations["lat"]

    # ---- POI ----
    pois = load_pois(args.poi, args.sample)
    groups = list(GROUP_RULES)
    city_cnt = {g: int((pois["group"] == g).sum()) for g in groups}
    print(f"站点 {n_st} 个 | POI {len(pois):,} 条 (半径 {args.radius:.0f}m, 前 {args.top_ratio:.0%} 定阈值)")

    # ---- 500m 半径计数 (纯 numpy: 包围盒粗筛 + haversine 精确校验) ----
    counts = count_within_radius(stations, pois, groups, args.radius)

    # ---- 分布阈值: 前 top_ratio 的站的设施数即阈值 ----
    n_hit = max(1, round(n_st * args.top_ratio))
    thresholds = {}
    for j, g in enumerate(groups):
        vals = np.sort(counts[:, j])[::-1]
        thr = int(vals[min(n_hit - 1, n_st - 1)])
        if thr == 0 and vals[0] > 0:      # 前25%分位为0(设施很稀有) → 只要有1个就算命中
            thr = 1
        thresholds[g] = thr

    # ---- 命中判定 ----
    hit = np.zeros((n_st, len(groups)), dtype=bool)
    for j, g in enumerate(groups):
        if thresholds[g] >= 1:
            hit[:, j] = counts[:, j] >= thresholds[g]

    # ---- 得分 = 计数/阈值 (超出分布阈值的倍数), 用于多类型并列与无命中兜底 ----
    score = np.zeros((n_st, len(groups)))
    for j, g in enumerate(groups):
        if thresholds[g] >= 1:
            score[:, j] = counts[:, j] / thresholds[g]

    # ---- 最终类型 ----
    labels = np.full(n_st, "其他", dtype=object)
    basis = np.full(n_st, "", dtype=object)   # hit=真命中 / best_fit=兜底 / empty=无设施
    top_hits = []
    for i in range(n_st):
        hs = [g for j, g in enumerate(groups) if hit[i, j]]
        if not hs:
            # 六类都没命中 → 兜底: 取得分(超出阈值倍数)最高的类型; 500m 内六类全为 0 才判"其他"
            if counts[i].max() == 0:
                basis[i] = "empty"
                top_hits.append("")
                continue
            j_best = min(range(len(groups)), key=lambda j: (-score[i, j], PRIORITY.index(groups[j])))
            labels[i] = groups[j_best]
            basis[i] = "best_fit"
            top_hits.append(f"{labels[i]}(兜底, 超出阈值 {score[i, j_best]:.2f} 倍)")
            continue
        basis[i] = "hit"
        if len(hs) == 1:
            labels[i] = hs[0]
        elif args.tie_break == "dominance":
            labels[i] = min(hs, key=lambda g: (-score[i, groups.index(g)], PRIORITY.index(g)))
        else:
            labels[i] = min(hs, key=lambda g: PRIORITY.index(g))
        top_hits.append(";".join(
            f"{g}({counts[i, groups.index(g)]}/{thresholds[g]})"
            for g in sorted(hs, key=lambda x: PRIORITY.index(x))))

    # ---- 客流修正: 早高峰净流出 >0 → 居住区, <0 → 商务办公区 ----
    net = load_morning_net(args.od)
    if net is not None:
        j_res, j_off = groups.index("居住区"), groups.index("商务办公区")
        if OD_OVERRIDE_AMBIGUOUS_ONLY:
            cand = np.where(hit[:, j_res] & hit[:, j_off])[0]
        else:
            cand = np.where((labels == "居住区") | (labels == "商务办公区"))[0]
        changed = 0
        for i in cand:
            s = float(net.get(int(stations.at[i, "stationID"]), 0.0))
            if s > 0 and labels[i] != "居住区":
                labels[i] = "居住区"; changed += 1
            elif s < 0 and labels[i] != "商务办公区":
                labels[i] = "商务办公区"; changed += 1
        print(f"客流修正: {len(cand)} 个候选站, 修正 {changed} 个")

    # ---- 汇总打印 ----
    print("\n== 每类设施 500m 分布与命中阈值 (前 {:.0%} 定阈值) ==".format(args.top_ratio))
    print(f"{'设施类型':<12}{'全市POI':>10}{'min':>6}{'p50':>7}{'max':>7}{'阈值':>6}{'命中站数':>8}")
    for j, g in enumerate(groups):
        col = counts[:, j]
        print(f"{g:<12}{city_cnt[g]:>10}{col.min():>6}{int(np.median(col)):>7}"
              f"{col.max():>7}{thresholds[g]:>6}{int(hit[:, j].sum()):>8}")
    print(f"判定依据: 真命中 {int(np.sum(basis == 'hit'))} 站, 兜底 {int(np.sum(basis == 'best_fit'))} 站, "
          f"无设施 {int(np.sum(basis == 'empty'))} 站")

    print("\n== 最终站区类型分布 ==")
    vc = pd.Series(labels).value_counts()
    for t, c in vc.items():
        names = stations.loc[labels == t, "name"].tolist()
        shown = "、".join(names[:10]) + (" …" if len(names) > 10 else "")
        print(f"{t:<12}{c:>4} 站   {shown}")

    # ---- 落盘 ----
    out = stations[["stationID", "name", "lon", "lat", "poi_lon", "poi_lat"]].copy()
    for j, g in enumerate(groups):
        out[f"cnt_{g}"] = counts[:, j]
        out[f"hit_{g}"] = hit[:, j]
    out["final_type"] = labels
    out["basis"] = basis              # hit=真命中 / best_fit=兜底 / empty=无设施
    out["top_hits"] = top_hits
    if net is not None:
        out["morning_net_out"] = out["stationID"].map(net).fillna(0).astype(np.int64)

    out_path = ROOT / "analysis_output" / "station_type_result.csv"
    out_path.parent.mkdir(exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n结果已写入: {out_path}  (用时 {time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
