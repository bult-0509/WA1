import fs from 'node:fs/promises';
import path from 'node:path';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const root=path.resolve(import.meta.dirname,'../..');
const out=path.join(root,'.work/artifacts/slides');await fs.mkdir(out,{recursive:true});
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={ink:'#123442',teal:'#187887',orange:'#D38A55',muted:'#536C77',bg:'#F6F8FA',white:'#FFFFFF'};
const DATA='本项目按MetroFlow公开数据计算，2017-05-01至08-31，302站、117个有效日期。';
const SOURCE='https://doi.org/10.1038/s41597-025-05416-8\nhttps://doi.org/10.6084/m9.figshare.28844942';
function text(s,str,x,y,w,h,size=28,color=C.ink,bold=false){const a=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0,style:'solid'}});a.text=str;a.text.style={fontSize:size,bold,color,typeface:'Microsoft YaHei',wrap:'word',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};return a;}
function slide(title,sub=''){const s=p.slides.add();s.background.fill=C.bg;const n=p.slides.items.length;text(s,'沪上流动  /  软件开发实践1',60,28,900,28,18,C.teal,true);text(s,String(n).padStart(2,'0'),1150,28,70,28,18,C.muted);text(s,title,60,87,1160,78,48,C.ink,true);if(sub)text(s,sub,60,172,1160,48,24,C.muted);return s;}
function notes(s,str,sources=SOURCE){s.speakerNotes.textFrame.setText(str+'\n\n[Sources]\n'+sources+'\n[/Sources]');}
async function shot(s,file,x=60,y=240,w=755,h=430){s.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'docs/screenshots',file))),contentType:'image/png',alt:'本项目实际运行截图：'+file,fit:'contain',position:{left:x,top:y,width:w,height:h}});}
function points(s,arr,x=870,y=270,w=345,size=26,gap=110){arr.forEach((v,i)=>text(s,v,x,y+i*gap,w,gap-15,size,i===0?C.teal:C.ink,i===0));}
function chart(s,type,categories,values,name,pos,extra={}){return s.charts.add(type,{position:pos,categories,series:[{name,values,fill:C.teal,line:{fill:C.teal,width:3}}],hasLegend:false,chartFill:C.bg,plotAreaFill:C.bg,xAxis:{textStyle:{fontSize:20,color:C.muted}},yAxis:{textStyle:{fontSize:18,color:C.muted},majorGridlines:{fill:'#DFE6EA',width:1,style:'solid'}},dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:22,color:C.ink}},...extra});}

