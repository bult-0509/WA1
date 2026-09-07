"""本地七页客流分析界面。先准备汇总数据，日常演示无需原始大文件。"""
from pathlib import Path
import json
import html
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from src import analysis as a, charts as c
from src.data_processing import FLOW

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/processed'
st.set_page_config(page_title='沪上流动 · 地铁客流分析', page_icon='assets/favicon.svg', layout='wide', initial_sidebar_state='expanded')
st.html('''<style>
@font-face{
  font-family:"Alimama FangYuanTi VF";
  src:url("app/static/fonts/AlimamaFangYuanTiVF-Thin.woff2") format("woff2");
  font-style:normal;font-weight:100 900;font-display:swap;
}
html,body,[class*="css"],.stApp,.stApp p,.stApp label,.stApp h1,.stApp h2,.stApp h3,
.stApp button,.stApp input,.stApp textarea{font-family:"Alimama FangYuanTi VF","Microsoft YaHei","Segoe UI",sans-serif;}
.block-container{padding-top:4.25rem;padding-bottom:2.5rem;max-width:1500px;}
[data-testid="stAppDeployButton"]{display:none;}
[data-testid="stSidebar"]{background:#102B3B;color:#EDF6F7;border-right:1px solid #183D4D;}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h3{color:#EDF6F7;}
[data-testid="stSidebar"] [data-baseweb="select"] div{color:#203748;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#BDCDD4;}
[data-testid="stSidebar"] [role="radiogroup"]{gap:5px;}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:7px 8px;border-radius:8px;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:rgba(105,177,178,.13);}
[data-testid="stMetric"]{background:white;border:1px solid #E1E9ED;border-radius:12px;padding:16px 20px;box-shadow:0 7px 24px rgba(19,52,66,.045);}
[data-testid="stMetricValue"]{font-weight:650;color:#153C4B;font-size:clamp(18px,2.4vw,32px);}
[data-testid="stPlotlyChart"]{border:1px solid #E1E9ED;border-radius:12px;overflow:hidden;box-shadow:0 7px 24px rgba(19,52,66,.035);}
.page-head{position:relative;background:#123442;color:white;border-radius:15px;padding:22px 26px 19px;margin-bottom:10px;overflow:hidden;}
.page-head:after{content:"";position:absolute;right:-42px;top:-75px;width:210px;height:210px;border-radius:50%;border:44px solid rgba(120,194,188,.10);}
.head-row{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;position:relative;z-index:1;}
.head-main{display:flex;gap:16px;align-items:flex-start;min-width:0;}
.page-index{width:38px;height:38px;flex:0 0 38px;border-radius:10px;background:#E88951;color:#102B3B;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:760;}
.page-head h1{font-size:26px;line-height:1.25;letter-spacing:.4px;color:white;margin:0 0 5px;padding:0;}
.page-head p{color:#C7DCDF;font-size:13px;margin:0;line-height:1.65;max-width:780px;}
.head-meta{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end;max-width:340px;}
.head-meta span{border:1px solid rgba(199,220,223,.24);background:rgba(255,255,255,.06);border-radius:999px;padding:5px 9px;color:#D8E8EA;font-size:11px;white-space:nowrap;}
.context-line{display:flex;gap:10px;align-items:center;background:#EEF4F4;border:1px solid #DDE9E8;border-radius:9px;padding:9px 13px;margin:0 0 17px;color:#34565D;font-size:12px;line-height:1.55;}
.context-line b{color:#176B70;white-space:nowrap;}
.insight{background:#E9F3F1;border-left:3px solid #448B85;border-radius:0 8px 8px 0;padding:13px 16px;margin:12px 0;color:#204D4E;line-height:1.7;}
.side-brand{padding:8px 0 20px;border-bottom:1px solid #34505F;margin-bottom:16px;}
.side-brand b{font-size:25px;letter-spacing:2px;color:white;}
.side-brand p{font-size:11px;letter-spacing:2px;opacity:.8;}
.side-section{font-size:12px;font-weight:700;letter-spacing:1.4px;color:#83B7B8;margin:2px 0 5px;}
h2,h3{letter-spacing:.2px;} button:focus-visible{outline:3px solid #64A8AF!important;outline-offset:2px;}
[class*="st-key-quick_"] button{min-height:54px;border:1px solid #DCE7EA;background:#FFFFFF;color:#183D4D;border-radius:11px;font-weight:680;box-shadow:0 6px 18px rgba(19,52,66,.035);}
[class*="st-key-quick_"] button:hover{border-color:#448B85;color:#176B70;background:#F2F8F7;}
[class*="st-key-quick_"] [data-testid="stCaptionContainer"] p{text-align:center;color:#617780;font-size:11px;margin-top:-4px;}
@media(max-width:900px){.head-meta{display:none;}.page-head{padding:20px;}.head-row{gap:12px;}}
@media(max-width:700px){.block-container{padding:4rem .8rem 1.5rem;}.page-head h1{font-size:22px;}.page-index{width:34px;height:34px;flex-basis:34px}.context-line{align-items:flex-start;}.stApp p,.stApp label{font-size:16px;}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
</style>''')


