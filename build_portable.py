"""从已验证的本地运行环境构建两个独立交付包。"""
from pathlib import Path
import shutil
import zipfile
import json
import sys

ROOT=Path(__file__).resolve().parent

def add_tree(z,folder,prefix,skip=()):
    for p in sorted(folder.rglob('*')):
        if p.is_file() and not any(part in skip for part in p.relative_to(folder).parts) and p.suffix not in {'.pyc','.log'}:
            z.write(p,str(Path(prefix)/p.relative_to(folder)))

def build():
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    runtime=ROOT/'.runtime'
    if not (runtime/'python.exe').exists():
        raise RuntimeError('缺少已验证的.runtime环境，请按README在构建机准备。')
    # requirements.txt包含实际验证过的全部依赖，第三方版权随runtime保留。
    source=dist/'代码.zip'
    core=['app.py','prepare_data.py','build_portable.py','launch.py','README.md','requirements.txt']
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in core:z.write(ROOT/name,name)
        for folder in ['src','assets','tests','.streamlit','my-folder']:
            add_tree(z,ROOT/folder,folder,('__pycache__',))
        add_tree(z,ROOT/'MetroFlow/processed','MetroFlow/processed')
        add_tree(z,ROOT/'MetroFlow/analysis_output','MetroFlow/analysis_output')
        for name in ['数据来源与准备.md','测试与验收记录.md']:
            p=ROOT/'docs'/name
            if p.exists():z.write(p,'docs/'+name)
    if source.stat().st_size>30_000_000:raise RuntimeError('代码ZIP超过课程30MB限制。')
    portable=dist/'便携演示包.zip'
    with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        with zipfile.ZipFile(source) as src:
            for info in src.infolist():z.writestr(info.filename,src.read(info))
        add_tree(z,runtime,'runtime',('__pycache__','tests','test','__pypackages__'))
        # 相对路径使程序离开当前盘符和用户名后仍能定位自己的文件。
        vbs='Set sh=CreateObject("WScript.Shell")\r\nSet fs=CreateObject("Scripting.FileSystemObject")\r\nroot=fs.GetParentFolderName(WScript.ScriptFullName)\r\nsh.CurrentDirectory=root\r\nsh.Run Chr(34) & root & "\\runtime\\pythonw.exe" & Chr(34) & " " & Chr(34) & root & "\\launch.py" & Chr(34),0,False\r\n'
        z.writestr('启动.vbs',vbs.encode('utf-16'))
        # cmd为禁用Windows脚本宿主的机器提供同等入口；ASCII内容兼容中文所在目录。
        z.writestr('启动.cmd','@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0launch.py"\r\n'.encode('ascii'))
        z.writestr('使用说明.txt','请完整解压到本地文件夹，再双击“启动.vbs”或“启动.cmd”。无需安装Python，无需联网。\r\n启动后保留提示窗口；演示结束点击该窗口的“确定”关闭服务。\r\n浏览器地址：http://127.0.0.1:8501\r\n如端口占用，请关闭原有服务后重试。\r\n'.encode('utf-8-sig'))
    sizes={p.name:p.stat().st_size for p in [source,portable]}
    (dist/'包大小.json').write_text(json.dumps(sizes,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(sizes,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':build()
