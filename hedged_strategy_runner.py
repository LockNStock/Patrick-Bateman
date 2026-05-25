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

# 1. Account 3 Credentials (Teddy KGB)
API_KEY = os.getenv("ALPACA_API_KEY_HEDGED")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY_HEDGED")

# 2. Portfolio Assets & Parameters
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
TRADE_AMOUNT_USD = 50.0  # Allocation amount per trade

def calculate_rsi(series, period=14):
    """Calculate Relative Strength Index (RSI) using standard Pandas rolling logic."""
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_regime():
    """Determine macro market trend based on 200-day Simple Moving Average (SMA) of SPY."""
    try:
        # Fetch 1 year of daily data to ensure we have enough data for 200 SMA
        df = yf.download("SPY", period="1y", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        close_prices = df["Close"]
        current_price = float(close_prices.iloc[-1])
        sma_200 = float(close_prices.rolling(window=200).mean().iloc[-1])
        
        is_bull = current_price > sma_200
        print(f"\n--- [大盘趋势分析] ---")
        print(f"SPY 当前收盘价: ${current_price:.2f} | 200日均线 (SMA 200): ${sma_200:.2f}")
        print(f"大盘状态判断: {'【牛市多头格局】(Bull Market)' if is_bull else '【熊市空头格局】(Bear Market)'}")
        return is_bull
    except Exception as e:
        print(f"[错误] 无法获取大盘状态数据，默认判定为牛市: {e}")
        return True

def run_hedged_strategy_for_symbol(client, symbol, is_bull_market, current_positions):
    """Evaluate and execute orders with Wall Street trend filters and hedging logic."""
    print(f"\n--- [对冲沙盒] 正在分析资产: {symbol} ---")
    
    # 1. Fetch Daily Data
    try:
        df = yf.download(symbol, period="2mo", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty or len(df) < RSI_PERIOD + 5:
            print(f"[错误] {symbol} 历史数据不足，跳过。")
            return
    except Exception as e:
        print(f"[错误] 无法获取 {symbol} 的数据: {e}")
        return

    # 2. Calculate RSI
    close_prices = df["Close"]
    df["RSI"] = calculate_rsi(close_prices, RSI_PERIOD)
    current_price = float(close_prices.iloc[-1])
    current_rsi = float(df["RSI"].iloc[-1])
    print(f"当前价格: ${current_price:.2f} | RSI({RSI_PERIOD}): {current_rsi:.2f}")

    has_position = symbol in current_positions
    qty_held = current_positions.get(symbol, 0.0)

    # 3. Apply Wall Street Trend Filters
    # Define directional permissions based on trend regime
    allowed_to_buy = True
    
    if symbol == "SPY" and not is_bull_market:
        # Block buying long ETF SPY during macro bear market
        allowed_to_buy = False
        print(f"【趋势风控】大盘处于熊市格局，禁止做多标的 {symbol}。")
        
    elif symbol == "SH" and is_bull_market:
        # Block buying short ETF SH during macro bull market to avoid volatility decay
        allowed_to_buy = False
        print(f"【趋势风控】大盘处于牛市格局，禁止做空/买入对冲资产 {symbol}。")

    # 4. Signal Execution
    # Buy Signal
    if current_rsi < RSI_OVERSOLD:
        if not has_position:
            if allowed_to_buy:
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
                print(f"RSI 提示超卖，但受【趋势风控】限制禁止买入 {symbol}。")
        else:
            print(f"RSI 提示超卖，但当前已持有 {symbol} 仓位。跳过。")

    # Sell Signal (Liquidate)
    elif current_rsi > RSI_OVERBOUGHT:
        if has_position:
            print(f"信号触发: RSI ({current_rsi:.2f}) > {RSI_OVERBOUGHT} (超买)。正在执行平仓。")
            try:
                client.close_position(symbol)
                print(f"成功平仓并清空 {symbol} 中的所有头寸。")
            except Exception as e:
                print(f"平仓失败: {e}")
        else:
            print(f"RSI 提示超买，但当前未持有 {symbol} 仓位。跳过。")
            
    else:
        print(f"无交易信号。RSI ({current_rsi:.2f}) 处于中立区间 ({RSI_OVERSOLD} - {RSI_OVERBOUGHT})。")

def main():
    print("=========================================")
    print("开始运行 [Teddy KGB] 华尔街改良版对冲策略 (Hedged Swing Strategy)...")
    print("=========================================")
    
    # 1. Initialize Client
    client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, paper=True)
    
    # 2. Get Open Positions
    current_positions = {}
    try:
        positions = client.get_all_positions()
        for pos in positions:
            current_positions[pos.symbol] = float(pos.qty)
    except Exception as e:
        print(f"获取持仓状态失败: {e}")

    # 3. Analyze Macro Trend
    is_bull = get_market_regime()

    # 4. Evaluate Portfolio Assets
    # SPY (Long), SH (1x Short), GLD (Safe Haven Gold)
    for symbol in ["SPY", "SH", "GLD"]:
        run_hedged_strategy_for_symbol(client, symbol, is_bull, current_positions)

    print("\n=========================================")
    print("对冲交易策略分析运行结束。")
    print("=========================================")

if __name__ == "__main__":
    main()