// 01：留白和清楚的课题身份，不添加与项目无关的装饰图。
{
const s=p.slides.add();s.background.fill=C.ink;
text(s,'软件开发实践1 · 选题1',60,60,1000,35,24,'#9ACDCD');
text(s,'沪上流动',60,193,1100,105,76,C.white,true);
text(s,'上海地铁客流时空规律分析与可视化',60,321,1140,70,40,C.white);
text(s,'2017年5—8月  /  302站  /  本地离线交互',60,430,1100,45,28,'#B7D0D6');
text(s,'[01] 林睿信 · 吴旻昊 · 朱子墨 · 邢雨晨',60,610,1100,40,25,C.white);
notes(s,'约25秒。介绍项目题目与范围。说明使用公开历史聚合客流，目标是可解释的分析和稳定的离线演示。');
}
{
const s=slide('五个问题决定功能范围','每个页面都要回答问题，并给出可核验的结果。');
['A  高峰何时出现？','B  哪些站点更繁忙，在哪里？','C  早晚进出方向如何变化？','D  三类出行各占多少？','E  天气与客流是否有关？'].forEach((v,i)=>text(s,v,72,260+i*74,950,55,34,i%2?C.ink:C.teal,true));
notes(s,'约30秒。课程硬要求包括预处理、描述性统计、客流规律、出行模式和地图。KMeans为本组已选择增强，课程原文没有强制预测。用户确定范围；这里没有加入爬虫、OD和复杂模型。','本地课程文件：软件开发实践1-项目要求【2026.9】.docx\n本地规格：docs/requirements/需求冻结版项目规格.md');
}
{
const s=slide('378万行聚合记录，正常分析117天','行数、客流人次与独立乘客人数是不同的统计对象。');
text(s,'3,788,892',70,270,750,100,78,C.teal,true);text(s,'原始记录 / 13个字段',72,385,750,55,32);
text(s,'123天 → 排除6个计数缺损日 → 117天',70,492,1110,55,35,C.ink,true);
text(s,'零流量保留；不把缺损日填成“正常低谷”。',70,587,1100,45,29,C.muted);
notes(s,'约40秒。原始CSV为10分钟站点汇总，正常统计前检查类型、唯一键、分项和、站点与时段完整性。六个缺损日仍保留在质量页面，不是把它们删除后隐藏。处理后小时表631482行，约8.4MB结果可供演示。'+DATA);
}
{
const s=slide('把数据处理和页面展示分开','四个小模块支撑六个页面，便于复核和答辩解释。');
text(s,'公开数据 → 检查与标记 → 小时/日聚合',70,270,1140,62,39,C.teal,true);
text(s,'统计与聚类 → 本地加载 → 筛选、解释与导出',70,375,1140,62,37,C.ink,true);
text(s,'Python 3.13.15  ·  pandas  ·  Streamlit  ·  Plotly  ·  scikit-learn',70,505,1140,60,27,C.muted);
text(s,'离线地理图；运行时不请求在线地图或API。',70,605,1140,42,28,C.ink);
notes(s,'约30秒。数据处理、分析、聚类和绘图各有模块；app.py只组织页面，启动器管理自己的服务。技术版本详见requirements.txt，不在界面暴露随机种子等开发参数。','本地源码：src/、app.py、launch.py、requirements.txt');
}
{
const s=slide('工作日更集中，非工作日高峰更晚','有效工作日81天；非工作日36天。');
chart(s,'bar',['工作日','非工作日'],[699.3,451.0],'日均进站 / 万人次',{left:65,top:250,width:710,height:390});
points(s,['日均进站量（万人次）','工作日峰值：08—09时\n平均96.7万人次','非工作日峰值：17—18时\n平均34.4万人次'],850,260,355,27,127);
notes(s,'约40秒。先区分工作日与非工作日，再比较典型小时曲线。调休以来源日历为准。全网日均622.9万人次，峰值日期5月19日。这里的人次不是独立乘客数量。'+DATA);
}
{
const s=slide('排名回答“多不多”，地图回答“在哪里”','同一有效日期集合下比较站点日均进站量。');
await shot(s,'S03-stations.png');points(s,["People's Square\n15.38万人次/日",'Xujiahui\n10.21万人次/日',"Jing'an Temple\n10.16万人次/日"],860,260,350,28,123);
notes(s,'约35秒。图为真实站点空间页面。英文站名沿用数据源。地图坐标是地理位置，邻接连线不是轨道精确走向；不能据此推断OD和换乘人数。'+DATA,'本地实际截图：docs/screenshots/S03-stations.png\n'+SOURCE);
}
{
const s=slide('出行构成与方向，应放在一起解释','C/HBO/NHB为发布方推断类别，本组没有重新训练分类器。');
chart(s,'bar',['通勤 C','居家其他 HBO','非居家 NHB'],[32.03,29.51,38.46],'进站构成 / %',{left:65,top:260,width:740,height:375});
text(s,'进站构成 / %',65,226,710,34,22,C.muted);
points(s,['非居家占比最高\n38.46%','早晚方向指数\n(进−出)/(进+出)','先合计人次再算比例\n不直接平均每行比例'],855,270,360,26,117);
notes(s,'约40秒。三类绝对进站量分别233455300、215063027、280295483；总和等于有效进站量。方向指数正值表示进站更多，零分母不算；峰段使用左闭右开7—9和17—19时。'+DATA);
}
{
const s=slide('天气存在负向关联，但不能解释为因果','同类日期分别比较，避免把工作日差异混进天气结论。');
await shot(s,'S07-weather.png');points(s,['工作日：81天\n温度 −0.490 / 雨量 −0.226','非工作日：36天\n温度 −0.505 / 雨量 −0.451','Spearman相关\n单个城市代表点'],850,258,368,25,130);
notes(s,'约35秒。天气按日汇总，温度取均值，降雨求和，要求24小时完整。负相关不能说明因果，月份、节假日等还可能影响结果。'+DATA,'本地实际截图：docs/screenshots/S07-weather.png\n'+SOURCE);
}
{
const s=slide('相对曲线聚成2组，内部评价为0.427','初始参照为3组；统一比较2—5组后选择最高轮廓系数。');
chart(s,'bar',['2组','3组','4组','5组'],[0.427,0.299,0.260,0.205],'轮廓系数',{left:65,top:250,width:730,height:385},{yAxis:{numberFormatCode:'0.0',textStyle:{fontSize:18,color:C.muted},majorGridlines:{fill:'#DFE6EA',width:1,style:'solid'}},series:[{name:'轮廓系数',values:[0.427,0.299,0.260,0.205],valuesFormatCode:'0.000',fill:C.teal,dataLabelOverrides:[0.427,0.299,0.260,0.205].map((v,idx)=>({idx,text:v.toFixed(3),showValue:false,textStyle:{fontSize:22,color:C.ink}}))}]});
points(s,['175站 / 127站','输入：两类日期 ×\n17小时 × 进出 = 68项','评价已有数据的结构\n不代表预测准确率'],850,270,368,28,112);
notes(s,'约45秒。每种日类型的进出34项先归一化，减少规模对分组的主导；分组1呈工作日早进晚出突出。没有土地利用外部标签，不直接命名住宅区。固定seed42、n_init10仅帮助复现，无需在用户界面调参。'+DATA,'本地结果：data/processed/clusters/evaluation.csv、说明.json\nhttps://scikit-learn.org/stable/modules/clustering.html\n'+SOURCE);
}
{
const s=slide('一次演示：筛选、定位、解释、导出','六页系统共用清楚的统计口径。');
await shot(s,'S01-overview.png');points(s,['概览 → 时间 → 站点','出行模式 → 天气 → 质量','CSV保留筛选条件\nPNG保留图题与范围'],850,270,360,28,125);
notes(s,'预留约60秒现场演示：先看时间规律，再进入站点空间选择站点，切换出行模式，最后展示质量和导出。不要在答辩时重新训练模型。若现场演示未能完成，可用本页真实截图解释，但不能声称异机已通过。','本地实际截图：docs/screenshots/S01-overview.png\n本地源码：app.py');
}
{
const s=slide('把可运行与可解释一起交付','开发验证有记录，现场验收仍要实做。');
text(s,'13项测试通过',70,265,1100,70,47,C.teal,true);
text(s,'清洗边界、统计口径、六页与模式、筛选及空状态',70,348,1120,60,30);
text(s,'源代码ZIP约8.4MB；独立便携包内置Python与数据',70,463,1120,58,30);
text(s,'仍需：另一台Windows电脑断网测试、学号补齐、材料核验',70,585,1120,60,29,C.muted);
notes(s,'约35秒。说明已完成的开发测试，避免把中文空格目录测试说成真实异机。代码ZIP小于30MB，运行环境单独打包。源代码、报告、PPT、个人调研和AI附件均在总包。','本地证据：docs/测试与验收记录.md、docs/ai-process/最终自动化测试.log、dist/包大小.json');
}
{
const s=slide('结论有依据，边界也要讲清楚','从公开历史数据出发，完成可复现的本科分析系统。');
text(s,'成果',70,265,220,55,35,C.teal,true);text(s,'时间与空间规律、方向与构成、天气关联、站点分组',300,265,900,88,31);
text(s,'特色',70,400,220,55,35,C.teal,true);text(s,'离线交互、共同有效日期、清楚的质量说明与AI留档',300,400,900,88,31);
text(s,'限制',70,535,220,55,35,C.teal,true);text(s,'历史样本、单点天气；聚类仍需独立时期与外部资料验证',300,535,900,100,31);
notes(s,'约30秒收尾，之后预留问答。团队计划各25%；Codex生成程序和材料，用户确定范围并指导精简。真实人工修改和验收在发生后记录，不补造贡献。可回答：为何排除六天？为何不做预测？为何选择2组？为何进站人次不等于人数？为什么双包？','本地报告：docs/deliverables/期末报告.docx\n本地AI附件：docs/deliverables/AI辅助过程附件.docx');
}
for(const [i,s] of p.slides.items.entries()){
const stem=`slide-${String(i+1).padStart(2,'0')}`;
const png=await p.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(out,stem+'.png'),new Uint8Array(await png.arrayBuffer()));
const layout=await s.export({format:'layout'});await fs.writeFile(path.join(out,stem+'.json'),await layout.text());
console.log('rendered',i+1);
}
const deck=await PresentationFile.exportPptx(p);await deck.save(path.join(root,'docs/deliverables/答辩PPT.pptx'));
console.log('PPTX saved');
