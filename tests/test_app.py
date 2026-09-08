"""用Streamlit实际执行各页及关键筛选；浏览器视觉检查另行进行。"""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'

class AppPages(unittest.TestCase):
    def test_pages_and_modes(self):
        # 本版本AppTest不支持连续序列化单选segmented_control；每页从独立状态启动。
        # 真实页面之间的切换与标签点击另在浏览器验证。
        for page in ['时间规律','站点空间','动态客流地图','出行模式','天气关联','数据质量与说明','项目概览']:
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

    def test_station_and_empty_filter(self):
        from datetime import date
        app=AppTest.from_file(str(APP),default_timeout=60).run()
        app.multiselect(key='stations').set_value([112]).run()
        self.assertFalse(list(app.exception))
        app.date_input(key='dates').set_value((date(2017,5,4),date(2017,5,4))).run()
        self.assertFalse(list(app.exception));self.assertGreater(len(app.warning),0)

    def test_dynamic_map_ignores_analysis_filters(self):
        from datetime import date
        app = AppTest.from_file(str(APP), default_timeout=60)
        app.session_state['page'] = '动态客流地图'
        app.session_state['dates'] = (date(2017, 5, 4),)
        app.session_state['stations'] = [112]
        app.run()
        self.assertFalse(list(app.exception))
        self.assertFalse(list(app.error))
        self.assertEqual(len(app.get('iframe')), 1)
        self.assertEqual(len(app.date_input), 0)

    def test_dynamic_map_embeds_local_assets(self):
        from src.metro_map import build_metro_map_html
        document = build_metro_map_html(APP.parent / 'my-folder')
        self.assertNotIn('<script src=', document)
        self.assertNotIn('href="lib/', document)
        self.assertNotIn('url(images/', document)
        self.assertIn('data:image/png;base64,', document)
        self.assertIn('var EDGE_FLOW', document)

if __name__=='__main__':unittest.main()
