"""双击入口的最小启动脚本：只用包内Python，只开放本机访问。"""
from pathlib import Path
import ctypes
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent
PORT=8501

def message(text):
    ctypes.windll.user32.MessageBoxW(0,text,'沪上流动',0x40)

if __name__=='__main__':
    if not (ROOT/'data/processed/station_hourly.parquet').exists():
        message('数据文件缺失，请完整解压演示包，再双击启动。');sys.exit(1)
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',PORT))==0:
            message('本地8501端口已被占用。若本系统已打开，请使用原窗口；否则关闭占用程序后重试。');sys.exit(1)
    interpreter=Path(sys.executable).with_name('python.exe')
    logdir=ROOT/'运行记录'
    try:logdir.mkdir(exist_ok=True)
    except OSError:
        logdir=Path(os.environ.get('LOCALAPPDATA',str(ROOT)))/'MetroFlow'
        logdir.mkdir(parents=True,exist_ok=True)
    log=open(logdir/'运行.log','a',encoding='utf-8')
    child=subprocess.Popen([str(interpreter),'-X','utf8','-m','streamlit','run',str(ROOT/'app.py'),
        '--server.address','127.0.0.1','--server.port',str(PORT),'--server.headless','true',
        '--server.fileWatcherType','none','--browser.gatherUsageStats','false'],cwd=ROOT,
        stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(120):
        if child.poll() is not None:
            message(f'程序启动失败，请查看：{logdir / "运行.log"}');sys.exit(1)
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/_stcore/health',timeout=1) as r:
                if r.status==200:break
        except OSError:time.sleep(.5)
    else:
        child.terminate();message('启动等待超时，请查看运行记录后重试。');sys.exit(1)
    webbrowser.open(f'http://127.0.0.1:{PORT}')
    # 本窗口直接持有自己启动的子进程，不保存或猜测其他程序的PID。
    message('系统已在浏览器中打开。\n\n请保持此提示窗口打开。演示结束后点击“确定”关闭本系统服务。')
    child.terminate()
    try:child.wait(timeout=8)
    except subprocess.TimeoutExpired:child.kill()
    log.close()