@st.cache_data(show_spinner='正在读取本地数据…')
def load_data():
    tables = {name: pd.read_parquet(DATA / f'{name}.parquet') for name in
              ['station_hourly', 'station_daily', 'network_daily', 'stations', 'calendar', 'weather_daily']}
    tables['quality'] = json.loads((DATA / 'quality.json').read_text(encoding='utf-8'))
    tables['poi_stations'] = pd.read_parquet(DATA / 'poi_stations.parquet')
    tables['poi_city'] = pd.read_parquet(DATA / 'poi_city.parquet')
    tables['poi_quality'] = json.loads((DATA / 'poi_quality.json').read_text(encoding='utf-8'))
    return tables


@st.cache_data(show_spinner=False)
def load_metro_map_html():
    """把本地动画资源装入Streamlit组件；避免浏览器阻止静态HTML内嵌。"""
    base = ROOT / 'static/metro_map'
    page = (base / 'metro_map.html').read_text(encoding='utf-8')
    leaflet_css = (base / 'vendor/leaflet/leaflet.css').read_text(encoding='utf-8')
    page = page.replace('<link rel="stylesheet" href="vendor/leaflet/leaflet.css"/>', f'<style>{leaflet_css}</style>')
    page = page.replace('../fonts/AlimamaFangYuanTiVF-Thin.woff2', '/app/static/fonts/AlimamaFangYuanTiVF-Thin.woff2')
    for source in ['vendor/leaflet/leaflet.js', 'stations.js', 'edges.js', 'data_flow_edges.js']:
        script = (base / source).read_text(encoding='utf-8')
        page = page.replace(f'<script src="{source}"></script>', f'<script>{script}</script>')
    return page


def insight(text):
    st.html(f'<div class="insight">{html.escape(text)}</div>')


def show_plot(fig, key):
    # 图题和下载文件名记录实际筛选；PNG由浏览器本地生成。
    detail = context.replace(' · ', '<br>', 1)
    fig.update_layout(title_text=f'{fig.layout.title.text}<br><sup>{detail}</sup>', margin_t=95)
    config = dict(c.CONFIG)
    config['toImageButtonOptions'] = {'format': 'png', 'filename': f'{key}_{dates[0]}_{dates[1]}', 'scale': 2}
    st.plotly_chart(fig, width='stretch', config=config, key=key)


def table_export(table, key, label='查看数据并导出 CSV'):
    with st.expander(label):
        renamed = table.rename(columns={'station_id': '站点ID', 'name': '站名', 'date': '日期',
            'hour': '小时', 'value': '人次', 'days': '有效天数', 'inFlow': '进站人次', 'outFlow': '出站人次',
            'is_workday': '工作日标记', 'cluster': '分组', 'groups': '分组数', 'silhouette': '轮廓系数',
            'proportion': '占比', 'temperature_2m': '日均温度_摄氏度', 'rain': '日雨量_mm',
            'flow': '站点日均客流', 'poi_count_500m': '500米功能POI数', 'poi_count_1000m': '1公里功能POI数',
            'poi_density_1000m': '1公里POI密度_个每平方公里', 'diversity': '功能多样性',
            'dominant_group': '主要功能组', 'dominant_share': '主要功能组占比', 'rank_gap': '客流与POI百分位差'})
        st.dataframe(renamed, hide_index=True, width='stretch')
        export = renamed.copy()
        export['筛选范围'] = context
        export['站点范围'] = ','.join(map(str, selected)) if selected and not fixed_network and not cluster_view else '全部站点'
        export['日期类型'] = '固定聚类结果' if cluster_view else day_type
        export['有效日期数'] = int(h.date.nunique()) if not cluster_view else int(tables['quality']['valid_days'])
        st.download_button('下载 CSV', export.to_csv(index=False).encode('utf-8-sig'), f'{key}.csv', 'text/csv', on_click='ignore', key=f'download_{key}')


try:
    tables = load_data()
except (OSError, ValueError, KeyError) as error:
    st.error(f'本地数据尚未准备完整：{error}')
    st.info('请完整解压便携包；开发环境请按README准备原始数据后运行 prepare_data.py。')
    st.stop()

