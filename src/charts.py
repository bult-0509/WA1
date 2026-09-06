"""本地图表；地理站点图只依赖随包坐标及邻接关系，无在线底图。"""
import json
import math
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

COLORS = ['#167D8D', '#E48B54', '#5374BA', '#925EA1', '#619778']
LABELS = {'date': '日期', 'hour': '小时', 'value': '人次', 'inFlow': '进站人次',
          'outFlow': '出站人次', 'temperature_2m': '日均温度（°C）', 'rain': '日雨量（mm）',
          'proportion': '全天进出占比', 'groups': '分组数', 'silhouette': '轮廓系数'}
CONFIG = {'displaylogo': False, 'scrollZoom': False, 'displayModeBar': 'hover',
          'toImageButtonOptions': {'format': 'png', 'filename': '地铁客流分析', 'scale': 2},
          'modeBarButtonsToRemove': ['lasso2d', 'select2d']}


def style(fig, title, height=410, subtitle=''):
    fig.update_layout(template='plotly_white', title={'text': title + (f'<br><sup>{subtitle}</sup>' if subtitle else ''), 'font': {'size': 17}, 'x': .02},
                      font={'family': 'Alimama FangYuanTi VF, Microsoft YaHei, SimHei, Arial', 'color': '#243D51', 'size': 12},
                      colorway=COLORS, paper_bgcolor='white', plot_bgcolor='white', height=height,
                      margin={'t': 80 if subtitle else 60, 'b': 45, 'l': 55, 'r': 25},
                      legend={'orientation': 'h', 'y': -0.17, 'title': None},
                      hoverlabel={'bgcolor': 'white'}, separators='.,')
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor='#EDF1F4', zeroline=False)
    return fig


def line(data, x, y, color=None, title='', **kwargs):
    return style(px.line(data, x=x, y=y, color=color, labels=LABELS, color_discrete_sequence=COLORS, markers=False, **kwargs), title)


def bar(data, x, y, color=None, title='', **kwargs):
    return style(px.bar(data, x=x, y=y, color=color, labels=LABELS, color_discrete_sequence=COLORS, **kwargs), title)


def station_map(stations, values, selected=None, cluster=False, title='站点客流空间分布'):
    value_column = 'cluster' if cluster else 'value'
    f = stations.merge(values[['station_id', value_column]], on='station_id', how='left', validate='one_to_one')
    points = stations.set_index('station_id')
    xs, ys, seen = [], [], set()
    for r in stations.itertuples():
        for neighbour in json.loads(r.neighbour):
            edge = tuple(sorted((r.station_id, neighbour)))
            if edge in seen or neighbour not in points.index:
                continue
            seen.add(edge)
            xs.extend([r.lon, points.loc[neighbour, 'lon'], None])
            ys.extend([r.lat, points.loc[neighbour, 'lat'], None])
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode='lines', line={'color': '#D9E2E8', 'width': 1}, hoverinfo='skip', showlegend=False))
    if cluster:
        groups = f.dropna(subset=['cluster']).groupby('cluster')
        for i, (group, sub) in enumerate(groups):
            fig.add_trace(go.Scatter(x=sub.lon, y=sub.lat, mode='markers', name=f'第{int(group)}组',
                marker={'color': COLORS[i % len(COLORS)], 'size': 8, 'line': {'width': .6, 'color': 'white'}},
                customdata=np.column_stack([sub.name, sub.station_id]), hovertemplate='%{customdata[0]} · %{customdata[1]}<extra>%{fullData.name}</extra>'))
    else:
        sub = f.dropna(subset=['value'])
        maximum = max(float(sub.value.max()) if len(sub) else 0, 1)
        fig.add_trace(go.Scatter(x=sub.lon, y=sub.lat, mode='markers', showlegend=False,
            marker={'size': 5 + 17 * np.sqrt(sub.value / maximum), 'color': sub.value,
                    'colorscale': [[0, '#BCDCD8'], [.4, '#5AADA5'], [1, '#12545D']], 'showscale': True,
                    'colorbar': {'title': '日均人次', 'thickness': 12}, 'line': {'width': .7, 'color': 'white'}},
            customdata=np.column_stack([sub.name, sub.station_id, sub.value]),
            hovertemplate='%{customdata[0]} · %{customdata[1]}<br>日均 %{customdata[2]:,.0f} 人次<extra></extra>'))
    if selected:
        highlight = f[f.station_id.isin(selected)]
        fig.add_trace(go.Scatter(x=highlight.lon, y=highlight.lat, mode='markers',
                      marker={'size': 17, 'color': '#E48B54', 'symbol': 'circle-open', 'line': {'width': 2}},
                      name='所选站点', text=highlight.name, hovertemplate='%{text}<extra></extra>'))
    style(fig, title, 535)
    fig.update_xaxes(title='经度', tickformat='.2f')
    fig.update_yaxes(title='纬度', scaleanchor='x', scaleratio=1 / math.cos(math.radians(31.2)), tickformat='.2f')
    return fig
