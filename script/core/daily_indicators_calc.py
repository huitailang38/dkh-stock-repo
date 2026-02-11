import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_engine, text
import numpy as np
import os
import time

# 1. 屏蔽代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

# 2. 数据库配置
engine = create_engine('mysql+pymysql://root:ddd%401234@127.0.0.1:3306/dkh')

def update_indicators():
    print("--- 启动每日指标增量计算任务 ---")
    
    # 3. 寻找所有需要计算指标的股票清单
    # 逻辑：只要 rsi_14 是空的，就说明这只股票有新数据或刚修复了复权
    find_sql = "SELECT DISTINCT code FROM stock_history WHERE rsi_14 IS NULL"
    with engine.connect() as conn:
        result = conn.execute(text(find_sql))
        codes = [row[0] for row in result]

    total = len(codes)
    if total == 0:
        print("所有股票指标均已封盘，无须计算。")
        return

    print(f"检测到 {total} 只股票需要更新指标...")

    for i, code in enumerate(codes):
        try:
            # 4. 获取该股历史数据 (取最近 100 天足够算准指标)
            # 4h4g服务器处理 100 条数据非常快
            df = pd.read_sql(f"SELECT date, code, open, high, low, close FROM stock_history WHERE code='{code}' ORDER BY date ASC", con=engine)
            
            if len(df) < 5: continue 

            # --- 【核心改进：初始化坑位】 ---
            # 先给所有指标列赋 None，防止计算失败导致 SQL 参数缺失
            target_cols = ['rsi_14', 'k_9_3', 'd_9_3', 'j_9_3', 'macd_dif', 'macd_dea', 'macd_hist']
            for col in target_cols:
                df[col] = None

            # 5. 执行技术分析计算
            # 增加长度判断，彻底解决新股/停牌股报错问题
            if len(df) >= 15:
                df['rsi_14'] = ta.rsi(df['close'], length=14)
            
            if len(df) >= 10:
                kdj = ta.kdj(df['high'], df['low'], df['close'], length=9)
                if kdj is not None:
                    df['k_9_3'], df['d_9_3'], df['j_9_3'] = kdj['K_9_3'], kdj['D_9_3'], kdj['J_9_3']
            
            if len(df) >= 35:
                macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
                if macd is not None:
                    df['macd_dif'] = macd['MACD_12_26_9']
                    df['macd_dea'] = macd['MACDs_12_26_9']
                    df['macd_hist'] = macd['MACDh_12_26_9']

            # --- 【核心改进：数据清洗】 ---
            # 将 numpy 的 NaN 强制转换为 Python 的 None (MySQL 识别为 NULL)
            df[target_cols] = df[target_cols].astype(object)
            df = df.replace({np.nan: None})

            # 6. 批量回填数据库
            # 我们只更新那些指标字段还是 NULL 的行，或者更新该股全部（推荐更新全部，确保复权正确）
            with engine.begin() as conn:
                update_sql = text("""
                    UPDATE stock_history 
                    SET rsi_14 = :rsi_14, 
                        k_9_3 = :k_9_3, d_9_3 = :d_9_3, j_9_3 = :j_9_3,
                        macd_dif = :macd_dif, macd_dea = :macd_dea, macd_hist = :macd_hist
                    WHERE date = :date AND code = :code
                """)
                # 转换 DataFrame 为字典列表
                params = df.to_dict('records')
                conn.execute(update_sql, params)

            if i % 100 == 0:
                print(f"进度: {i}/{total} | {code} 指标已就绪")

        except Exception as e:
            # 即使报错也跳过，不影响整体进度
            print(f"跳过异常股票 {code}: {e}")
            continue

    print("✅ 每日指标计算任务完成。")

if __name__ == "__main__":
    start_tm = time.time()
    update_indicators()
    print(f"总耗时: {time.time() - start_tm:.2f} 秒")