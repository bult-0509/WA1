"""将本地2017上海POI大文件处理成可随项目分发的小型汇总。"""
from argparse import ArgumentParser
from pathlib import Path
import json

from src.poi_processing import prepare_poi


ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = ArgumentParser(description='准备站点周边POI分析数据')
    parser.add_argument('--input', type=Path, required=True, help='2017上海市POI_全部.csv 的路径')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/processed')
    args = parser.parse_args()
    result = prepare_poi(args.input, ROOT / 'data/processed/stations.parquet', args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
