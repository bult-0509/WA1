from pathlib import Path
import json,re,zipfile
from docx import Document
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parents[2]
results=[]
for f in sorted((ROOT/'docs/deliverables').glob('*.docx')):
    d=Document(f); txt='\n'.join(p.text for p in d.paragraphs)
    assert not d._element.xpath('.//w:highlight[@w:val="yellow"]'),f
    for s in d.sections:
        assert abs(s.page_width.cm-21)<.01 and abs(s.page_height.cm-29.7)<.01
        assert abs(s.left_margin.cm-3.175)<.01
    assert all(t._tbl.tblPr.find(qn('w:tblW')).get(qn('w:w'))=='8306' for t in d.tables)
    if f.name=='期末报告.docx':
        for i in range(1,9):assert re.search(r'^'+str(i)+r' ',txt,re.M)
        assert len(d.inline_shapes)==10
        for i in range(1,11):assert len(re.findall('图'+str(i)+r'(?!\d)',txt))>=2,i
        for i in range(1,6):assert len(re.findall('表'+str(i)+r'(?!\d)',txt))>=2,i
        assert len(d.sections)==2
        # 新正文段落由显式字体与段落格式生成；封面沿用模板。
        for p in d.paragraphs[15:]:
            if p.text and p.style.name=='Normal' and not re.match(r'^[图表]\d',p.text):
                for r in p.runs:
                    assert r.font.name=='Times New Roman' and r._element.rPr.rFonts.get(qn('w:eastAsia')) in {'宋体','黑体'}
    results.append({'file':f.name,'paragraphs':len(d.paragraphs),'tables':len(d.tables),'inline_images':len(d.inline_shapes),'structural_check':'pass','visual_check':'not rendered: soffice unavailable'})
layoutissues=[]
for f in sorted((ROOT/'.work/artifacts/slides').glob('slide-*.json')):
    data=json.loads(f.read_text(encoding='utf-8'))
    for el in data['elements']:
        x,y,w,h=el.get('bbox',[0,0,0,0])
        if x<-.5 or y<-.5 or x+w>1280.5 or y+h>720.5:layoutissues.append([f.name,el.get('text'),el.get('bbox')])
assert not layoutissues,layoutissues
with zipfile.ZipFile(ROOT/'docs/deliverables/答辩PPT.pptx') as z:
    assert sum(bool(re.fullmatch(r'ppt/slides/slide\d+\.xml',n)) for n in z.namelist())==12
    assert sum(bool(re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n)) for n in z.namelist())==12
    assert z.testzip() is None
(ROOT/'docs/ai-process/材料结构检查.json').write_text(json.dumps({'word':results,'slides':{'count':12,'notes':12,'bounds_check':'pass','visual_check':'12 rendered slides inspected; slides7/9 corrected'}},ensure_ascii=False,indent=2),encoding='utf-8')
print('Artifact structural checks passed')
