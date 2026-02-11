import os
import baostock as bs
import pandas as pd
from sqlalchemy import create_engine
import time
from datetime import datetime, timedelta

# 彻底禁用系统代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

# 数据库连接 (请确保密码正确)
engine = create_engine('mysql+pymysql://root:ddd%401234@127.0.0.1:3306/dkh')


def cold_start_only_baostock():
    # 1. 登录 BaoStock
    lg = bs.login()
    print(f"BaoStock 登录状态: {lg.error_msg}")

    # 2. 获取股票清单 (改用 BaoStock 自己的接口)
    print("正在通过 BaoStock 获取全市场股票清单...")
    # 获取最近一个交易日的清单（如果今天是周末，建议写前一个周五的日期）
    # 这里我们取昨天或今天的日期
    target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    rs_list = bs.query_all_stock(day=target_date)
    stock_data = []
    while (rs_list.error_code == '0') & rs_list.next():
        stock_data.append(rs_list.get_row_data())

    if not stock_data:
        # 如果取不到数据，可能是今天没开盘，尝试取上一个交易日
        print("指定日期无清单，尝试获取历史清单...")
        rs_list = bs.query_all_stock(day="2025-02-05")  # 写一个确定的交易日
        while (rs_list.error_code == '0') & rs_list.next():
            stock_data.append(rs_list.get_row_data())

    df_list = pd.DataFrame(stock_data, columns=rs_list.fields)

    # 过滤出 A 股（剔除指数等），BaoStock 的 code 格式已经是 'sh.600000'
    # 我们只需要 sh.60, sz.00, sz.30, sz.002 等开头的
    df_list = df_list[df_list['code'].str.contains('sh.60|sz.00|sz.30|sz.002')]
    stock_codes = df_list['code'].tolist()

    print(f"成功获取 {len(stock_codes)} 只 A 股清单")

    # 3. 定义抓取字段
    fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"

    total = len(stock_codes)
    for i, bs_code in enumerate(stock_codes):
        try:
            # 抓取 2024 年至今的历史 (adjustflag='2' 是前复权)
            rs = bs.query_history_k_data_plus(
                bs_code, fields,
                start_date='2024-01-01',
                frequency="d",
                adjustflag="2"
            )

            data = []
            while (rs.error_code == '0') & rs.next():
                data.append(rs.get_row_data())

            if data:
                df = pd.DataFrame(data, columns=rs.fields)

                # 类型转换
                cols_to_numeric = [c for c in df.columns if c not in ['date', 'code']]
                for col in cols_to_numeric:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                # 写入数据库
                df.to_sql('stock_history', con=engine, if_exists='append', index=False)

            if i % 10 == 0:
                print(f"进度: {i}/{total} - 已完成: {bs_code}")

            # 频率控制
            time.sleep(0.1)

        except Exception as e:
            print(f"错误: {bs_code} -> {e}")
            continue

    bs.logout()
    print("历史数据冷启动完成！")


if __name__ == "__main__":
    cold_start_only_baostock()