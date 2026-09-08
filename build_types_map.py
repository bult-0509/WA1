# -*- coding: utf-8 -*-
"""
build_types_map.py — 把 station_type_result.csv 生成交互式站点功能类型图 (station_types_map.html)。

用法: python build_types_map.py
输出: analysis_output/station_types_map.html (依赖同目录 echarts.min.js, 离线可打开)

页面功能:
  - 站点散点图 (经度/纬度相对位置, 非行政区划地图): 按功能类型着色, 大小=500m内设施总数;
  - 类型筛选胶囊 + 判定依据筛选 + 站名/ID 搜索;
  - 点击站点 → 右侧详情: 六类设施计数柱图 (命中为彩色, 未命中为灰色) + 判定说明;
  - 全量可筛选表格 + 各类型数量分布图 + 每类设施的分布阈值表。
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analysis_output"

# 与 classify_stations.py 保持一致
TYPE_ORDER = ["旅游区", "交通枢纽", "商务办公区", "商业区", "文教区", "居住区", "其他"]
TYPE_COLORS = {
    "旅游区": "#4FB3A5",
    "交通枢纽": "#5B9BD5",
    "商务办公区": "#8E7CC3",
    "商业区": "#E8846A",
    "文教区": "#D9A441",
    "居住区": "#6FBF73",
    "其他": "#A8A8A8",
}
TOP_RATIO = 0.20  # 与 classify_stations.py 默认一致, 用于页面上的阈值表


def load_data():
    df = pd.read_csv(OUT / "station_type_result.csv")
    # 中文站名
    sd = json.load(open(OUT / "spatial_data.json", encoding="utf-8"))
    cn = {int(s["stationID"]): s.get("name_cn") or s["name"] for s in sd["stations"]}

    records = []
    for _, r in df.iterrows():
        sid = int(r["stationID"])
        records.append({
            "id": sid,
            "name": str(r["name"]),
            "cn": cn.get(sid, str(r["name"])),
            "lon": float(r["poi_lon"]),
            "lat": float(r["poi_lat"]),
            "c": [int(r[f"cnt_{g}"]) for g in TYPE_ORDER[:6]],
            "h": [bool(r[f"hit_{g}"]) for g in TYPE_ORDER[:6]],
            "t": str(r["final_type"]),
            "b": str(r["basis"]),
        })
    return records


def compute_stats(records):
    """每类设施: 阈值(前20%分位, 稀有类降为1)、中位、最大、命中站数。"""
    groups = TYPE_ORDER[:6]
    counts = np.array([rec["c"] for rec in records])          # (302, 6)
    hits = np.array([rec["h"] for rec in records])
    n = len(records)
    n_hit = max(1, round(n * TOP_RATIO))
    stats = {}
    for j, g in enumerate(groups):
        vals = np.sort(counts[:, j])[::-1]
        thr = int(vals[min(n_hit - 1, n - 1)])
        if thr == 0 and vals[0] > 0:
            thr = 1
        stats[g] = {
            "threshold": thr,
            "median": int(np.median(counts[:, j])),
            "max": int(vals[0]),
            "hit": int(hits[:, j].sum()),
        }
    return stats


def build_html(records, stats, gen_time):
    data_json = json.dumps(records, ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)
    colors_json = json.dumps(TYPE_COLORS, ensure_ascii=False)
    types_json = json.dumps(TYPE_ORDER, ensure_ascii=False)

    html = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>上海地铁站 · 功能类型互动分布</title>
<style>
:root{--text:#1A1B1C;--muted:#6B7280;--bg:#F4F3EE;--card:#FFFFFF;--line:#E4E3DD;--accent:#2E8B8B}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.6 "PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1460px;margin:0 auto;padding:22px 20px 40px}
h1{margin:0 0 4px;font-size:24px;letter-spacing:.5px}
h2{font-size:16px;margin:0 0 10px}
.sub{color:var(--muted);font-size:13px}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap}
.badge{border:1px solid #b9dfd9;color:#15877d;background:#e7f6f1;border-radius:30px;padding:4px 13px;font-size:13px;white-space:nowrap}
.controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:16px 0}
input[type=text],select{font:inherit;padding:8px 11px;border:1px solid #cdd8e3;border-radius:9px;background:#fff;color:var(--text)}
input[type=text]{width:230px}
.pills{display:flex;gap:7px;flex-wrap:wrap}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:#fff;border-radius:30px;padding:6px 11px;font-size:13px;cursor:pointer;user-select:none}
.pill .dot{width:10px;height:10px;border-radius:50%}
.pill.on{border-color:#2E8B8B;box-shadow:0 0 0 1px #2E8B8B inset}
.pill .cnt{color:var(--muted);font-size:12px}
.pill.off{opacity:.45}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0}
.metric{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.metric .v{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
.metric .k{color:var(--muted);font-size:13px;margin-top:2px}
.grid{display:grid;grid-template-columns:1.65fr 1fr;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;min-width:0}
.chart{width:100%;height:540px}
.chart.small{height:250px}
.note{color:var(--muted);font-size:12px;margin-top:8px}
.hint{color:var(--muted);font-size:12px;line-height:1.9;margin-top:6px}
#detailName{font-size:20px;font-weight:700;margin:0}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 4px}
.tbadge{display:inline-flex;align-items:center;gap:6px;border-radius:20px;padding:3px 11px;font-size:13px;color:#fff}
.bbase{border-radius:20px;padding:3px 11px;font-size:12px;background:#eef2f5;color:#556}
#detailMeta{color:var(--muted);font-size:13px;margin:4px 0 10px}
#detailTopHits{background:#f6f8f9;border-left:3px solid #2E8B8B;padding:8px 12px;font-size:13px;border-radius:0 8px 8px 0;margin-top:8px;line-height:1.8}
#detailTopHits b{color:var(--accent)}
.gap{margin-top:14px}
.twocol{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-top:14px}
table{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap}
.twrap{max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:10px}
th{position:sticky;top:0;background:#f8fafc;color:var(--muted);text-align:left;font-weight:600;padding:9px 10px;border-bottom:1px solid var(--line);z-index:1}
td{padding:8px 10px;border-bottom:1px solid #f0f2f4}
tr{cursor:pointer}
tr:hover{background:#eef5f5}
tr.sel{background:#dcefef}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tdot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.foot{color:var(--muted);font-size:12px;border-top:1px solid var(--line);margin-top:22px;padding-top:14px;line-height:1.9}
.foot b{color:#15877d}
.fallback{padding:60px 20px;text-align:center;color:var(--muted);font-size:15px}
@media(max-width:960px){.grid,.twocol{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.chart{height:420px}}
@media(max-width:520px){.metrics{grid-template-columns:repeat(2,1fr)}.metric .v{font-size:21px}.wrap{padding:14px 12px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1>上海地铁站 · 功能类型互动分布</h1>
      <div class="sub">302 站 · 按 500m 半径内 POI 设施分布分类（前 20% 定阈值）· 交互式探索</div>
    </div>
    <span class="badge">旅游 / 交通 / 商务 / 商业 / 文教 / 居住</span>
  </div>

  <div class="controls">
    <input type="text" id="q" placeholder="搜索站名（中/英）或 ID" aria-label="搜索站名">
    <span class="pills" id="pills"></span>
    <label style="font-size:13px;color:var(--muted)">判定依据
      <select id="basis">
        <option value="all">全部</option>
        <option value="hit">真命中</option>
        <option value="best_fit">兜底</option>
        <option value="empty">无设施</option>
      </select>
    </label>
  </div>

  <div class="metrics">
    <div class="metric"><div class="v" id="mTotal">–</div><div class="k">站点总数</div></div>
    <div class="metric"><div class="v" id="mShow">–</div><div class="k">当前显示</div></div>
    <div class="metric"><div class="v" id="mHit">–</div><div class="k">真命中站数</div></div>
    <div class="metric"><div class="v" id="mTop">–</div><div class="k">主导类型</div></div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>站点空间分布 · 按功能类型着色 <span class="sub">（点大小 = 500m 内设施总数；滚轮缩放，点击查看详情）</span></h2>
      <div id="scatterChart" class="chart" role="img" aria-label="站点按功能类型着色的散点分布图"></div>
      <div class="note">相对位置散点图：横纵轴为经度/纬度（已做 GCJ02 坐标校正），仅用于观察空间分布，非行政区划地图、不表示精确地理边界。站点集中处有重叠，可滚轮缩放。</div>
    </div>
    <div class="card">
      <h2>站点详情</h2>
      <div id="detailName">点击左侧任意站点</div>
      <div class="badges" id="detailBadges"></div>
      <div id="detailMeta"></div>
      <div id="detailChart" class="chart small" role="img" aria-label="该站六类设施计数柱状图"></div>
      <div class="hint">彩色柱 = 该类设施命中前 20% 分布阈值（判定为该类型候选）；灰色柱 = 未命中。命中多类时取“超出阈值倍数”最高者，并列按优先级。</div>
      <div id="detailTopHits"></div>
    </div>
  </div>

  <div class="twocol">
    <div class="card">
      <h2>各类型站点数（随筛选更新）</h2>
      <div id="distChart" class="chart" style="height:300px" role="img" aria-label="各功能类型站点数量柱状图"></div>
      <div class="note">每类设施的 500m 分布阈值（前 20% 分位）与命中站数</div>
    </div>
    <div class="card">
      <h2>分布阈值与口径</h2>
      <table id="thrTable"></table>
      <div class="hint">阈值口径：每类设施取全站分布前 20% 的设施数作为命中线；若前 20% 分位为 0（设施很稀有，如风景名胜），降为“有 1 个即命中”。一个站命中多类时按超出阈值倍数定最终类型，倍数并列按优先级：旅游区 &gt; 交通枢纽 &gt; 商务办公区 &gt; 商业区 &gt; 文教区 &gt; 居住区。</div>
    </div>
  </div>

  <div class="card gap">
    <h2>全量站点明细（302 站）</h2>
    <div class="twrap">
      <table id="mainTable">
        <thead><tr>
          <th>ID</th><th>站名</th><th>类型</th><th>判定</th>
          <th class="num">商业</th><th class="num">居住</th><th class="num">旅游</th>
          <th class="num">交通</th><th class="num">商务</th><th class="num">文教</th><th class="num">设施合计</th>
        </tr></thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
    <div class="note">点击任意行查看详情；筛选与搜索同步作用于散点图、分布图与表格。</div>
  </div>

  <div class="foot">
    <b>数据口径：</b>站点位置来自 stationInfo.csv（WGS84→GCJ02 校正，与 POI 坐标对齐）；设施来自 2017 上海市 POI 全量（162.5 万条）在 500m 缓冲区内按大类计数；分类脚本 classify_stations.py，全量可复现（python classify_stations.py 后执行 python build_types_map.py 重新生成本页）。<br>
    <b>坐标说明：</b>散点按经纬度相对位置绘制，非精确地图，不表示行政区划边界。<br>
    页面离线可用：本文件与同目录 echarts.min.js 一起打开即可，无需联网。生成时间：__GEN__。
  </div>
</div>

<script src="echarts.min.js"></script>
<script>
window.STATION_DATA = __DATA__;
window.THRESHOLDS = __THRESH__;
window.TYPE_COLORS = __COLORS__;
window.TYPE_ORDER = __TYPES__;
</script>
<script>
(function(){
  var DATA = window.STATION_DATA || [];
  var COLORS = window.TYPE_COLORS || {};
  var ORDER = window.TYPE_ORDER || [];
  var THR = window.THRESHOLDS || {};
  var GROUPS = ORDER.slice(0, 6);
  var GROUPS_CN = {0:'商业',1:'居住',2:'旅游',3:'交通',4:'商务',5:'文教'};
  var state = {types: {}, basis: 'all', query: '', selected: null};

  function fail(msg){
    var box = document.getElementById('scatterChart');
    if (box) box.innerHTML = '<div class="fallback">' + msg + '</div>';
  }
  if (typeof echarts === 'undefined'){ fail('图表库 (echarts.min.js) 加载失败，请确认与本站点文件位于同一目录。下方表格仍可正常使用。'); return; }

  var scatterEl = document.getElementById('scatterChart');
  var detailEl = document.getElementById('detailChart');
  var distEl = document.getElementById('distChart');
  if (!scatterEl || !detailEl || !distEl){ fail('页面容器缺失'); return; }
  var scatterChart = echarts.init(scatterEl);
  var detailChart = echarts.init(detailEl);
  var distChart = echarts.init(distEl);

  function colorOf(t){ return COLORS[t] || '#A8A8A8'; }
  function visible(){
    return DATA.filter(function(s){
      if (!state.types[s.t]) return false;
      if (state.basis !== 'all' && s.b !== state.basis) return false;
      if (state.query){
        var q = state.query.toLowerCase();
        if (String(s.id).indexOf(q) < 0 && s.name.toLowerCase().indexOf(q) < 0 && s.cn.indexOf(q) < 0) return false;
      }
      return true;
    });
  }
  var MAXTOTAL = 1;
  DATA.forEach(function(s){ var tot = s.c.reduce(function(a,b){return a+b;},0); s.total = tot; if (tot > MAXTOTAL) MAXTOTAL = tot; });
  /* 固定全城坐标范围: 筛选/搜索时视图不跳变, 单点也不会坐标轴退化 */
  var LON0 = Infinity, LON1 = -Infinity, LAT0 = Infinity, LAT1 = -Infinity;
  DATA.forEach(function(s){
    if (s.lon < LON0) LON0 = s.lon; if (s.lon > LON1) LON1 = s.lon;
    if (s.lat < LAT0) LAT0 = s.lat; if (s.lat > LAT1) LAT1 = s.lat;
  });
  var XL = Math.round((LON0 - (LON1 - LON0) * 0.05) * 1000) / 1000, XR = Math.round((LON1 + (LON1 - LON0) * 0.05) * 1000) / 1000;
  var YB = Math.round((LAT0 - (LAT1 - LAT0) * 0.10) * 1000) / 1000, YT = Math.round((LAT1 + (LAT1 - LAT0) * 0.10) * 1000) / 1000;

  /* ---------- 散点图 ---------- */
  function scatterOption(list){
    var data = list.map(function(s){
      return {
        value: [s.lon, s.lat, s.total, s.id],
        itemStyle: { color: colorOf(s.t) },
        station: s
      };
    });
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        confine: true,
        textStyle: { fontSize: 12, lineHeight: 17 },
        formatter: function(p){
          if (!p || !p.data || !p.data.station) return '';
          var s = p.data.station;
          var lines = ['<b>' + s.cn + '（' + s.name + '）</b>',
                       '类型：' + s.t + (s.b === 'hit' ? ' · 真命中' : (s.b === 'best_fit' ? ' · 兜底' : ' · 无设施')),
                       'ID：' + s.id + '　坐标：' + s.lon.toFixed(4) + ', ' + s.lat.toFixed(4)];
          s.c.forEach(function(c, j){ lines.push(GROUPS_CN[j] + '：' + c + (s.h[j] ? '（命中）' : '')); });
          lines.push('设施合计：' + s.total);
          return lines.join('\n');
        }
      },
      dataZoom: [{ type: 'inside' }],
      xAxis: { type: 'value', name: '经度', min: XL, max: XR, axisLabel: { color: '#555', fontSize: 11 }, splitLine: { lineStyle: { color: '#EDEDE7' } } },
      yAxis: { type: 'value', name: '纬度', min: YB, max: YT, axisLabel: { color: '#555', fontSize: 11 }, splitLine: { lineStyle: { color: '#EDEDE7' } } },
      series: [{
        type: 'scatter',
        name: '站点',
        data: data,
        symbolSize: function(v){ return 5 + 9 * Math.sqrt((v[2] || 0) / MAXTOTAL); },
        emphasis: { scale: 1.6, focus: 'self' }
      }]
    };
  }
  scatterChart.setOption(scatterOption(visible()));
  scatterChart.on('click', function(p){
    if (p && p.data && p.data.station) select(p.data.station);
  });

  /* ---------- 详情 ---------- */
  function detailOption(s){
    var data = s.c.map(function(c, j){
      return { value: c, itemStyle: { color: s.h[j] ? colorOf(GROUPS[j]) : '#D8DCDD' } };
    });
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item', renderMode: 'richText', confine: true,
        textStyle: { fontSize: 12, lineHeight: 17 },
        formatter: function(p){
          if (!p || !p.dataIndex == null) return '';
          var j = p.dataIndex;
          return GROUPS[j] + '：' + p.value + ' 个<br/>阈值：' + THR[GROUPS[j]].threshold + '　' + (s.h[j] ? '✓ 命中' : '未命中');
        }
      },
      grid: { left: 50, right: 20, top: 30, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: GROUPS.map(function(g){ return g.replace('区','').replace('枢纽',''); }), axisLabel: { color: '#444', fontSize: 12 } },
      yAxis: { type: 'value', name: '设施数', axisLabel: { color: '#555', fontSize: 11 } },
      series: [{ type: 'bar', barWidth: '46%', data: data, label: { show: true, position: 'top', color: '#555', fontSize: 11 } }]
    };
  }
  function select(s){
    state.selected = s.id;
    document.getElementById('detailName').textContent = s.cn + '（' + s.name + '）';
    document.getElementById('detailMeta').textContent = 'stationID ' + s.id + ' · 经度 ' + s.lon.toFixed(5) + ' · 纬度 ' + s.lat.toFixed(5) + ' · 500m 内设施合计 ' + s.total;
    var badges = document.getElementById('detailBadges');
    badges.innerHTML = '';
    var tb = document.createElement('span');
    tb.className = 'tbadge'; tb.style.background = colorOf(s.t);
    tb.innerHTML = '<span style="width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.85);display:inline-block"></span>' + s.t;
    var bb = document.createElement('span');
    bb.className = 'bbase';
    bb.textContent = s.b === 'hit' ? '真命中' : (s.b === 'best_fit' ? '兜底（未达任何阈值，取相对最高）' : '无设施');
    badges.appendChild(tb); badges.appendChild(bb);
    var hits = [];
    s.c.forEach(function(c, j){ if (s.h[j]) hits.push(GROUPS[j] + ' ' + c + '/' + THR[GROUPS[j]].threshold); });
    document.getElementById('detailTopHits').innerHTML = hits.length
      ? '<b>命中：</b>' + hits.join('　')
      : '<b>说明：</b>六类设施均未达前 20% 分布阈值，取超出阈值倍数最高的一类作为兜底类型。';
    detailChart.setOption(detailOption(s), true);
    scatterChart.setOption({ series: [{ data: null }] }, true);
    scatterChart.setOption(scatterOption(visible()), true);
    refreshTable();
  }

  /* ---------- 分布图 + 阈值表 ---------- */
  function distOption(list){
    var cnt = {};
    list.forEach(function(s){ cnt[s.t] = (cnt[s.t] || 0) + 1; });
    var names = Object.keys(cnt).sort(function(a, b){ return cnt[b] - cnt[a]; });
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', triggerOn: 'click', renderMode: 'richText', confine: true, textStyle: { fontSize: 12 } },
      grid: { left: 10, right: 40, top: 10, bottom: 10, containLabel: true },
      xAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#555', fontSize: 11 } },
      yAxis: { type: 'category', data: names, axisLabel: { color: '#333', fontSize: 12 } },
      series: [{ type: 'bar', barWidth: 14, data: names.map(function(n){ return { value: cnt[n], itemStyle: { color: colorOf(n) } }; }), label: { show: true, position: 'right', color: '#333', fontSize: 12 } }]
    };
  }
  function thrTable(){
    var html = '<thead><tr><th>设施类型</th><th class="num">阈值</th><th class="num">中位数</th><th class="num">最大</th><th class="num">命中站数</th></tr></thead><tbody>';
    ORDER.slice(0, 6).forEach(function(g){
      var t = THR[g] || {};
      html += '<tr><td><span class="tdot" style="background:' + colorOf(g) + '"></span>' + g + '</td><td class="num">' + t.threshold + '</td><td class="num">' + t.median + '</td><td class="num">' + t.max + '</td><td class="num">' + t.hit + '</td></tr>';
    });
    document.getElementById('thrTable').innerHTML = html + '</tbody>';
  }
  thrTable();

  /* ---------- 表格 ---------- */
  var tbody = document.getElementById('tableBody');
  function refreshTable(){
    var list = visible();
    var html = '';
    list.forEach(function(s){
      html += '<tr data-id="' + s.id + (state.selected === s.id ? '" class="sel"' : '"') + '>' +
        '<td>' + s.id + '</td>' +
        '<td>' + s.cn + '<span style="color:var(--muted)"> · ' + s.name + '</span></td>' +
        '<td><span class="tdot" style="background:' + colorOf(s.t) + '"></span>' + s.t + '</td>' +
        '<td>' + (s.b === 'hit' ? '真命中' : (s.b === 'best_fit' ? '兜底' : '无设施')) + '</td>' +
        s.c.map(function(c, j){ return '<td class="num">' + c + '</td>'; }).join('') +
        '<td class="num"><b>' + s.total + '</b></td></tr>';
    });
    tbody.innerHTML = html;
    Array.prototype.forEach.call(tbody.querySelectorAll('tr'), function(tr){
      tr.addEventListener('click', function(){
        var rec = DATA.filter(function(x){ return x.id === Number(tr.getAttribute('data-id')); })[0];
        if (rec) select(rec);
      });
    });
  }

  /* ---------- 顶部控件 ---------- */
  function renderPills(){
    var box = document.getElementById('pills');
    box.innerHTML = '';
    ORDER.forEach(function(t){
      var n = DATA.filter(function(s){ return s.t === t; }).length;
      var p = document.createElement('span');
      p.className = 'pill ' + (state.types[t] ? 'on' : 'off');
      p.innerHTML = '<span class="dot" style="background:' + colorOf(t) + '"></span>' + t + '<span class="cnt">' + n + '</span>';
      p.addEventListener('click', function(){
        state.types[t] = !state.types[t];
        p.className = 'pill ' + (state.types[t] ? 'on' : 'off');
        applyFilters();
      });
      box.appendChild(p);
    });
  }
  function applyFilters(){
    var list = visible();
    scatterChart.setOption(scatterOption(list), true);
    distChart.setOption(distOption(list), true);
    refreshTable();
    var mShow = document.getElementById('mShow');
    mShow.textContent = list.length;
    document.getElementById('mHit').textContent = list.filter(function(s){ return s.b === 'hit'; }).length;
    var cnt = {};
    list.forEach(function(s){ cnt[s.t] = (cnt[s.t] || 0) + 1; });
    var top = Object.keys(cnt).sort(function(a, b){ return cnt[b] - cnt[a]; })[0];
    document.getElementById('mTop').textContent = top ? top + ' ' + cnt[top] : '—';
    if (state.selected !== null){
      var still = DATA.filter(function(x){ return x.id === state.selected; })[0];
      if (!still || !state.types[still.t] || (state.basis !== 'all' && still.b !== state.basis)) state.selected = null;
    }
    refreshTable();
  }

  document.getElementById('q').addEventListener('input', function(e){
    state.query = e.target.value.trim();
    applyFilters();
    var list = visible();
    if (list.length) select(list[0]);
  });
  document.getElementById('basis').addEventListener('change', function(e){
    state.basis = e.target.value;
    applyFilters();
  });
  window.addEventListener('resize', function(){
    scatterChart.resize(); detailChart.resize(); distChart.resize();
  });

  /* ---------- 初始化 ---------- */
  ORDER.forEach(function(t){ state.types[t] = true; });
  renderPills();
  applyFilters();
  document.getElementById('mTotal').textContent = DATA.length;
  if (DATA.length) select(DATA[0]);
})();
</script>
</body>
</html>"""
    html = (html
            .replace("__DATA__", data_json)
            .replace("__THRESH__", stats_json)
            .replace("__COLORS__", colors_json)
            .replace("__TYPES__", types_json)
            .replace("__GEN__", gen_time))
    return html


def main():
    records = load_data()
    stats = compute_stats(records)
    gen_time = time.strftime("%Y-%m-%d %H:%M")
    html = build_html(records, stats, gen_time)
    out_path = OUT / "station_types_map.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"已生成: {out_path}  ({len(html)/1024:.0f} KB, {len(records)} 站)")
    print("类型分布:", dict(pd.Series([r['t'] for r in records]).value_counts()))


if __name__ == "__main__":
    main()
