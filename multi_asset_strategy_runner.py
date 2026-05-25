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

# 2. Portfolio Configuration
# We select a diversified pool of high-liquidity assets (ETFs + leading blue-chip tech stocks)
SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]
RSI_PERIOD = 14
RSI_OVERSOLD = 30  # Buy signal threshold
RSI_OVERBOUGHT = 70  # Sell/Liquidate signal threshold
TRADE_AMOUNT_USD = 50.0  # Allocation amount per trade using fractional shares

def calculate_rsi(series, period=14):
    """Calculate Relative Strength Index (RSI) using standard Pandas rolling logic."""
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_strategy_for_symbol(client, symbol, current_positions):
    """Evaluate and execute the RSI Swing Strategy for a single symbol."""
    print(f"\n--- 正在分析资产: {symbol} ---")
    
    # 1. Fetch Historical Data
    try:
        df = yf.download(symbol, period="2mo", interval="1d", progress=False)
        # Flatten multi-index columns if present (from yfinance)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty or len(df) < RSI_PERIOD + 5:
            print(f"[错误] 资产 {symbol} 历史数据不足，跳过分析。")
            return
    except Exception as e:
        print(f"[错误] 无法获取资产 {symbol} 的数据: {e}")
        return

    # 2. Calculate RSI
    close_prices = df["Close"]
    df["RSI"] = calculate_rsi(close_prices, RSI_PERIOD)
    
    current_price = float(close_prices.iloc[-1])
    current_rsi = float(df["RSI"].iloc[-1])
    print(f"当前收盘价: ${current_price:.2f} | 当前 RSI({RSI_PERIOD}): {current_rsi:.2f}")

    # 3. Check Current Position status
    has_position = symbol in current_positions
    qty_held = current_positions.get(symbol, 0.0)
    if has_position:
        print(f"账户状态: 当前持有 {symbol} 共计 {qty_held} 股。")
    else:
        print(f"账户状态: 当前在 {symbol} 中没有持仓。")

    # 4. Signal Evaluation & Execution
    # Buy Signal: RSI < Oversold and no existing position
    if current_rsi < RSI_OVERSOLD:
        if not has_position:
            print(f"信号触发: RSI ({current_rsi:.2f}) < {RSI_OVERSOLD} (超卖)。正在提交买入订单。")
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
            print(f"RSI 提示 {symbol} 超卖，但当前已持有仓位。跳过交易。")

    # Sell Signal: RSI > Overbought and has existing position
    elif current_rsi > RSI_OVERBOUGHT:
        if has_position:
            print(f"信号触发: RSI ({current_rsi:.2f}) > {RSI_OVERBOUGHT} (超买)。正在执行平仓操作。")
            try:
                client.close_position(symbol)
                print(f"成功平仓并清空 {symbol} 中的所有头寸。")
            except Exception as e:
                print(f"平仓失败: {e}")
        else:
            print(f"RSI 提示 {symbol} 超买，但当前未持有仓位。跳过交易。")
            
    else:
        print(f"未触发交易信号。RSI ({current_rsi:.2f}) 处于中立区间 ({RSI_OVERSOLD} - {RSI_OVERBOUGHT})。")

def main():
    print("=========================================")
    print("开始运行 多资产波段交易策略 (Multi-Asset Swing Strategy)...")
    print("=========================================")
    
    # Initialize Alpaca Client
    client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=True)
    
    # Fetch all currently held open positions
    print("正在查询当前账户持仓状态...")
    current_positions = {}
    try:
        positions = client.get_all_positions()
        for pos in positions:
            current_positions[pos.symbol] = float(pos.qty)
        print(f"当前账户共持有 {len(current_positions)} 个资产的头寸。")
    except Exception as e:
        print(f"获取持仓状态失败 (若为首次运行且无持仓，此警告可忽略): {e}")

    # Evaluate signal for each asset in the portfolio
    for symbol in SYMBOLS:
        run_strategy_for_symbol(client, symbol, current_positions)
        
    print("\n=========================================")
    print("多资产交易策略分析运行结束。")
    print("=========================================")

if __name__ == "__main__":
    main()
