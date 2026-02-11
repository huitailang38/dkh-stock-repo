import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_engine, text
import numpy as np
import os

# 屏蔽代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 1. 连接数据库 (请确保数据库名是 dkh)
engine = create_engine('mysql+pymysql://root:ddd%401234@127.0.0.1:3306/dkh')

def update_all_indicators():
    print("正在获取股票清单...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT code FROM stock_history"))
        codes = [row[0] for row in result]

    total = len(codes)
    print(f"开始补齐 {total} 只股票的指标...")

    for i, code in enumerate(codes):
        try:
            # 2. 读取数据
            df = pd.read_sql(f"SELECT date, code, open, high, low, close FROM stock_history WHERE code='{code}' ORDER BY date ASC", con=engine)
            
            if len(df) < 30: # 数据太少无法计算
                continue 
            
            # 3. 计算指标
            # RSI
            df['rsi_14'] = ta.rsi(df['close'], length=14)
            # KDJ
            kdj = ta.kdj(df['high'], df['low'], df['close'], length=9, signal=3)
            if kdj is not None:
                df['k_9_3'] = kdj['K_9_3']
                df['d_9_3'] = kdj['D_9_3']
                df['j_9_3'] = kdj['J_9_3']
            # MACD
            macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
            if macd is not None:
                df['macd_dif'] = macd['MACD_12_26_9']
                df['macd_dea'] = macd['MACDs_12_26_9']
                df['macd_hist'] = macd['MACDh_12_26_9']

            # --- 核心修正：处理 NaN ---
            # 把所有的 np.nan 替换为 None
            df = df.replace({np.nan: None})

            # 4. 批量更新
            with engine.begin() as conn:
                update_sql = text("""
                    UPDATE stock_history 
                    SET rsi_14 = :rsi_14, 
                        k_9_3 = :k_9_3, d_9_3 = :d_9_3, j_9_3 = :j_9_3,
                        macd_dif = :macd_dif, macd_dea = :macd_dea, macd_hist = :macd_hist
                    WHERE date = :date AND code = :code
                """)
                
                # 构造参数字典
                params = df.to_dict('records')
                conn.execute(update_sql, params)
                
            if i % 100 == 0:
                print(f"进度: {i}/{total} - {code} 完成")

        except Exception as e:
            # 如果还是报错，打印出具体的错误列，方便排查
            print(f"错误: {code} -> {str(e)[:100]}")
            continue

    print("✅ 任务完成！")

if __name__ == "__main__":
    update_all_indicators()