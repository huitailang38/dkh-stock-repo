import pandas as pd
import pandas_ta as ta
import requests
from sqlalchemy import create_engine, text
import os
from datetime import datetime
import numpy as np

# 1. 屏蔽代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 2. 数据库配置
engine = create_engine('mysql+pymysql://root:ddd%401234@127.0.0.1:3306/dkh')

def fetch_realtime_tencent_full(code_list):
    """通过腾讯全量接口获取实时数据，支持 GBK 编码"""
    results = []
    # 腾讯全量接口单次建议不超过 60 个代码，防止 URL 过长
    batch_size = 60 
    
    print(f"开始请求腾讯实时接口，共 {len(code_list)} 只股票...")
    
    for i in range(0, len(code_list), batch_size):
        batch = code_list[i:i+batch_size]
        # 格式转换: sh.600000 -> sh600000
        api_codes = ",".join([c.replace('.', '') for c in batch])
        url = f"http://qt.gtimg.cn/q={api_codes}"
        
        try:
            r = requests.get(url, timeout=10)
            r.encoding = 'GBK' # 腾讯必须用 GBK
            
            lines = r.text.split(';')
            for line in lines:
                if len(line) < 50: continue # 过滤空行
                
                # 解析格式: v_sh601166="51~兴业银行~601166~18.28~18.85~18.85...~3800.55";
                header, content = line.split('=')
                parts = content.strip('"').split('~')
                
                # 提取关键字段索引
                # 3:现价, 4:昨收, 5:今开, 6:成交量(手), 33:最高, 34:最低, 45:流通市值(亿)
                results.append({
                    'code': header.strip().replace('v_', '').replace('sh', 'sh.').replace('sz', 'sz.'),
                    'name': parts[1],
                    'close': float(parts[3]),
                    'pre_close': float(parts[4]),
                    'open': float(parts[5]),
                    'high': float(parts[33]),
                    'low': float(parts[34]),
                    'volume': float(parts[6]) * 100, # 转换成股
                    'mc_circ_billion': float(parts[45]) if parts[45] else 0
                })
        except Exception as e:
            continue
            
    return pd.DataFrame(results)

def main_strategy_v6():
    print(f"--- 选股任务启动 [{datetime.now().strftime('%H:%M:%S')}] ---")
    
    # 1. 获取数据库代码清单
    with engine.connect() as conn:
        all_codes = [row[0] for row in conn.execute(text("SELECT DISTINCT code FROM stock_history"))]
    
    if not all_codes:
        print("数据库中没有股票代码，请检查冷启动是否成功。")
        return

    # 2. 抓取实时数据
    df_spot = fetch_realtime_tencent_full(all_codes)
    
    if df_spot.empty:
        print("❌ 错误：未能从实时接口获取任何数据。请检查服务器是否能访问 qt.gtimg.cn")
        return
    
    print(f"2. 实时接口抓取成功，实际获取到 {len(df_spot)} 只股票数据")

    # 3. 硬性条件：市值过滤 (50亿 - 200亿)
    df_filtered = df_spot[(df_spot['mc_circ_billion'] >= 50) & (df_spot['mc_circ_billion'] <= 200)].copy()
    print(f"3. 市值过滤完成，剩余 {len(df_filtered)} 只候选股")

    if df_filtered.empty:
        print("没有符合市值条件的股票。")
        return

    # 4. 一次性读取数据库历史 (最近 90 天)
    sql = "SELECT date, code, open, high, low, close, volume FROM stock_history WHERE date > DATE_SUB(CURDATE(), INTERVAL 90 DAY)"
    with engine.connect() as conn:
        df_hist_all = pd.read_sql(text(sql), con=conn)

    final_picks = []

    # 5. 多因子评分
    print("4. 正在进行多因子打分...")
    for i, row in df_filtered.iterrows():
        full_code = row['code']
        
        # 提取历史记录
        df_h = df_hist_all[df_hist_all['code'] == full_code].copy()
        if len(df_h) < 35: continue
        
        # 缝合 T+0 数据
        today_row = pd.DataFrame([{
            'date': datetime.now().date(),
            'code': full_code,
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume']
        }])
        df_c = pd.concat([df_h, today_row], ignore_index=True)

        try:
            # 计算技术指标
            df_c['rsi'] = ta.rsi(df_c['close'], length=14)
            kdj = ta.kdj(df_c['high'], df_c['low'], df_c['close'], length=9)
            macd = ta.macd(df_c['close'])
            df_c['ma60'] = ta.sma(df_c['close'], length=60)
            df_c['vol_ma5'] = df_c['volume'].rolling(5).mean()
            df_c = pd.concat([df_c, kdj, macd], axis=1)

            curr = df_c.iloc[-1]
            prev = df_c.iloc[-2]

            score = 0
            # --- 打分逻辑 (2分一个因子) ---
            f1 = 2 if curr['rsi'] < 35 else 0
            # KDJ金叉: 昨K<昨D 且 今K>今D
            f2 = 2 if (prev['K_9_3'] < prev['D_9_3'] and curr['K_9_3'] > curr['D_9_3']) else 0
            # 量能: 今日量 > 5日均量
            f3 = 2 if curr['volume'] > curr['vol_ma5'] else 0
            # MACD多头: DIF > DEA
            f4 = 2 if curr['MACD_12_26_9'] > curr['MACDs_12_26_9'] else 0
            # MA60支撑: 现价在MA60上下 2% 范围内
            f5 = 2 if (curr['ma60'] and abs(curr['close'] - curr['ma60'])/curr['ma60'] <= 0.02) else 0
            
            total_score = f1 + f2 + f3 + f4 + f5
            
            if total_score >= 6:
                # 计算涨跌幅
                pct = round((row['close'] - row['pre_close']) / row['pre_close'] * 100, 2)
                final_picks.append({
                    'data_date': curr['date'],
                    'stock_code': full_code,
                    'stock_name': row['name'],
                    'total_score': total_score,
                    'current_price': row['close'],
                    'pct_change': pct,
                    'is_rsi': '是' if f1 else '否',
                    'is_kdj_gold': '是' if f2 else '否',
                    'is_vol_push': '是' if f3 else '否',
                    'is_macd_gold': '是' if f4 else '否',
                    'is_ma60_support': '是' if f5 else '否'
                })
        except:
            continue

# 6. 结果呈现
    if final_picks:
        res_df = pd.DataFrame(final_picks).sort_values('total_score', ascending=False)
        print(f"\n✅ 选股完成！筛选出 {len(res_df)} 只高分金股：")
        print(res_df[['stock_code', 'stock_name', 'total_score', 'current_price', 'pct_change']])
        # --- 新增：写入前先删除当天旧数据，防止重复 ---
        today_date = res_df['data_date'].iloc[0]
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM strategy_results WHERE data_date = '{today_date}'"))
        # ----------------------------------------
		
        # 保存到数据库
        res_df.to_sql('strategy_results', con=engine, if_exists='append', index=False)
        print("\n结果已存入数据库 strategy_results 表。")
    else:
        print("\n❌ 未能选出符合总分 >= 6 的股票。")

if __name__ == "__main__":
    main_strategy_v6()