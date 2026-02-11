import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 数据库连接 - 密码中的@需要编码为%40
engine = create_engine('mysql+pymysql://root:ddd%401234@127.0.0.1:3306/dkh')

def get_latest_trading_date():
    """获取最新的交易日"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(date) FROM stock_history"))
        return result.fetchone()[0]

def filter_stocks_by_all_conditions():
    """
    严格按照给定的9个条件筛选股票
    """
    # 获取最新交易日
    latest_date = get_latest_trading_date()
    print(f"最新交易日: {latest_date}")
    
    # 1. 首先获取满足条件1-4,6-8的最新交易日股票数据
    query_conditions = f"""
    SELECT 
        date, code, 
        open, high, low, close, 
        volume, amount,
        rsi_14, 
        k_9_3, d_9_3, j_9_3,
        macd_dif, macd_dea, macd_hist,
        pctChg as change_pct,
        peTTM,
        tradestatus, isST
    FROM stock_history 
    WHERE date = '{latest_date}'
    """
    
    df = pd.read_sql(query_conditions, con=engine)
    
    if df.empty:
        print(f"日期 {latest_date} 无数据")
        return pd.DataFrame()
    
    print(f"总股票数量: {len(df)}")
    
    # 条件1: 排除ST股票和停牌股票
    df_filtered = df[(df['isST'] == 0) & (df['tradestatus'] == 1)]
    print(f"条件1 - 排除ST和停牌后: {len(df_filtered)}")
    
    # 条件2: RSI < 35
    df_filtered = df_filtered[df_filtered['rsi_14'] < 35]
    print(f"条件2 - RSI < 35: {len(df_filtered)}")
    
    # 条件3: KDJ金叉 (K > D)
    df_filtered = df_filtered[df_filtered['k_9_3'] > df_filtered['d_9_3']]
    print(f"条件3 - KDJ金叉(K>D): {len(df_filtered)}")
    
    # 条件4: MACD金叉 (DIF > DEA)
    df_filtered = df_filtered[df_filtered['macd_dif'] > df_filtered['macd_dea']]
    print(f"条件4 - MACD金叉(DIF>DEA): {len(df_filtered)}")
    
    # 条件6: KDJ J值在0-100之间
    df_filtered = df_filtered[(df_filtered['j_9_3'] >= 0) & (df_filtered['j_9_3'] <= 100)]
    print(f"条件6 - KDJ J值0-100: {len(df_filtered)}")
    
    # 条件7: 市盈率0-50倍
    df_filtered = df_filtered[(df_filtered['peTTM'] > 0) & (df_filtered['peTTM'] <= 50)]
    print(f"条件7 - 市盈率0-50倍: {len(df_filtered)}")
    
    # 条件8: 涨幅在-5%到10%之间
    df_filtered = df_filtered[(df_filtered['change_pct'] >= -5) & (df_filtered['change_pct'] <= 10)]
    print(f"条件8 - 涨幅-5%到10%: {len(df_filtered)}")
    
    if df_filtered.empty:
        print("前8个条件已筛选完毕，无符合股票")
        return pd.DataFrame()
    
    # 获取符合条件的股票代码
    qualified_codes = df_filtered['code'].tolist()
    
    print(f"\n开始检查条件5和条件9...")
    
    # 检查条件5: 今日成交量 > 5日均量
    # 检查条件9: 价格在60日均线(±2%)内
    final_stocks = []
    
    for idx, row in df_filtered.iterrows():
        code = row['code']
        
        # 查询该股票最近60个交易日的数据
        query_history = f"""
        SELECT date, close, volume
        FROM stock_history 
        WHERE code = '{code}' 
            AND date <= '{latest_date}'
        ORDER BY date DESC
        LIMIT 61  # 取61天，包含今天
        """
        
        history_df = pd.read_sql(query_history, con=engine)
        
        if len(history_df) < 61:
            continue  # 数据不足60天
        
        # 计算5日均量 (不包括今天)
        volume_ma5 = history_df.iloc[1:6]['volume'].mean()  # 前5天(不包括今天)
        
        # 计算60日均价 (不包括今天)
        price_ma60 = history_df.iloc[1:61]['close'].mean()  # 前60天(不包括今天)
        
        today_volume = row['volume']
        today_close = row['close']
        
        # 条件5: 今日成交量 > 5日均量
        condition5 = today_volume > volume_ma5
        
        # 条件9: 价格在60日均线(±2%)内
        lower_bound = price_ma60 * 0.98  # -2%
        upper_bound = price_ma60 * 1.02  # +2%
        condition9 = lower_bound <= today_close <= upper_bound
        
        if condition5 and condition9:
            # 添加额外计算字段
            stock_data = row.to_dict()
            stock_data['volume_ma5'] = volume_ma5
            stock_data['price_ma60'] = price_ma60
            stock_data['distance_to_ma60'] = ((today_close - price_ma60) / price_ma60 * 100)
            final_stocks.append(stock_data)
    
    # 转换为DataFrame
    if final_stocks:
        final_df = pd.DataFrame(final_stocks)
        print(f"条件5 - 成交量>5日均量: {len(final_df)}")
        print(f"条件9 - 价格在60日均线±2%内: {len(final_df)}")
        return final_df
    else:
        print("条件5和条件9筛选后无符合股票")
        return pd.DataFrame()

def display_results(filtered_df):
    """
    显示筛选结果
    """
    if filtered_df.empty:
        print("\n没有满足所有条件的股票")
        return
    
    print(f"\n{'='*80}")
    print(f"最终筛选结果: 共找到 {len(filtered_df)} 只股票满足所有9个条件")
    print(f"{'='*80}")
    
    # 按RSI排序（RSI越低越超卖）
    filtered_df = filtered_df.sort_values('rsi_14')
    
    print("\n股票列表 (按RSI从低到高排序，RSI越低越超卖):")
    print("-" * 120)
    print(f"{'代码':<10} {'收盘价':<8} {'涨跌幅%':<8} {'RSI':<6} {'K':<6} {'D':<6} {'J':<6} {'MACD DIF':<10} {'MACD DEA':<10} {'成交量/5日均量':<15} {'距60日线%':<12}")
    print("-" * 120)
    
    for idx, row in filtered_df.iterrows():
        volume_ratio = row['volume'] / row['volume_ma5'] if row['volume_ma5'] > 0 else 0
        
        print(f"{row['code']:<10} {row['close']:<8.2f} {row['change_pct']:<8.2f} "
              f"{row['rsi_14']:<6.1f} {row['k_9_3']:<6.1f} {row['d_9_3']:<6.1f} {row['j_9_3']:<6.1f} "
              f"{row['macd_dif']:<10.4f} {row['macd_dea']:<10.4f} "
              f"{volume_ratio:<15.2f} {row['distance_to_ma60']:<12.2f}")
    
    # 显示统计信息
    print(f"\n{'='*80}")
    print("统计信息:")
    print(f"平均RSI: {filtered_df['rsi_14'].mean():.2f}")
    print(f"平均市盈率PE: {filtered_df['peTTM'].mean():.2f}")
    print(f"平均涨幅: {filtered_df['change_pct'].mean():.2f}%")
    print(f"平均成交量/5日均量比率: {(filtered_df['volume'] / filtered_df['volume_ma5']).mean():.2f}")
    print(f"平均距60日线距离: {filtered_df['distance_to_ma60'].mean():.2f}%")
    
    # 显示所有符合条件的股票代码
    print(f"\n所有符合条件的股票代码:")
    codes = filtered_df['code'].tolist()
    for i in range(0, len(codes), 10):
        print("  ".join(codes[i:i+10]))

def export_detailed_results(filtered_df):
    """
    导出详细结果到CSV文件
    """
    if filtered_df.empty:
        print("没有数据可导出")
        return None
    
    # 准备导出数据
    export_df = filtered_df.copy()
    
    # 计算额外指标
    export_df['volume_ratio'] = export_df['volume'] / export_df['volume_ma5']
    
    # 选择要导出的列
    export_columns = [
        'date', 'code', 'close', 'change_pct',
        'rsi_14', 'k_9_3', 'd_9_3', 'j_9_3',
        'macd_dif', 'macd_dea', 'macd_hist',
        'peTTM', 'volume', 'volume_ma5', 'volume_ratio',
        'price_ma60', 'distance_to_ma60'
    ]
    
    # 重命名列
    export_df = export_df[export_columns]
    export_df = export_df.rename(columns={
        'change_pct': '涨跌幅%',
        'rsi_14': 'RSI',
        'k_9_3': 'K值',
        'd_9_3': 'D值',
        'j_9_3': 'J值',
        'macd_dif': 'MACD_DIF',
        'macd_dea': 'MACD_DEA',
        'macd_hist': 'MACD柱',
        'peTTM': '市盈率',
        'volume': '成交量',
        'volume_ma5': '5日均量',
        'volume_ratio': '成交量比(今日/5日均)',
        'price_ma60': '60日均价',
        'distance_to_ma60': '距60日线%'
    })
    
    # 导出到CSV
    filename = f"股票筛选结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    export_df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"\n详细结果已导出到: {filename}")
    return filename

def check_individual_stock(code):
    """
    检查单只股票是否符合所有条件
    """
    latest_date = get_latest_trading_date()
    
    # 查询该股票最新数据
    query = f"""
    SELECT 
        date, code, 
        open, high, low, close, 
        volume, amount,
        rsi_14, 
        k_9_3, d_9_3, j_9_3,
        macd_dif, macd_dea, macd_hist,
        pctChg as change_pct,
        peTTM,
        tradestatus, isST
    FROM stock_history 
    WHERE code = '{code}' AND date = '{latest_date}'
    """
    
    df = pd.read_sql(query, con=engine)
    
    if df.empty:
        print(f"股票 {code} 在 {latest_date} 无数据")
        return
    
    row = df.iloc[0]
    
    print(f"\n检查股票 {code} 在 {latest_date} 的条件符合情况:")
    print("-" * 50)
    
    # 条件1: 排除ST股票和停牌股票
    cond1 = (row['isST'] == 0) and (row['tradestatus'] == 1)
    print(f"条件1 - 非ST且正常交易: {'✓' if cond1 else '✗'}")
    
    # 条件2: RSI < 35
    cond2 = row['rsi_14'] < 35
    print(f"条件2 - RSI < 35 (当前: {row['rsi_14']}): {'✓' if cond2 else '✗'}")
    
    # 条件3: KDJ金叉
    cond3 = row['k_9_3'] > row['d_9_3']
    print(f"条件3 - KDJ金叉 (K:{row['k_9_3']} > D:{row['d_9_3']}): {'✓' if cond3 else '✗'}")
    
    # 条件4: MACD金叉
    cond4 = row['macd_dif'] > row['macd_dea']
    print(f"条件4 - MACD金叉 (DIF:{row['macd_dif']} > DEA:{row['macd_dea']}): {'✓' if cond4 else '✗'}")
    
    # 条件6: KDJ J值0-100
    cond6 = 0 <= row['j_9_3'] <= 100
    print(f"条件6 - J值0-100 (当前: {row['j_9_3']}): {'✓' if cond6 else '✗'}")
    
    # 条件7: 市盈率0-50
    cond7 = 0 < row['peTTM'] <= 50
    print(f"条件7 - 市盈率0-50倍 (当前: {row['peTTM']}): {'✓' if cond7 else '✗'}")
    
    # 条件8: 涨幅-5%到10%
    cond8 = -5 <= row['change_pct'] <= 10
    print(f"条件8 - 涨幅-5%到10% (当前: {row['change_pct']}%): {'✓' if cond8 else '✗'}")
    
    # 获取历史数据计算条件5和9
    query_history = f"""
    SELECT date, close, volume
    FROM stock_history 
    WHERE code = '{code}' 
        AND date <= '{latest_date}'
    ORDER BY date DESC
    LIMIT 61
    """
    
    history_df = pd.read_sql(query_history, con=engine)
    
    if len(history_df) >= 61:
        # 条件5: 今日成交量 > 5日均量
        volume_ma5 = history_df.iloc[1:6]['volume'].mean()
        cond5 = row['volume'] > volume_ma5
        print(f"条件5 - 成交量>{volume_ma5:.0f} (今日:{row['volume']}): {'✓' if cond5 else '✗'}")
        
        # 条件9: 价格在60日均线(±2%)内
        price_ma60 = history_df.iloc[1:61]['close'].mean()
        lower_bound = price_ma60 * 0.98
        upper_bound = price_ma60 * 1.02
        cond9 = lower_bound <= row['close'] <= upper_bound
        distance = ((row['close'] - price_ma60) / price_ma60 * 100)
        print(f"条件9 - 价格在60日线±2%内 (60日线:{price_ma60:.2f}, 当前:{row['close']}, 距离:{distance:.2f}%): {'✓' if cond9 else '✗'}")
        
        all_conditions = [cond1, cond2, cond3, cond4, cond5, cond6, cond7, cond8, cond9]
    else:
        print(f"条件5和9 - 数据不足(需要至少60天历史数据): ✗")
        all_conditions = [cond1, cond2, cond3, cond4, False, cond6, cond7, cond8, False]
    
    # 总结
    print("-" * 50)
    passed_count = sum(all_conditions)
    print(f"总计: 通过 {passed_count}/9 个条件")
    
    if passed_count == 9:
        print(f"✅ 股票 {code} 符合所有筛选条件!")
    else:
        print(f"❌ 股票 {code} 未通过所有条件")
        
        # 显示未通过的条件
        failed_conditions = [i+1 for i, cond in enumerate(all_conditions) if not cond]
        print(f"未通过的条件: {failed_conditions}")

if __name__ == "__main__":
    print("股票筛选系统 - 严格按照9个条件筛选")
    print("=" * 60)
    
    print("正在筛选...")
    filtered_stocks = filter_stocks_by_all_conditions()
    
    if not filtered_stocks.empty:
        display_results(filtered_stocks)
        
        # 询问是否导出
        export_choice = input("\n是否导出详细结果到CSV? (y/n, 默认y): ") or "y"
        if export_choice.lower() == 'y':
            export_filename = export_detailed_results(filtered_stocks)
        
        # 询问是否检查特定股票
        check_choice = input("\n是否检查特定股票的条件符合情况? (输入股票代码或回车跳过): ")
        if check_choice:
            check_individual_stock(check_choice)
    else:
        print("\n没有找到符合所有条件的股票")
        
        # 即使没有符合所有条件的，也可以检查特定股票
        check_choice = input("\n是否检查特定股票的条件符合情况? (输入股票代码或回车退出): ")
        if check_choice:
            check_individual_stock(check_choice)
    
    print("\n筛选完成!")