stations = tables['stations']
names = dict(zip(stations.station_id, stations.name))
pages = ['项目概览', '时间规律', '站点空间', '出行模式', '天气关联', 'POI与客流', '数据质量']
page_numbers = {name: f'{i:02d}' for i, name in enumerate(pages, start=1)}
with st.sidebar:
    st.html('<div class="side-brand"><b>沪上流动</b><p>METROFLOW · SHANGHAI</p></div>')
    st.html('<div class="side-section">功能</div>')
    page = st.radio('分析导航', pages, format_func=lambda x: f'{page_numbers[x]}　{x}', key='page', label_visibility='collapsed')
    st.divider()
    st.html('<div class="side-section">筛选</div>')
    cluster_view = page == '出行模式' and st.session_state.get('mode', '进出方向') == '站点聚类'
    dynamic_view = page == '站点空间' and st.session_state.get('space_view', '站点总览') == '10分钟动画'
    poi_view = page == 'POI与客流'
    fixed_network = page in ['天气关联', '数据质量'] or dynamic_view
    dates_value = st.date_input('日期范围', value=(pd.Timestamp('2017-05-01').date(), pd.Timestamp('2017-08-31').date()),
        min_value=pd.Timestamp('2017-05-01').date(), max_value=pd.Timestamp('2017-08-31').date(), disabled=cluster_view or dynamic_view, key='dates')
    day_type = st.selectbox('日期类型', ['全部', '工作日', '非工作日'], disabled=cluster_view or dynamic_view, key='day_type')
    selected = st.multiselect('选择站点（留空为全部）', stations.station_id.tolist(),
        format_func=lambda x: f'{names[x]} · {x}', disabled=fixed_network or poi_view, key='stations', placeholder='全部302站')
    direction_label = st.selectbox('客流方向', ['进站', '出站'] + (['进出总量'] if page == '站点空间' else []),
        disabled=fixed_network or cluster_view or page == '出行模式', key='direction')
    st.divider()
    st.caption('2017年5—8月 · 302站 · 本地运行')
    st.caption('图表相机按钮导出 PNG；明细区导出 CSV。')

if len(dates_value) != 2:
    st.info('请选择完整的开始和结束日期。')
    st.stop()
dates = tuple(dates_value)
direction = {v: k for k, v in a.FLOW_NAMES.items()}[direction_label]
if fixed_network:
    direction = 'inFlow'
filter_stations = None if fixed_network or poi_view else selected
h = a.filter_data(tables['station_hourly'], dates, day_type, filter_stations)
d = a.filter_data(tables['station_daily'], dates, day_type, filter_stations)
n = a.filter_data(tables['network_daily'], dates, day_type)
scope = f'所选{len(selected)}站' if selected and not fixed_network else '全网'
context = f'{dates[0]} — {dates[1]} · {day_type} · {scope} · {a.FLOW_NAMES[direction]}人次'
descriptions = {
    '项目概览': ('客流总览', '先看规模和每日变化，再进入专题分析。'),
    '时间规律': ('高峰时段与日期差异', '比较工作日、非工作日和逐日小时分布。'),
    '站点空间': ('站点客流与空间分布', '查看站点排名，或播放10分钟边流量变化。'),
    '出行模式': ('进出方向与出行构成', '查看早晚方向、三类行程和站点分组。'),
    '天气关联': ('天气与全网客流', '按日期类型比较温度、降雨和进站量。'),
    'POI与客流': ('站点周边功能与客流', '比较1公里站点圈的设施密度、功能组合和客流差异。'),
    '数据质量': ('数据质量与统计口径', '查看异常日期、字段含义和处理结果。')}
title, intro = descriptions[page]
if dynamic_view:
    meta_items = ['9 个有效日', '349 条邻接边', '离线运行']
elif poi_view:
    meta_items = ['162.5 万条 POI', '1 公里站点圈', '302 个站点']
else:
    meta_items = ['117 个有效日', '302 个站点', '离线运行']
meta_html = ''.join(f'<span>{html.escape(item)}</span>' for item in meta_items)
st.html(f'''<section class="page-head"><div class="head-row"><div class="head-main">
<div class="page-index">{page_numbers[page]}</div><div><h1>{html.escape(title)}</h1><p>{html.escape(intro)}</p></div>
</div><div class="head-meta">{meta_html}</div></div></section>''')
if dynamic_view:
    context_text = '2017-05-01 — 2017-05-12 · 9个有效日 · 10分钟边流量 · 固定附件范围'
elif cluster_view:
    context_text = '站点聚类使用四个月固定结果；日期和方向筛选不改变分组。'
else:
    context_text = context
st.html(f'<div class="context-line"><b>当前范围</b><span>{html.escape(context_text)}</span></div>')
if h.empty and page != '数据质量' and not cluster_view and not dynamic_view:
    st.warning('当前选择没有有效数据。六个计数缺损日已排除，请扩大日期范围或改选其他日期。')
    st.stop()

