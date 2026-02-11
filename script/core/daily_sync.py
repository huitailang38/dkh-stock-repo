import baostock as bs
import pandas as pd
from sqlalchemy import create_engine, text
import numpy as np
import os
from datetime import datetime

# 1. 屏蔽代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

# 2. 数据库配置 (确认数据库名为 dkh)
engine = create_engine('mysql+pymysql://root:ddd%401234@127.0.0.1:3306/dkh')
def daily_sync_task():
    bs.login()
    print(f"[{datetime.now()}] 启动每日同步任务...")

    # --- 模块 A：获取数据库当前状态 ---
    # 我们不仅拿最后一天，还拿倒数第二天，确保复权校验万无一失
    sql = """
    SELECT a.code, a.date, a.close
    FROM stock_history a
    INNER JOIN (
        SELECT code, MAX(date) as max_date FROM stock_history GROUP BY code
    ) b ON a.code = b.code AND a.date >= DATE_SUB(b.max_date, INTERVAL 7 DAY)
    ORDER BY a.code, a.date ASC
    """
    with engine.connect() as conn:
        all_db_data = pd.read_sql(text(sql), con=conn)
    
    stock_groups = all_db_data.groupby('code')
    total = len(stock_groups)
    fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
    today_str = datetime.now().strftime("%Y-%m-%d")

    for i, (code, group) in enumerate(stock_groups):
        db_last_row = group.iloc[-1]
        db_last_date = db_last_row['date']
        db_last_close = float(db_last_row['close'])
        db_prev_close = float(group.iloc[-2]['close']) if len(group) >= 2 else None

        try:
            # 抓取：从数据库最后一天开始，到今天为止
            rs = bs.query_history_k_data_plus(code, fields, 
                                             start_date=db_last_date.strftime("%Y-%m-%d"), 
                                             end_date=today_str, 
                                             frequency="d", adjustflag="2")
            
            api_list = []
            while (rs.error_code == '0') & rs.next():
                api_list.append(rs.get_row_data())
            
            if not api_list: continue # 没有新数据，跳过

            df_api = pd.DataFrame(api_list, columns=rs.fields)
            for col in ['close', 'preclose']:
                df_api[col] = pd.to_numeric(df_api[col], errors='coerce')

            # --- 模块 B：自动修复逻辑 (发现数据断裂时触发) ---
            is_need_fix = False
            api_last_day_close = float(df_api.iloc[0]['close'])
            
            # 校验 1：如果 API 传回的“最后一天”价格和库里对不上
            if abs(api_last_day_close - db_last_close) > 0.01:
                is_need_fix = True
            
            # 校验 2：如果 API 的昨收和库里的前一天对不上 (解决兴业银行分红问题)
            if not is_need_fix and db_prev_close is not None:
                api_last_day_preclose = float(df_api.iloc[0]['preclose'])
                if abs(api_last_day_preclose - db_prev_close) > 0.01:
                    is_need_fix = True

            if is_need_fix:
                print(f"🚩 [修复模式] {code} 数据失效，重刷历史...")
                full_rebuild_stock(code, fields, today_str)
                continue # 修复完直接跳过，因为新数据已经包含在重刷里了

            # --- 模块 C：增量插入逻辑 (正常交易日补全) ---
            # 如果 df_api 长度大于 1，说明除了“用来对比的那天”，后面还有“新的一天”或“更多天”
            if len(df_api) > 1:
                # 【这就是你要找的新数据插入代码块】
                # 我们切片取出从第 1 行到最后的所有行（第 0 行是库里已有的）
                df_new_rows = df_api.iloc[1:].copy()
                
                # 数据清洗：转数字，处理空值
                for col in df_new_rows.columns:
                    if col not in ['date', 'code']:
                        df_new_rows[col] = pd.to_numeric(df_new_rows[col], errors='coerce')
                df_new_rows = df_new_rows.where(pd.notnull(df_new_rows), None)

                # 执行插入到数据库
                df_new_rows.to_sql('stock_history', con=engine, if_exists='append', index=False)
                # print(f"✅ [增量模式] {code} 成功补全 {len(df_new_rows)} 天新数据")

            if i % 200 == 0:
                print(f"当前进度: {i}/{total}")

        except Exception as e:
            print(f"错误: {code} -> {e}")
            continue

    bs.logout()
    print("✨ 全市场数据同步任务已圆满结束！")

def full_rebuild_stock(code, fields, end_date):
    """把该股的历史数据彻底推倒重来"""
    rs = bs.query_history_k_data_plus(code, fields, start_date='2024-01-01', end_date=end_date, frequency="d", adjustflag="2")
    data = []
    while (rs.error_code == '0') & rs.next():
        data.append(rs.get_row_data())
    if data:
        df = pd.DataFrame(data, columns=rs.fields)
        for col in df.columns:
            if col not in ['date', 'code']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.where(pd.notnull(df), None)
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM stock_history WHERE code='{code}'"))
            df.to_sql('stock_history', con=conn, if_exists='append', index=False)

if __name__ == "__main__":
    daily_sync_task()