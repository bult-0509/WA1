"""将本地地图及依赖打包为可直接嵌入 Streamlit iframe 的 HTML。"""
import base64
import re
from pathlib import Path


def build_metro_map_html(folder: Path) -> str:
    document = (folder / 'metro_map.html').read_text(encoding='utf-8')
    leaflet = folder / 'lib' / 'leaflet'
    stylesheet = (leaflet / 'leaflet.css').read_text(encoding='utf-8')

    def inline_image(match):
        data = (leaflet / match.group(1)).read_bytes()
        return 'url(data:image/png;base64,' + base64.b64encode(data).decode('ascii') + ')'

    stylesheet = re.sub(r'url\((images/[^)]+\.png)\)', inline_image, stylesheet)
    document = document.replace('<link rel="stylesheet" href="lib/leaflet/leaflet.css"/>',
                                '<style>' + stylesheet + '</style>')
    for relative in ['lib/leaflet/leaflet.js', 'stations.js', 'edges.js', 'data_flow_edges.js']:
        script = (folder / relative).read_text(encoding='utf-8')
        # srcdoc 内嵌脚本不能包含可被 HTML 解析器识别的结束标签。
        script = re.sub(r'</script', r'<\\/script', script, flags=re.IGNORECASE)
        document = document.replace(f'<script src="{relative}"></script>', '<script>' + script + '</script>')
    return document
