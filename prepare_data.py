"""开发机运行一次；答辩时直接读取准备好的数据。"""
from pathlib import Path
import json
import pandas as pd
from src.data_processing import prepare
from src.clustering import train

ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    quality = prepare(ROOT / 'data/raw', ROOT / 'data/processed')
    print(json.dumps(quality, ensure_ascii=False, indent=2), flush=True)
    print(json.dumps(train(ROOT / 'data/processed'), ensure_ascii=False, indent=2), flush=True)
    network = pd.read_parquet(ROOT / 'data/processed/network_daily.parquet')
    valid = network.loc[network.is_valid, 'inFlow']
    pd.DataFrame({'统计量':['总量','日均','日中位数','日最小值','日最大值','有效天数'],
        '值':[valid.sum(),valid.mean(),valid.median(),valid.min(),valid.max(),len(valid)]}).to_csv(
        ROOT / 'data/processed/statistics.csv', index=False, encoding='utf-8-sig')