if page == '项目概览':
    days = a.daily_series(h, direction)
    values = days.value
    st.subheader('选择分析功能')
    shortcuts = [
        ('时间规律', '高峰 · 热力图', 'quick_time'),
        ('站点空间', '地图 · 排名 · 动画', 'quick_station'),
        ('出行模式', '方向 · 构成 · 聚类', 'quick_mode'),
        ('天气关联', '相关 · 雨日比较', 'quick_weather'),
        ('POI与客流', '密度 · 多样性 · 差异', 'quick_poi'),
        ('数据质量', '异常 · 字段 · 来源', 'quick_quality'),
    ]
    def open_page(target):
        st.session_state.page = target
    for start in range(0, len(shortcuts), 3):
        for col, (target, note, key) in zip(st.columns(3), shortcuts[start:start + 3]):
            with col:
                st.button(f'{page_numbers[target]}  {target.replace("与说明", "")}', key=key,
                          width='stretch', on_click=open_page, args=(target,))
                st.caption(note)
    st.subheader('当前范围概况')
    cols = st.columns(4)
    for col, label, value in zip(cols, ['累计客流 / 万人次', '日均客流 / 万人次', '有效日期 / 天', '分析站点 / 个'],
            [f'{values.sum()/10000:,.1f}', f'{values.mean()/10000:,.1f}', str(len(days)), str(h.station_id.nunique())]):
        col.metric(label, value)
    st.write('')
    left, right = st.columns([1.6, 1])
    with left:
        plot_days = days.set_index('date').reindex(pd.date_range(*dates)).rename_axis('date').reset_index()
        fig = c.line(plot_days, 'date', 'value', title='每日客流变化')
        show_plot(fig, 'overview_daily')
    with right:
        profile = a.hourly_profile(h, direction)
        show_plot(c.line(profile, 'hour', 'value', '日类型', '工作日与非工作日'), 'overview_hourly')
    peak = days.loc[days.value.idxmax()]
    insight(f'{peak.date:%Y年%m月%d日}最高，为{peak.value/10000:,.1f}万人次；日均{values.mean()/10000:,.1f}万人次。六个计数缺损日未计入。')
    summary = pd.DataFrame({'统计量':['总量','日均','日中位数','日最小值','日最大值'],
        '人次':[values.sum(),values.mean(),values.median(),values.min(),values.max()]})
    table_export(summary, 'descriptive_statistics', '查看描述性统计并导出 CSV')
    table_export(days, 'overview_statistics')

elif page == '时间规律':
    profile = a.hourly_profile(h, direction)
    left, right = st.columns([1.1, 1])
    with left:
        show_plot(c.line(profile, 'hour', 'value', '日类型', '小时客流：按有效日日均'), 'hourly_profile')
    with right:
        daily_hour = h.assign(value=a.direction_values(h, direction)).groupby(['date', 'hour']).value.sum().unstack()
        daily_hour = daily_hour.reindex(pd.date_range(*dates))
        fig = c.style(go.Figure(go.Heatmap(z=daily_hour.to_numpy(), x=daily_hour.columns,
            y=daily_hour.index.strftime('%m-%d'), colorscale='Teal', colorbar={'title': '人次'},
            hoverongaps=False, hovertemplate='%{y} %{x}时<br>%{z:,.0f}人次<extra></extra>')), '逐日逐小时客流')
        fig.update_xaxes(title='小时'); fig.update_yaxes(title='日期', type='category', autorange='reversed',
            tickmode='array', tickvals=daily_hour.index.strftime('%m-%d')[::14])
        show_plot(fig, 'time_heatmap')
    sentences = []
    for day_name, group in profile.groupby('日类型'):
        top = group[group.value.eq(group.value.max())]
        sentences.append(f'{day_name}最高小时为'+ '、'.join(f'{int(x)}时' for x in top.hour) + f'，小时日均{group.value.max()/10000:.1f}万人次（{int(group.days.max())}个有效日）')
    insight('；'.join(sentences) + '。热力图空白表示该日未纳入有效分析，不代表零客流。')
    if profile.is_workday.nunique() < 2:
        st.info('当前只含一种日期类型，不能据此比较工作日与非工作日。')
    table_export(profile, 'time_profile')

