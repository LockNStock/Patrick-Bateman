import yfinance as yf
from backtesting import Backtest, Strategy
import pandas as pd

def calculate_rsi(series, period=14):
    """Calculate Relative Strength Index (RSI) using standard Pandas rolling logic."""
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Define the RSI Swing Strategy for Backtesting
class RsiSwing(Strategy):
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70

    def init(self):
        # Calculate RSI indicator. Wrapping in self.I tracks it for visualization.
        close = pd.Series(self.data.Close)
        self.rsi = self.I(calculate_rsi, close, self.rsi_period)

    def next(self):
        # Buy Signal: RSI enters oversold region (< 30) and no position is held
        if self.rsi[-1] < self.rsi_oversold:
            if not self.position:
                self.buy()
        # Sell Signal: RSI enters overbought region (> 70) and position is held (liquidate)
        elif self.rsi[-1] > self.rsi_overbought:
            if self.position:
                self.position.close()

# Key metrics Chinese translation dictionary
TRANSLATION_DICT = {
    "Start": "回测开始时间",
    "End": "回测结束时间",
    "Duration": "回测总时长",
    "Exposure Time [%]": "市场暴露时间比 [%]",
    "Equity Final [$]": "期末账户净资产 [$]",
    "Equity Peak [$]": "历史最高账户净资产 [$]",
    "Commissions [$]": "累计交易手续费 [$]",
    "Return [%]": "总收益率 [%]",
    "Buy & Hold Return [%]": "买入持有策略收益率 [%]",
    "Return (Ann.) [%]": "年化收益率 [%]",
    "Volatility (Ann.) [%]": "年化波动率 [%]",
    "CAGR [%]": "复合年均增长率 (CAGR) [%]",
    "Sharpe Ratio": "夏普比率 (Sharpe Ratio)",
    "Sortino Ratio": "索提诺比率 (Sortino Ratio)",
    "Calmar Ratio": "卡玛比率 (Calmar Ratio)",
    "Alpha [%]": "阿尔法超额收益 (Alpha) [%]",
    "Beta": "贝塔系统风险 (Beta)",
    "Max. Drawdown [%]": "历史最大回撤 [%]",
    "Avg. Drawdown [%]": "平均单次回撤 [%]",
    "Max. Drawdown Duration": "历史最大回撤持续时间",
    "Avg. Drawdown Duration": "平均回撤持续时间",
    "# Trades": "总交易笔数",
    "Win Rate [%]": "交易胜率 [%]",
    "Best Trade [%]": "单笔最大盈利 [%]",
    "Worst Trade [%]": "单笔最大亏损 [%]",
    "Avg. Trade [%]": "单笔平均收益 [%]",
    "Max. Trade Duration": "单笔最长持仓时间",
    "Avg. Trade Duration": "单笔平均持仓时间",
    "Profit Factor": "利润因子 (Profit Factor)",
    "Expectancy [%]": "交易数学期望 [%]",
    "SQN": "系统品质数 (SQN)",
    "Kelly Criterion": "凯利公式仓位比例",
}

if __name__ == "__main__":
    print("正在从 Yahoo Finance 获取 SPY 的历史数据...")
    # Fetch historical data (using 3 years of daily candles for swing trading)
    ticker = "SPY"
    df = yf.download(ticker, start="2023-01-01", end="2026-01-01")
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    print(f"数据获取成功：共计 {len(df)} 行。")

    # Run backtest with $10,000 initial cash and 0.2% commission
    bt = Backtest(df, RsiSwing, cash=10000, commission=.002, exclusive_orders=True)
    stats = bt.run()
    
    # Translate the performance metrics
    translated_stats = {}
    for key, value in stats.items():
        if key in TRANSLATION_DICT:
            translated_stats[TRANSLATION_DICT[key]] = value
        else:
            if not key.startswith("_"):
                translated_stats[key] = value

    translated_series = pd.Series(translated_stats)

    print("\n--- 历史回测结果: RSI 波段策略 (RSI Swing Strategy) ---")
    print(translated_series)
    
    try:
        bt.plot(filename="trading_assets/backtest_plot.html", open_browser=False)
        print("\n回测交互式图表已成功保存为：'trading_assets/backtest_plot.html'。")
    except Exception as e:
        print(f"\n图表生成失败: {e}")
