# 沪上流动：上海地铁客流时空规律分析与可视化系统

软件开发实践1，第1题。使用MetroFlow公开聚合数据，分析2017年5—8月上海302站的时间高峰、繁忙站点、早晚进出、出行类别及天气关联，另用KMeans对站点曲线分组。

## 最快开始：便携演示包

GitHub仓库：[bult-0509/WA1](https://github.com/bult-0509/WA1)。免安装演示包见[项目 Releases](https://github.com/bult-0509/WA1/releases)，选择 `WA1-Windows-portable.zip`。GitHub的“Download ZIP”只下载源码，不含Python运行环境。

1. 将“便携演示包.zip”完整解压到Windows本地文件夹，支持中文及空格路径。
2. 双击“启动.vbs”或“启动.cmd”。无需安装Python，无需联网，无需管理员权限。
3. 浏览器打开 `http://127.0.0.1:8501`；如未自动打开，手动输入此地址。
4. 保持启动提示窗口打开，使用侧栏切换页面和筛选。
5. 演示结束，在启动提示窗口点击“确定”，关闭本系统服务。

目标系统：Windows 10/11 64位，推荐8GB及以上内存、现代浏览器。异机实测状态见`docs/测试与验收记录.md`，开发机通过不等于另一台电脑已通过。

## 六个页面与操作

| 页面 | 内容与操作 |
|---|---|
| 项目概览 | 总量、日均、有效日期、站点数、每日趋势和两类日期曲线 |
| 时间规律 | 小时日均与日期热力图，比较工作日和非工作日 |
| 站点空间 | 地理站点图和前20站日均排名；悬停站点查看数值 |
| 出行模式 | 进出方向、出行构成、站点聚类三个视图 |
| 天气关联 | 温度/雨量散点、雨日比较、相关系数及样本数 |
| 数据质量与说明 | 来源、字段、真实检查结果、六个缺损日和处理前后对比 |

日期范围、日期类型和站点筛选即时生效；站点留空表示全部。空间页还可看进出总量。天气固定用全网进站量，聚类固定用四个月有效数据，不适用控件会禁用并说明。

每张图右上角相机按钮下载PNG，鼠标移入图表后可见；图下“查看数据并导出CSV”展开明细后下载表格。文件包含范围说明，CSV使用UTF-8 BOM，Excel可直接打开。数据单位是人次，不能当成去重人数。

## 开发环境与依赖

- Python **3.13.15**，Windows x64；开发工具为OpenAI Codex桌面应用及其终端。
- Streamlit 1.49.1、pandas 2.3.2、NumPy 2.3.2、SciPy 1.16.1、scikit-learn 1.7.1、Plotly 6.3.0、PyArrow 21.0.0、Matplotlib 3.10.6。
- `requirements.txt`保存本次运行验证的完整依赖版本。

在已安装Python 3.13.15的开发机，项目目录中执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

源码包自带处理后数据，可直接运行六页系统；只有重新清洗数据才需要原始文件。

GitHub仓库同时保留`docs/deliverables/`中的期末报告、答辩PPT、四份个人调研及AI过程附件。原始聊天记录、聊天截图、原始大数据和本地运行环境不进入Git历史。文档中的完整留档路径是本地交付材料路径，公开仓库不包含全部原始对话证据。

## 数据准备与重新计算

数据源：[MetroFlow作者仓库](https://github.com/Ariza-Sun/MetroFlow)、[Figshare正式数据](https://doi.org/10.6084/m9.figshare.28844942)，许可CC BY 4.0。论文：Sun等（2025），[Human mobility datasets in the complex metro system of shanghai](https://doi.org/10.1038/s41597-025-05416-8)。

按`docs/数据来源与准备.md`将四个原始CSV放到`data/raw/`后执行：

```powershell
.venv\Scripts\python.exe prepare_data.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

原始进出表3,788,892行、13列、217,442,845字节。六个计数缺损日保留原值，排除常规统计和聚类：2017-05-04、05-08、05-09、06-16、06-27、06-28。其余117日参与分析。零值不会被一概删除，高峰不会因数值大就被裁剪。

地图使用发布方坐标和邻接关系，无在线底图；坐标参考系未声明，连线不是精确轨道。天气为城市代表点，不是逐站观测；相关不证明因果。三类出行由发布方推断。聚类评价是现有数据的内部评价，不能当作预测准确率。

## 重新制作便携包

开发机从[Python官方发布页](https://www.python.org/downloads/release/python-31315/)取得Windows 64位embeddable ZIP，解压至项目根目录`.runtime/`。用完整Python 3.13开发环境安装随包依赖：

```powershell
python -m pip install --target .runtime/Lib/site-packages -r requirements.txt
```

将`.runtime/python313._pth`写为下列相对路径（其中`..`指项目根目录）：

```text
python313.zip
.
Lib/site-packages
..
import site
```

然后执行：

```powershell
.runtime\python.exe -X utf8 -m unittest discover -s tests -v
.runtime\python.exe -X utf8 build_portable.py
```

`dist/代码.zip`含README、源码、小型处理后数据，必须≤30,000,000字节；`dist/便携演示包.zip`另含Python和依赖，体积不受这一代码包限制。打包脚本不把原始大CSV、开发缓存或完整AI对话装入代码包。第三方依赖及Python的许可随运行环境保留。

## 目录

```text
app.py                 六页界面、筛选和导出
prepare_data.py        数据准备与聚类入口
build_portable.py      双包构建
launch.py              简单本地启动与关闭
src/                   数据处理、统计、聚类、图表
data/raw/              原始CSV（不进交付包）
data/processed/        小时/日汇总、辅助数据、分组结果
assets/                本地图标等
tests/                 统计、质量和页面检查
docs/                  来源、需求、AI记录、截图和课程材料
dist/                  构建后的交付包
```

## 常见问题

- **启动没反应**：确认完整解压；不能在ZIP窗口中直接双击。可改用启动.cmd。
- **端口占用**：先检查是否已打开本系统；使用原窗口，或关闭原系统的启动提示后再启动。不会自动关闭其他程序。
- **浏览器未打开**：手动打开本地地址，保持启动提示窗口开启。
- **缺数据或无法读取**：重新完整解压；开发机按准备说明运行prepare_data.py，答辩机不现场下载。
- **筛选后空白**：仅选择六个异常日会显示无有效数据提示，扩大日期范围即可。
- **中文路径或字体**：路径按文件所在位置计算，支持中文和空格；图表优先使用Windows微软雅黑。图中源站名保留发布方英文名称及ID。
- **导出CSV乱码**：用Excel直接打开带BOM的导出文件，或明确选择UTF-8编码。
- **怎样停止**：关闭浏览器标签不会关闭服务；点击启动提示窗口的“确定”。
- **运行错误**：查看“运行记录/运行.log”；目录不可写时写入当前用户的LocalAppData/MetroFlow。

## 团队与交付

上午班[01]；林睿信（组长）、吴旻昊、朱子墨、邢雨晨，计划工作量各25%，学号待补。成员实际参与以AI过程和核验记录为准。

邮件及总包名：`[01]林睿信_吴旻昊_朱子墨_邢雨晨_地铁`。课程截止为2026年9月8日23:00前，收件地址jfyh2010@qq.com。运行成功不等于材料已提交，发送需用户另行授权。
