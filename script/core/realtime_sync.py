import pandas as pd 
import requests 
from sqlalchemy import create_engine, text 
import os 
import time 
from datetime import datetime 

# 1. 屏蔽代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

# 2. 数据库配置
engine = create_engine('mysql+pymysql://root:ddd%401234@localhost:3306/dkh') 

def fetch_all_fields(): 
    # 动态获取代码清单
    with engine.connect() as conn: 
        all_codes = [row[0] for row in conn.execute(text("SELECT DISTINCT code FROM stock_history"))] 
     
    if not all_codes: 
        print(f"[{datetime.now()}] 未找到待同步的股票代码")
        return 
     
    batch_size = 60  
    all_data = [] 
     
    for i in range(0, len(all_codes), batch_size): 
        batch = all_codes[i:i+batch_size] 
        # 腾讯接口代码格式：sh600000, sz000001
        api_codes = ",".join([c.replace('.', '') for c in batch]) 
        url = f"http://qt.gtimg.cn/q={api_codes}" 
         
        try: 
            r = requests.get(url, timeout=5) 
            r.encoding = 'GBK' 
            lines = r.text.split(';') 
            for line in lines: 
                if len(line) < 100: continue 
                
                # 解析逻辑：v_sh600000="xxx~xxx~..."
                header, content_str = line.split('=')
                # 从 header 中提取代码，例如 v_sh600000 -> sh.600000
                raw_code = header.replace('v_', '').strip()
                if raw_code.startswith('sh'):
                    formatted_code = 'sh.' + raw_code[2:]
                elif raw_code.startswith('sz'):
                    formatted_code = 'sz.' + raw_code[2:]
                else:
                    formatted_code = raw_code
                
                content = content_str.strip('"') 
                p = content.split('~') 
                 
                all_data.append({ 
                    'code': formatted_code, 
                    'name': p[1], 
                    'price': float(p[3]), 
                    'pre_close': float(p[4]), 
                    'open': float(p[5]), 
                    'high': float(p[33]), 
                    'low': float(p[34]), 
                    'volume': int(float(p[6]) * 100), 
                    'amount': float(p[37]) * 10000, 
                    'outer_vol': int(p[7]) * 100 if p[7] else 0, 
                    'inner_vol': int(p[8]) * 100 if p[8] else 0, 
                    'buy1_price': float(p[9]) if p[9] else 0, 
                    'buy1_vol': int(p[10]) if p[10] else 0, 
                    'sell1_price': float(p[19]) if p[19] else 0, 
                    'sell1_vol': int(p[20]) if p[20] else 0, 
                    'recent_trade_time': datetime.strptime(p[30], '%Y%m%d%H%M%S'), 
                    'pct_chg': float(p[32]), 
                    'amplitude': float(p[43]), 
                    'turnover': float(p[38]) if p[38] else 0, 
                    'pe': float(p[39]) if p[39] else 0, 
                    'volume_ratio': float(p[41]) if p[41] else 0, 
                    'mc_circ_billion': float(p[44]) if p[44] else 0, 
                    'mc_total_billion': float(p[45]) if p[45] else 0 
                }) 
        except Exception as e: 
            print(f"解析错误: {e}")
            continue 
 
    if all_data: 
        df = pd.DataFrame(all_data) 
        with engine.begin() as conn: 
            # 使用 TRUNCATE 清空表以保证快照的实时性
            conn.execute(text("TRUNCATE TABLE stock_realtime_full")) 
            df.to_sql('stock_realtime_full', con=conn, if_exists='append', index=False) 
        print(f"[{datetime.now()}] 成功刷新 {len(df)} 只股票数据") 
 
if __name__ == "__main__": 
    print("--- 启动全市场实时行情同步任务 (自动退出模式) ---")
    while True: 
        now = datetime.now() 
        current_time = (now.hour, now.minute)
        
        # 1. 活跃抓取窗：9:15-11:30, 12:55-15:00
        is_active = (9, 15) <= current_time <= (11, 30) or (12, 55) <= current_time <= (15, 0)
        
        # 2. 缓冲退出窗：11:30-11:35, 15:00-15:05
        # 只要超过了 15:00 且在 15:05 之内，我们停止抓取，等待 5 分钟后退出
        is_buffer_morning = (11, 30) < current_time <= (11, 35)
        is_buffer_afternoon = (15, 0) < current_time <= (15, 5)

        if is_active: 
            try:
                fetch_all_fields() 
            except Exception as e:
                print(f"任务运行异常: {e}")
            time.sleep(60)  
        elif is_buffer_morning or is_buffer_afternoon:
            print(f"[{now}] 交易结束，进入 5 分钟安全缓冲期...")
            time.sleep(300)
            print(f"[{datetime.now()}] 缓冲期结束，脚本优雅退出。")
            break
        else:
            # 如果是其他时间（比如中午休市），继续休眠但不退出，直到下午场
            if (11, 35) < current_time < (12, 55):
                print(f"[{now}] 中午休市，休眠中...")
                time.sleep(300)
            else:
                # 理论上如果是晚上启动，直接退出
                print(f"[{now}] 非交易时段，脚本退出。")
                break
