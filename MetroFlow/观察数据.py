import pandas as pd

pd.set_option('display.max_columns', None)  # 显示所有列
pd.set_option('display.width', None)        # 不限制输出宽度

df = pd.read_csv("metroData_ODFlow.csv", nrows=10)
print(df)


