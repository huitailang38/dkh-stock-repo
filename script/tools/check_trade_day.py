import baostock as bs
import sys
from datetime import datetime
import os

# 屏蔽代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

def is_trade_day():
    lg = bs.login()
    if lg.error_code != '0':
        # 如果登录失败，保守起见返回 True (0)，让主脚本尝试运行
        return True
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 查询交易日历
    rs = bs.query_trade_dates(start_date=today, end_date=today)
    
    is_trading = False
    if rs.error_code == '0':
        row = rs.get_row_data()
        if row and row[1] == '1': # is_trading_day 为 '1' 表示交易日
            is_trading = True
            
    bs.logout()
    return is_trading

if __name__ == "__main__":
    if is_trade_day():
        print(f"[{datetime.now()}] 今日是交易日，允许启动。")
        sys.exit(0) # 退出码 0 表示真
    else:
        print(f"[{datetime.now()}] 今日为非交易日，脚本不启动。")
        sys.exit(1) # 退出码 1 表示假
