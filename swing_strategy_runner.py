import os
import yfinance as yf
import pandas as pd
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

# 1. Credentials Configuration
API_KEY = os.getenv("ALPACA_API_KEY_SLOW")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_SLOW")

SYMBOL = "SPY"
RSI_PERIOD = 14
RSI_OVERSOLD = 30  # Buy signal threshold
RSI_OVERBOUGHT = 70  # Sell signal threshold
TRADE_AMOUNT_USD = 50.0  # Cost per trade (Fractional swing size)

def calculate_rsi(series, period=14):
    """Calculate Relative Strength Index (RSI) using standard Pandas rolling logic."""
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    print(f"开始运行 {SYMBOL} 的波段交易策略...")
    
    # 2. Initialize Alpaca Client
    client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=True)
    
    # 3. Fetch Recent Historical Data
    print(f"正在获取 {SYMBOL} 的最新历史数据...")
    df = yf.download(SYMBOL, period="2mo", interval="1d")
    
    # Flatten multi-index columns if present (from yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    if df.empty or len(df) < RSI_PERIOD + 5:
        print("[错误] 历史数据不足，无法计算 RSI 指标。")
        return

    # Calculate RSI
    close_prices = df["Close"]
    df["RSI"] = calculate_rsi(close_prices, RSI_PERIOD)
    
    # Get current state
    current_price = float(close_prices.iloc[-1])
    current_rsi = float(df["RSI"].iloc[-1])
    print(f"当前价格: ${current_price:.2f} | 当前 RSI({RSI_PERIOD}): {current_rsi:.2f}")
    
    # 4. Check Current Positions on Alpaca
    has_position = False
    qty_held = 0.0
    try:
        position = client.get_open_position(SYMBOL)
        has_position = True
        qty_held = float(position.qty)
        print(f"当前持仓: 持有 {qty_held} 股 {SYMBOL}。")
    except Exception:
        print(f"当前在 {SYMBOL} 中没有持仓。")

    # 5. Signal Evaluation & Execution
    # Buy Signal: RSI < Oversold and no existing position
    if current_rsi < RSI_OVERSOLD:
        if not has_position:
            print(f"信号触发: RSI ({current_rsi:.2f}) < {RSI_OVERSOLD} (超卖)。正在提交买入订单。")
            order_data = MarketOrderRequest(
                symbol=SYMBOL,
                notional=TRADE_AMOUNT_USD,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            try:
                order = client.submit_order(order_data=order_data)
                print(f"买入订单已提交，订单 ID: {order.id}")
            except Exception as e:
                print(f"买入订单提交失败: {e}")
        else:
            print("RSI 提示超卖，但当前已持有仓位。未执行任何操作。")

    # Sell Signal: RSI > Overbought and has existing position
    elif current_rsi > RSI_OVERBOUGHT:
        if has_position:
            print(f"信号触发: RSI ({current_rsi:.2f}) > {RSI_OVERBOUGHT} (超买)。正在执行平仓操作。")
            try:
                # Liquidate the position
                client.close_position(SYMBOL)
                print(f"成功平仓 {SYMBOL} 中的所有头寸。")
            except Exception as e:
                print(f"平仓失败: {e}")
        else:
            print("RSI 提示超买，但当前没有持仓。未执行任何操作。")
            
    else:
        print(f"未触发任何信号。RSI ({current_rsi:.2f}) 处于中立区间 ({RSI_OVERSOLD} - {RSI_OVERBOUGHT})。")

if __name__ == "__main__":
    main()