elif page == '站点空间':
    space_view = st.segmented_control('空间视图', ['站点总览', '10分钟动画'], default='站点总览',
                                      key='space_view', selection_mode='single')
    # 控件切换后重跑，使侧栏禁用状态和页头范围同步更新。
    if (space_view == '10分钟动画') != dynamic_view:
        st.rerun()
    if dynamic_view:
        components.html(load_metro_map_html(), height=760, scrolling=False)
        insight('附件覆盖2017年5月1日至12日。排除5月4日、8日和9日三个计数缺损日后，动画展示9天。边流量是附件中的预生成结果，本项目未重新估计；颜色和线宽表示相对强度，边流量合计不等同于去重乘客人数。')
        st.caption('地图使用发布方站点坐标和邻接边，无在线底图。可切换日期、播放或暂停、逐时段查看，并调整播放速度。')
    else:
        ranking = a.station_ranking(d, direction).merge(stations[['station_id', 'name']], on='station_id', validate='one_to_one')
        left, right = st.columns([1.25, 1])
        with left:
            show_plot(c.station_map(stations, ranking, selected, title=f'站点地理图 · {a.FLOW_NAMES[direction]}'), 'station_map')
            st.caption('使用发布方经纬度及邻接关系绘制，无在线底图；连线不代表精确轨道。坐标参考系未由发布方声明。')
        with right:
            top = ranking.head(20).sort_values('value')
            fig = c.bar(top, 'value', 'name', title='日均客流前20站', orientation='h')
            fig.update_layout(height=535, yaxis_title=None, xaxis_title='日均人次')
            show_plot(fig, 'station_ranking')
        top = ranking.iloc[0]
        insight(f'当前范围中，{top["name"]}（{int(top.station_id)}）日均{top.value:,.0f}人次，排名第1。排名统一使用{int(top.days)}个有效日期；站点规模不能直接推断列车满载或拥挤程度。')
        table_export(ranking, 'station_ranking_data')

