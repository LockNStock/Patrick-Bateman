import os
import yfinance as yf
import pandas as pd
from datetime import datetime, time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

def load_dotenv():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(base_dir, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        os.environ[parts[0].strip()] = parts[1].strip().strip('"').strip("'")

# Load environment variables from local .env if it exists
load_dotenv()

# 1. Account 2 Credentials (Johnny TwoTimes)
API_KEY = os.getenv("ALPACA_API_KEY_FAST")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_FAST")

# 2. Strategy Configuration for Rapid Testing
SYMBOLS = ["NVDA", "SQQQ"]
RSI_PERIOD = 9
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 75
TRADE_AMOUNT_USD = 50.0  # Fractional order size

def is_market_open_now():
    """Verify if current time falls within Regular Trading Hours (PT: 06:30 - 13:00, Mon-Fri)."""
    now = datetime.now()
    # Check weekend
    if now.weekday() >= 5:
        return False
    
    current_time = now.time()
    start_time = time(6, 30)
    end_time = time(13, 0)
    return start_time <= current_time <= end_time

def calculate_rsi(series, period=9):
    """Calculate Relative Strength Index (RSI) using standard Pandas rolling logic."""
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_fast_strategy_for_symbol(client, symbol, current_positions):
    """Execute 15-minute timeframe RSI strategy for a single symbol."""
    print(f"\n--- [快速试错] 正在分析资产: {symbol} ---")
    
    # 1. Fetch recent 15-minute interval historical data
    try:
        # Using 5 days of 15m bars to ensure we have enough data points for RSI(9)
        df = yf.download(symbol, period="5d", interval="15m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty or len(df) < RSI_PERIOD + 5:
            print(f"[错误] 资产 {symbol} 15m历史数据不足，跳过分析。")
            return
    except Exception as e:
        print(f"[错误] 无法获取资产 {symbol} 的15m数据: {e}")
        return

    # 2. Calculate RSI
    close_prices = df["Close"]
    df["RSI"] = calculate_rsi(close_prices, RSI_PERIOD)
    
    current_price = float(close_prices.iloc[-1])
    current_rsi = float(df["RSI"].iloc[-1])
    print(f"15m收盘价: ${current_price:.2f} | 15m RSI({RSI_PERIOD}): {current_rsi:.2f}")

    # 3. Check Position status
    has_position = symbol in current_positions
    qty_held = current_positions.get(symbol, 0.0)
    if has_position:
        print(f"账户状态: 当前持有 {symbol} 共计 {qty_held} 股。")
    else:
        print(f"账户状态: 当前在 {symbol} 中没有持仓。")

    # 4. Signal Evaluation
    if current_rsi < RSI_OVERSOLD:
        if not has_position:
            print(f"信号触发: 15m RSI ({current_rsi:.2f}) < {RSI_OVERSOLD} (极度超卖)。正在提交买入订单。")
            order_data = MarketOrderRequest(
                symbol=symbol,
                notional=TRADE_AMOUNT_USD,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            try:
                order = client.submit_order(order_data=order_data)
                print(f"买入订单提交成功，订单 ID: {order.id}")
            except Exception as e:
                print(f"买入订单提交失败: {e}")
        else:
            print(f"RSI提示超卖，但当前已持有 {symbol} 仓位。跳过。")

    elif current_rsi > RSI_OVERBOUGHT:
        if has_position:
            print(f"信号触发: 15m RSI ({current_rsi:.2f}) > {RSI_OVERBOUGHT} (极度超买)。正在执行平仓。")
            try:
                client.close_position(symbol)
                print(f"成功平仓并清空 {symbol} 中的所有头寸。")
            except Exception as e:
                print(f"平仓失败: {e}")
        else:
            print(f"RSI提示超买，但当前未持有 {symbol} 仓位。跳过。")
            
    else:
        print(f"无交易信号。15m RSI ({current_rsi:.2f}) 处于中立区间 ({RSI_OVERSOLD} - {RSI_OVERBOUGHT})。")

def main():
    print(f"\n=========================================")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("开始运行 [快速试错] 多资产高频策略 (Timeframe: 15-Min)...")
    print("=========================================")

    # 1. Market Time Check
    if not is_market_open_now():
        print("当前不在美股常规交易时间段内 (PT 06:30 - 13:00)，程序安全退出。")
        print("=========================================")
        return

    # 2. Initialize Alpaca Client
    client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=True)
    
    # 3. Fetch Positions
    current_positions = {}
    try:
        positions = client.get_all_positions()
        for pos in positions:
            current_positions[pos.symbol] = float(pos.qty)
    except Exception as e:
        print(f"获取持仓状态失败: {e}")

    # 4. Evaluate symbols
    for symbol in SYMBOLS:
        run_fast_strategy_for_symbol(client, symbol, current_positions)

    print("=========================================\n")

if __name__ == "__main__":
    main()
