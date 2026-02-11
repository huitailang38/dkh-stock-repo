# 📈 DKH A-Share Quantitative Analysis System

本项目是一套工业级的 A 股量化基础基础设施，涵盖了从**多源数据 ETL**、**自动化指标计算**、**实时行情监控**到**多因子策略选股**的全链路闭环。系统设计侧重于数据的高可靠性（自动修复复权断裂）和策略的实时性。

---

## 🏗️ 系统架构与数据流

```text
[数据源]                      [核心处理层 (Python)]                [存储层 (MySQL)]
Baostock (历史/日线) ------> daily_sync.py (增量/修复) ----------> stock_history
Tencent API (实时)   ------> realtime_sync.py (快照) ----------> stock_realtime_full
                              |
                              v
                        daily_indicators_calc.py (TA-Lib) ----> (回填指标到) stock_history
                              |
                              v
                        lianghua.py / realtime_picker.py ----> strategy_results
```

---

## � 目录结构

- [logs/](file:///root/dkh/dkh-stock-repo/logs/): 存储 Crontab 任务的自动化运行日志。
- [sql/](file:///root/dkh/dkh-stock-repo/sql/): 包含 `stock_history` (主宽表), `stock_realtime_full` (实时快照), `strategy_results` (策略输出) 的建表语句。
- [script/core/](file:///root/dkh/dkh-stock-repo/script/core/):
    - [daily_sync.py](file:///root/dkh/dkh-stock-repo/script/core/daily_sync.py): **核心 ETL**。支持增量更新，并具备自动校验逻辑（对比 API 昨收与本地库价格），发现复权异常自动触发 `full_rebuild`。
    - [daily_indicators_calc.py](file:///root/dkh/dkh-stock-repo/script/core/daily_indicators_calc.py): **指标引擎**。基于 `pandas_ta` 计算 RSI, KDJ, MACD。
    - [realtime_sync.py](file:///root/dkh/dkh-stock-repo/script/core/realtime_sync.py): **实时同步器**。交易时段内高频刷新全市场快照。
- [script/strategies/](file:///root/dkh/dkh-stock-repo/script/strategies/):
    - [lianghua.py](file:///root/dkh/dkh-stock-repo/script/strategies/lianghua.py): **9 因子静态模型**。用于盘后深度筛选。
    - [realtime_strategy_picker.py](file:///root/dkh/dkh-stock-repo/script/strategies/realtime_strategy_picker.py): **动态评分模型**。盘中实时打分。
- [script/tools/](file:///root/dkh/dkh-stock-repo/script/tools/): 包含交易日检查、历史数据补全等运维脚本。

---

## 📊 数据库 Schema 概览

### 1. `stock_history` (核心数据表)
存储所有历史行情及预计算的技术指标：
- **行情字段**: 开高低收、成交量、成交额、换手率、涨跌幅。
- **财务字段**: PE(TTM), PB, PS, 是否 ST。
- **预计算指标**: `rsi_14`, `k_9_3`, `d_9_3`, `j_9_3`, `macd_dif`, `macd_dea`, `macd_hist`。

### 2. `stock_realtime_full` (实时快照表)
存储盘中高频更新的数据，包括买卖五档、实时量比、内外盘等，每次更新前会 `TRUNCATE` 保证绝对实时。

---

## 🧠 策略逻辑说明

### 1. 静态 9 因子模型 (`lianghua.py`)
必须同时满足以下所有条件：
1. **基础过滤**: 非 ST，非停牌。
2. **超卖识别**: RSI(14) < 35。
3. **趋势金叉**: KDJ 金叉 (K > D) 且 MACD 金叉 (DIF > DEA)。
4. **价格形态**: KDJ J值在 0-100 之间，且价格处于 60 日均线 ±2% 范围内（支撑位校验）。
5. **量价配合**: 今日成交量 > 5 日均量。
6. **估值筛选**: PE(TTM) 在 0-50 之间。
7. **涨幅控制**: 当日涨幅在 -5% 到 10% 之间。

### 2. 实时评分模型 (`realtime_strategy_picker.py`)
对市值在 50亿-200亿 之间的标的进行 5 因子动态评分（每项 2 分，满分 10 分）：
- `f1`: RSI < 35 (超卖)
- `f2`: KDJ 实时金叉 (趋势向上)
- `f3`: 成交量 > 5日均量 (放量)
- `f4`: MACD DIF > DEA (多头)
- `f5`: 价格处于 60日均线支撑位 (±2%)
- **入选门槛**: 总分 >= 6 分。

---

## ⏰ 自动化运维 (Crontab)

系统通过以下定时任务实现全自动流转：

```bash
# 01:30 | 行情同步: 获取 Baostock 数据并修复复权问题
30 01 * * * /root/dkh/myenv/bin/python /root/dkh/dkh-stock-repo/script/core/daily_sync.py >> /root/dkh/dkh-stock-repo/logs/sync.log 2>&1

# 02:30 | 指标计算: 增量回填技术指标
30 02 * * * /root/dkh/myenv/bin/python /root/dkh/dkh-stock-repo/script/core/daily_indicators_calc.py >> /root/dkh/dkh-stock-repo/logs/calc.log 2>&1

# 09:15 | 实时选股: 开启监控并在 15:05 自动退出
15 09 * * * /root/dkh/myenv/bin/python /root/dkh/dkh-stock-repo/script/tools/check_trade_day.py && /root/dkh/myenv/bin/python /root/dkh/dkh-stock-repo/script/core/realtime_sync.py >> /root/dkh/dkh-stock-repo/logs/realtime.log 2>&1
```

---

## �️ 开发者指南

### 环境依赖
- **Python**: 3.12+
- **核心库**: `pandas`, `pandas_ta`, `sqlalchemy`, `baostock`, `requests`
- **虚拟环境**: `/root/dkh/myenv`

### 常用命令
- **手动执行 9 因子选股**:
  ```bash
  /root/dkh/myenv/bin/python /root/dkh/dkh-stock-repo/script/strategies/lianghua.py
  ```
- **查看选股结果**:
  ```sql
  SELECT * FROM dkh.strategy_results ORDER BY created_at DESC;
  ```