elif page == '出行模式':
    mode = st.segmented_control('模式视图', ['进出方向', '出行构成', '站点聚类'], default='进出方向', key='mode', selection_mode='single')
    # 控件回调后重跑，侧栏依当前模式正确禁用不适用筛选。
    if (mode == '站点聚类') != cluster_view:
        st.rerun()
    if mode == '进出方向':
        profile = h.groupby(['date', 'hour'])[['inFlow', 'outFlow']].sum().groupby('hour').mean().reset_index()
        long = profile.melt('hour', var_name='方向', value_name='value'); long['方向'] = long['方向'].map(a.FLOW_NAMES)
        context = f'{dates[0]} — {dates[1]} · {day_type} · {scope} · 进出人次'
        show_plot(c.line(long, 'hour', 'value', '方向', '进站与出站的小时曲线'), 'direction_curves')
        peaks = a.peak_direction(h).merge(stations[['station_id', 'name']], on='station_id')
        shown = peaks if selected else peaks[peaks.station_id.isin(a.station_ranking(d).head(10).station_id)]
        fig = c.bar(shown, 'name', '方向指数', '时段', '早晚进出方向 · 默认显示繁忙前10站', barmode='group')
        fig.update_yaxes(range=[-1, 1]); fig.update_xaxes(title=None)
        show_plot(fig, 'direction_index')
        insight('方向指数＝（进站−出站）÷（进站+出站）。正值偏进站，负值偏出站；早峰07:00–09:00，晚峰17:00–19:00。该指标不用于判断周边土地用途。')
        table_export(peaks, 'direction_data')
    elif mode == '出行构成':
        chosen = st.radio('构成方向', ['进站', '出站'], horizontal=True)
        field = 'inFlow' if chosen == '进站' else 'outFlow'
        context = f'{dates[0]} — {dates[1]} · {day_type} · {scope} · {chosen}人次'
        comp = a.trip_composition(h, field)
        left, right = st.columns(2)
        with left:
            show_plot(c.bar(comp, '出行类型', '人次', '出行类型', '三类出行的绝对规模'), 'trip_counts')
        with right:
            comp['统计范围'] = '当前范围'
            fig = c.bar(comp, '统计范围', '占比', '出行类型', '三类出行的构成比例', barmode='stack')
            fig.update_yaxes(tickformat='.0%', range=[0,1]); show_plot(fig, 'trip_proportions')
        suffix = field
        type_cols = [p + suffix for p in a.TYPE_NAMES]
        series = h.groupby(['date','hour'])[type_cols].sum().groupby('hour').mean().reset_index()
        long = series.melt('hour', var_name='出行类型', value_name='value')
        long['出行类型'] = long['出行类型'].map({p+suffix:v for p,v in a.TYPE_NAMES.items()})
        show_plot(c.line(long,'hour','value','出行类型','各类出行的小时日均'), 'trip_hourly')
        top = comp.loc[comp['占比'].idxmax()] if comp['占比'].notna().any() else None
        insight(f'{chosen}数据中，'+(f'{top["出行类型"]}占比最高，为{top["占比"]:.1%}。' if top is not None else '总量为0，无法计算占比。')+'C/HBO/NHB为发布方推断类别，本项目未重新训练分类模型。')
        table_export(comp, 'trip_composition')
    elif mode == '站点聚类':
        try:
            labels = pd.read_csv(DATA/'clusters/labels.csv')
            profiles = pd.read_csv(DATA/'clusters/profiles.csv')
            evaluation = pd.read_csv(DATA/'clusters/evaluation.csv')
            meta = json.loads((DATA/'clusters/说明.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            st.error(f'聚类结果不可用，请在开发机重新准备数据：{error}'); st.stop()
        context = '2017-05-01 — 2017-08-31 · 固定分组 · 排除六个缺损日'
        left, middle, right = st.columns(3)
        left.metric('站点分组', f'{meta["groups"]} 组'); middle.metric('轮廓系数', f'{meta["silhouette"]:.3f}'); right.metric('参与站点', meta['stations'])
        group = st.selectbox('查看分组', sorted(labels.cluster.unique()), format_func=lambda x:f'第{x}组')
        chosen_ids = labels.loc[labels.cluster.eq(group)].sort_values('center_distance').station_id.tolist()
        left, right = st.columns([1.1,1])
        with left:
            show_plot(c.station_map(stations, labels, selected, True, '相似曲线站点的空间分组'), 'cluster_map')
        with right:
            p = profiles[profiles.cluster.eq(group)].copy()
            p['曲线'] = p.is_workday.map(a.DAY_NAMES) + ' · ' + p.direction.map(a.FLOW_NAMES)
            fig = c.line(p,'hour','proportion','曲线',f'第{group}组的平均曲线')
            fig.update_yaxes(tickformat='.0%'); show_plot(fig, 'cluster_profiles')
            st.caption(f'本组 {len(chosen_ids)} 站。最接近组平均曲线的代表站：'+ '、'.join(names[x] for x in chosen_ids[:8]) + (' 等' if len(chosen_ids)>8 else ''))
        show_plot(c.bar(evaluation,'groups','silhouette',title='候选组数的轮廓系数'), 'cluster_evaluation')
        insight('以工作日、非工作日的进出站小时占比聚类。比较2—5组后，采用轮廓系数最高的组数；该分数不代表预测能力。')
        counts = labels.groupby('cluster').size().rename('站点数').reset_index()
        st.dataframe(counts.rename(columns={'cluster':'分组'}),hide_index=True)
        table_export(labels.drop(columns=['center_distance']).merge(stations[['station_id','name']],on='station_id'), 'cluster_members')
        table_export(evaluation, 'cluster_scores')

elif page == '天气关联':
    joined, stats = a.weather_analysis(n, tables['weather_daily'])
    if joined.empty:
        st.warning('当前范围没有同时具备完整天气与有效客流的日期。'); st.stop()
    left, right = st.columns(2)
    with left:
        fig = c.style(px.scatter(joined,x='temperature_2m',y='inFlow',color='日类型',color_discrete_sequence=c.COLORS,
            hover_data=['date'],labels=c.LABELS), '温度与全网日进站量')
        show_plot(fig,'weather_temperature')
    with right:
        fig = c.style(px.scatter(joined,x='rain',y='inFlow',color='日类型',color_discrete_sequence=c.COLORS,
            hover_data=['date'],labels=c.LABELS), '雨量与全网日进站量')
        show_plot(fig,'weather_rain')
    fig = c.style(px.box(joined,x='日类型',y='inFlow',color='降雨情况',points='all',labels=c.LABELS,color_discrete_sequence=c.COLORS), '同类日期的有雨与无雨比较')
    show_plot(fig,'weather_comparison')
    st.dataframe(stats,hide_index=True,width='stretch')
    insight(f'共有{len(joined)}个日期同时具备客流和天气数据。相关方向不等于因果；月份、节假日等因素也会影响客流。')
    st.caption('天气取城市代表点（31.2222°N，121.4581°E）。按日期类型计算 Spearman 相关；样本不足或变量恒定时不计算。')
    table_export(stats,'weather_correlations'); table_export(joined,'weather_daily')

elif page == 'POI与客流':
    poi = tables['poi_stations']
    quality = tables['poi_quality']
    linked, correlations, density_comparison, composition = a.poi_flow_analysis(poi, d, direction)
    rho = correlations.iloc[0]
    median_poi = linked.poi_count_1000m.median()
    columns = st.columns(4)
    values = [f'{quality["raw_rows"] / 10000:,.1f} 万', f'{quality["functional_rows"] / 10000:,.1f} 万',
              f'{median_poi:,.0f}', f'{rho["Spearman相关系数"]:.3f}']
    labels = ['原始 POI', '用于功能分析', '站点圈 POI 中位数', '密度—客流相关']
    for column, label, value in zip(columns, labels, values):
        column.metric(label, value)

    left, right = st.columns([1.15, 1])
    with left:
        scatter_data = linked[linked.poi_count_1000m.gt(0)]
        scatter = px.scatter(scatter_data, x='poi_count_1000m', y='flow', color='dominant_group', size='diversity',
            hover_name='name', hover_data={'station_id': True, 'poi_count_1000m': ':,', 'flow': ':,.0f',
                                           'diversity': ':.3f', 'dominant_group': True},
            labels={'poi_count_1000m': '1公里功能POI数', 'flow': f'站点日均{a.FLOW_NAMES[direction]}人次',
                    'dominant_group': '主要功能组', 'diversity': '功能多样性'},
            color_discrete_sequence=c.COLORS)
        scatter.update_xaxes(type='log'); scatter.update_yaxes(type='log')
        show_plot(c.style(scatter, '设施密度与客流规模', 535), 'poi_flow_scatter')
        st.caption('横纵轴采用对数刻度，圆点大小表示功能多样性。相关系数按302个站点计算；上海市POI不覆盖位于昆山的花桥、光明路两站，散点图不绘制其零值。')
    with right:
        poi_map = linked[['station_id', 'poi_count_1000m']].rename(columns={'poi_count_1000m': 'value'})
        show_plot(c.station_map(stations, poi_map, title='1公里站点圈功能POI分布', value_label='POI数'), 'poi_station_map')
        st.caption('站点圈允许重叠，同一POI可能进入相邻站点的统计；地图用于比较站点，不可跨站相加。')

    lower = density_comparison.iloc[0]
    upper = density_comparison.iloc[-1]
    interval = f'{rho["95%区间下限"]:.3f}～{rho["95%区间上限"]:.3f}'
    ratio = upper['客流中位数'] / lower['客流中位数'] if lower['客流中位数'] else np.nan
    insight(f'1公里功能POI数与站点日均{a.FLOW_NAMES[direction]}客流的Spearman相关系数为{rho["Spearman相关系数"]:.3f}，重复抽样95%区间为{interval}。高密度组的客流中位数约为低密度组的{ratio:.2f}倍；这是同向关系，不表示POI增加会直接导致客流增长。')

    left, right = st.columns(2)
    with left:
        comparison_fig = px.bar(density_comparison, x='density_group', y='客流中位数',
            category_orders={'density_group': ['低密度', '中低密度', '中高密度', '高密度']},
            labels={'density_group': '1公里POI密度分组', '客流中位数': f'站点日均{a.FLOW_NAMES[direction]}人次'},
            color='density_group', color_discrete_sequence=c.COLORS)
        show_plot(c.style(comparison_fig, '按POI密度四等分比较客流'), 'poi_density_groups')
    with right:
        difference = composition[['功能组', '占比差']].drop_duplicates().sort_values('占比差')
        difference['方向'] = np.where(difference['占比差'].ge(0), '客流前25%更高', '客流后25%更高')
        difference_fig = px.bar(difference, x='占比差', y='功能组', orientation='h',
            color='方向', labels={'占比差': '两组POI构成占比差'}, color_discrete_sequence=[c.COLORS[0], c.COLORS[1]])
        difference_fig.update_xaxes(tickformat='.1%'); difference_fig.add_vline(x=0, line_color='#8799A3', line_width=1)
        show_plot(c.style(difference_fig, '高低客流站的周边功能差异'), 'poi_composition_difference')
        st.caption('正值表示该功能在客流前25%站点周边占比更高；比较的是构成比例，不受POI总量直接影响。')

    st.subheader('单站结构与偏离站点')
    focus = st.selectbox('查看一个站点', linked.sort_values('flow', ascending=False).station_id,
                         format_func=lambda x: f'{names[x]} · {x}', key='poi_focus_station')
    station = linked.loc[linked.station_id.eq(focus)].iloc[0]
    group_columns = [column for column in linked if column.startswith('group_')]
    station_groups = pd.DataFrame({'功能组': [x.removeprefix('group_') for x in group_columns],
                                   'POI数': station[group_columns].to_numpy(int)})
    station_groups['占比'] = station_groups['POI数'] / station_groups['POI数'].sum()
    left, right = st.columns([1, 1.3])
    with left:
        station_fig = px.bar(station_groups.sort_values('占比'), x='占比', y='功能组', orientation='h',
                             color='功能组', color_discrete_sequence=c.COLORS)
        station_fig.update_xaxes(tickformat='.0%')
        show_plot(c.style(station_fig, f'{station["name"]} · 1公里功能构成'), 'poi_station_composition')
    with right:
        high = linked.nlargest(5, 'rank_gap').assign(偏离方向='客流排名高于POI排名')
        low = linked.nsmallest(5, 'rank_gap').assign(偏离方向='POI排名高于客流排名')
        outliers = pd.concat([high, low], ignore_index=True)
        st.dataframe(outliers[['name', 'station_id', '偏离方向', 'flow', 'poi_count_1000m', 'diversity', 'rank_gap']]
            .rename(columns={'name': '站名', 'station_id': '站点ID', 'flow': f'日均{a.FLOW_NAMES[direction]}人次',
                             'poi_count_1000m': '1公里POI数', 'diversity': '多样性', 'rank_gap': '百分位差'}),
            hide_index=True, width='stretch')
        st.caption('百分位差用于发现“客流规模与周边设施密度不一致”的站点，可能与换乘、线路位置、枢纽功能或数据覆盖有关。')
    table_export(linked, 'poi_station_analysis')
    table_export(correlations, 'poi_correlations')
    table_export(density_comparison, 'poi_density_comparison')
    table_export(composition, 'poi_composition_comparison')

    with st.expander('数据质量与计算口径'):
        st.write(f'原始{quality["raw_rows"]:,}行；按“名称、地址、坐标、细分类”移除候选重复{quality["candidate_duplicates_removed"]:,}行。'
                 f'电话字段缺失{quality["missing_cells"]["TELEPHONE"]:,}行，但不参与分析；一级类型和坐标没有缺失。')
        st.write(f'剔除仅作地图标注的{len(quality["excluded_base_types"])}类一级类型后，保留{quality["functional_rows"]:,}个功能POI。'
                 '多样性采用归一化Shannon指数，范围0—1，越高表示九类功能越均衡。')
        st.write(f'站点坐标转换前，与最近“地铁站”POI的中位距离为{quality["median_nearest_subway_m_before_conversion"]:,.1f}米；'
                 f'统一坐标后为{quality["median_nearest_subway_m_after_conversion"]:,.1f}米，'
                 f'{quality["stations_within_300m_after_conversion"]}/{quality["station_count"]}个站在300米内匹配到地铁站POI。')
        st.caption('POI为2017年静态快照，客流为2017年5—8月。站点圈采用直线距离，不代表实际步行路径；相关和分组比较均不能证明因果。')

else:
    q = tables['quality']
    cols = st.columns(4)
    for col,label,value in zip(cols,['原始记录 / 行','原始字段 / 个','有效日期 / 天','计数缺损日 / 天'],
                               [f'{q["raw_rows"]:,}',q['columns'],q['valid_days'],len(q['excluded_days'])]): col.metric(label,value)
    checks = pd.DataFrame({'检查项':['缺失单元格','完全重复记录','重复键冲突记录','非法流量记录','分项加和不一致记录','进出均为0记录'],
        '数量':[q[x] for x in ['missing_cells','exact_duplicates_removed','conflicting_rows','invalid_count_rows','component_mismatch_rows','zero_in_out_rows']]})
    left,right=st.columns([1,1.3])
    with left:
        st.subheader('真实检查结果'); st.dataframe(checks,hide_index=True,width='stretch')
    with right:
        bad=pd.DataFrame(q['excluded_days'])
        context='2017年5—8月 · 原始质量检查 · 六个缺损日'
        show_plot(c.bar(bad,'date','inFlow',title='六个缺损日仍有残余计数'), 'quality_bad_days')
    network=tables['network_daily']
    st.write(f'原始123日日均进站：{network.inFlow.mean()/10000:,.1f}万人次；排除六日后117日日均进站：{network.loc[network.is_valid,"inFlow"].mean()/10000:,.1f}万人次。')
    insight('六个日期记录行数完整，但客流计数明显缺损。处理时保留原值、排除常规分析，不补0；正常零值和高峰不删除。')
    st.subheader('字段与数据边界')
    st.dataframe(pd.DataFrame({'字段':['date / startTime / endTime','station','inFlow / outFlow','C / HBO / NHB','isWorday','lon / lat','temperature_2m / rain'],
        '说明':['本地日期及10分钟区间，起点包含、终点不包含','302站的站点ID','聚合进出人次，不是去重人数','发布方推断：通勤 / 居家其他 / 非居家','源日历工作日标记，包含调休','发布方经纬度；坐标参考系未声明','代表点温度（°C）与小时雨量（mm）']}),hide_index=True,width='stretch')
    st.markdown('数据：[MetroFlow作者仓库](https://github.com/Ariza-Sun/MetroFlow) · [Figshare数据](https://doi.org/10.6084/m9.figshare.28844942) · [数据论文](https://doi.org/10.1038/s41597-025-05416-8)。数据采用 CC BY 4.0，展示范围为2017年5—8月。来源链接供查证，系统运行不依赖联网。')
    st.caption('开发工具：OpenAI Codex。成员：林睿信、吴旻昊、朱子墨、邢雨晨，计划分工各25%。AI过程与实际验证材料另行留档。')
    table_export(checks,'quality_checks'); table_export(bad,'quality_excluded_days')

st.divider()
st.caption('沪上流动 · 软件开发实践1　｜　2017年历史客流 · 原始数据来源 MetroFlow　｜　分析结果以当前有效数据为准')
