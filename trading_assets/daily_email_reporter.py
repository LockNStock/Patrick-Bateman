import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from alpaca.trading.client import TradingClient

# 1. Dynamic Path Resolution & Env Loading
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "trading_assets", "email_config.json")
LOG_PATH = os.path.join(BASE_DIR, "trading_assets", "strategy.log")

def load_dotenv():
    dotenv_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        os.environ[parts[0].strip()] = parts[1].strip().strip('"').strip("'")

load_dotenv()

ACCOUNTS = [
    {
        "name": "账户 1 (burnner1 - 慢速)",
        "key": os.getenv("ALPACA_API_KEY_SLOW"),
        "secret": os.getenv("ALPACA_SECRET_KEY_SLOW")
    },
    {
        "name": "账户 2 (Johnny TwoTimes - 15m高频)",
        "key": os.getenv("ALPACA_API_KEY_FAST"),
        "secret": os.getenv("ALPACA_SECRET_KEY_FAST")
    },
    {
        "name": "账户 3 (Teddy KGB - 稳健对冲)",
        "key": os.getenv("ALPACA_API_KEY_HEDGED"),
        "secret": os.getenv("ALPACA_SECRET_KEY_HEDGED")
    }
]

def load_email_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        # Check if default placeholders are unchanged
        if "your_sender_email" in config.get("sender_email", ""):
            return None
        return config
    except Exception:
        return None

def fetch_portfolio_data():
    portfolio = []
    for acc in ACCOUNTS:
        try:
            client = TradingClient(api_key=acc["key"], secret_key=acc["secret"], paper=True)
            account_info = client.get_account()
            positions = client.get_all_positions()
            
            equity = float(account_info.equity)
            last_equity = float(account_info.last_equity) if account_info.last_equity else equity
            today_pnl = equity - last_equity
            
            pos_list = []
            for p in positions:
                pos_list.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "value": float(p.market_value),
                    "pl": float(p.unrealized_pl),
                    "plpc": float(p.unrealized_plpc) * 100
                })
                
            portfolio.append({
                "name": acc["name"],
                "equity": equity,
                "cash": float(account_info.cash),
                "today_pnl": today_pnl,
                "positions": pos_list
            })
        except Exception as e:
            print(f"获取 {acc['name']} 数据失败: {e}")
    return portfolio

def build_html_report(portfolio):
    today_str = datetime.now().strftime("%Y-%m-%d")
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #333; line-height: 1.6; }}
            h2 {{ color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            th {{ background-color: #f7fafc; color: #4a5568; font-weight: 600; }}
            .positive {{ color: #38a169; font-weight: bold; }}
            .negative {{ color: #e53e3e; font-weight: bold; }}
            .neutral {{ color: #718096; }}
            .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        </style>
    </head>
    <body>
        <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2b6cb0; text-align: center; margin-bottom: 30px;">量化交易账户每日汇总报告</h1>
            <p style="text-align: right; color: #718096;">报告日期: {today_str}</p>
    """
    
    for acc in portfolio:
        pnl_class = "positive" if acc["today_pnl"] > 0 else ("negative" if acc["today_pnl"] < 0 else "neutral")
        pnl_sign = "+" if acc["today_pnl"] > 0 else ""
        
        html += f"""
        <div class="card">
            <h2>{acc['name']}</h2>
            <p><b>总资产 (Equity):</b> ${acc['equity']:,.2f}</p>
            <p><b>现金余额 (Cash):</b> ${acc['cash']:,.2f}</p>
            <p><b>今日盈亏 (Today P&L):</b> <span class="{pnl_class}">{pnl_sign}${acc['today_pnl']:,.2f}</span></p>
            
            <h3>当前持有头寸</h3>
        """
        
        if not acc["positions"]:
            html += "<p class='neutral'>当前空仓 (100% 现金观望)</p>"
        else:
            html += """
            <table>
                <thead>
                    <tr>
                        <th>资产代码 (Symbol)</th>
                        <th>持有股数 (Qty)</th>
                        <th>当前市值 (Value)</th>
                        <th>浮动盈亏 (Unrealized P&L)</th>
                    </tr>
                </thead>
                <tbody>
            """
            for pos in acc["positions"]:
                pos_pnl_class = "positive" if pos["pl"] > 0 else ("negative" if pos["pl"] < 0 else "neutral")
                pos_pnl_sign = "+" if pos["pl"] > 0 else ""
                html += f"""
                    <tr>
                        <td><b>{pos['symbol']}</b></td>
                        <td>{pos['qty']:.6f}</td>
                        <td>${pos['value']:,.2f}</td>
                        <td><span class="{pos_pnl_class}">{pos_pnl_sign}${pos['pl']:,.2f} ({pos['plpc']:.2f}%)</span></td>
                    </tr>
                """
            html += """
                </tbody>
            </table>
            """
        html += "</div>"
        
    html += """
            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin-top: 40px;">
            <p style="text-align: center; font-size: 12px; color: #a0aec0;">本报告由 Patrick Bateman 量化交易工作台自动生成并发送。</p>
        </div>
    </body>
    </html>
    """
    return html

def send_email(config, html_content):
    sender = config["sender_email"]
    receiver = config["receiver_email"]
    subject = f"量化交易每日报告 - {datetime.now().strftime('%Y-%m-%d')}"
    
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        # Connect to SMTP server (SSL setup)
        server = smtplib.SMTP_SSL(config["smtp_server"], int(config["smtp_port"]))
        server.login(sender, config["sender_password"])
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 每日总结邮件成功发送至: {receiver}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 邮件发送失败: {e}")

def main():
    config = load_email_config()
    if not config:
        print("未检测到已配置的邮件配置文件 email_config.json 或仍处于占位默认值，已跳过发送邮件流程。")
        return
        
    print("正在抓取各账户最新表现并生成邮件报告...")
    portfolio = fetch_portfolio_data()
    if not portfolio:
        print("未获取到任何账户的交易数据。")
        return
        
    html_content = build_html_report(portfolio)
    send_email(config, html_content)

if __name__ == "__main__":
    main()
