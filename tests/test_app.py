"""用Streamlit实际执行各页及关键筛选；浏览器视觉检查另行进行。"""
import json
import re
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'

class AppPages(unittest.TestCase):
    def test_pages_and_modes(self):
        # 本版本AppTest不支持连续序列化单选segmented_control；每页从独立状态启动。
        # 真实页面之间的切换与标签点击另在浏览器验证。
        for page in ['时间规律','站点空间','出行模式','天气关联','POI与客流','数据质量','项目概览']:
            app=AppTest.from_file(str(APP),default_timeout=60)
            app.session_state['page']=page
            app.run()
            self.assertFalse(list(app.exception),f'{page}: {app.exception}')
        for mode in ['出行构成','站点聚类','进出方向']:
            app=AppTest.from_file(str(APP),default_timeout=60)
            app.session_state['page']='出行模式'
            app.session_state['mode']=mode
            app.run()
            self.assertFalse(list(app.exception),f'{mode}: {app.exception}')
        app=AppTest.from_file(str(APP),default_timeout=60)
        app.session_state['page']='站点空间'
        app.session_state['space_view']='10分钟动画'
        app.run()
        self.assertFalse(list(app.exception),f'10分钟动画: {app.exception}')

    def test_station_and_empty_filter(self):
        from datetime import date
        app=AppTest.from_file(str(APP),default_timeout=60).run()
        app.multiselect(key='stations').set_value([112]).run()
        self.assertFalse(list(app.exception))
        app.date_input(key='dates').set_value((date(2017,5,4),date(2017,5,4))).run()
        self.assertFalse(list(app.exception));self.assertGreater(len(app.warning),0)

    def test_overview_shortcut(self):
        app=AppTest.from_file(str(APP),default_timeout=60).run()
        app.button(key='quick_station').click().run()
        self.assertFalse(list(app.exception))
        self.assertEqual(app.session_state['page'],'站点空间')


class MetroMapAssets(unittest.TestCase):
    def test_dynamic_map_bundle_is_offline_and_complete(self):
        base=APP.parent/'static'/'metro_map'
        required=['metro_map.html','stations.js','edges.js','data_flow_edges.js',
                  'vendor/leaflet/leaflet.css','vendor/leaflet/leaflet.js','vendor/leaflet/LICENSE']
        for relative in required:
            path=base/relative
            self.assertTrue(path.is_file(),relative)
            self.assertGreater(path.stat().st_size,0,relative)

        html=(base/'metro_map.html').read_text(encoding='utf-8')
        self.assertNotIn('http://',html)
        self.assertNotIn('https://',html)
        for reference in ['vendor/leaflet/leaflet.css','vendor/leaflet/leaflet.js',
                          'stations.js','edges.js','data_flow_edges.js']:
            self.assertIn(reference,html)

        def load_var(filename,var_name):
            text=(base/filename).read_text(encoding='utf-8')
            match=re.search(rf'var\s+{var_name}\s*=\s*(.*);\s*$',text,re.S)
            self.assertIsNotNone(match,filename)
            return json.loads(match.group(1))

        self.assertEqual(len(load_var('stations.js','STATIONS')),302)
        self.assertEqual(len(load_var('edges.js','EDGES')),349)
        edge_flow=load_var('data_flow_edges.js','EDGE_FLOW')
        self.assertEqual(len(edge_flow),12)
        self.assertEqual(set(edge_flow)-{'20170504','20170508','20170509'},
                         {'20170501','20170502','20170503','20170505','20170506',
                          '20170507','20170510','20170511','20170512'})

if __name__=='__main__':unittest.main()
