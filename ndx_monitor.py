import yfinance as yf
import json
import os
import smtplib
from email.mime.text import MIMEText
import time
# ===================== 配置区（变量从Github Secrets读取，不要直接写在这里！） =====================
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PWD = os.getenv("EMAIL_PWD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
THRESHOLDS = {
    "8%": 0.08,
    "12%": 0.12,
    "18%": 0.18
}
DATA_FILE = "ndx_high.json"
MAX_RETRY = 3  # 拉取行情失败重试次数
# ================================================================================================
def send_email(subject, content):
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=10)
        server.login(EMAIL_SENDER, EMAIL_PWD)
        server.send_message(msg)
        server.quit()
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)}")
def load_high():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["high"]
    return 0
def save_high(high_val):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"high": high_val}, f)
def get_ndx_data():
    ticker = yf.Ticker("^NDX")
    for retry in range(MAX_RETRY):
        try:
            hist = ticker.history(period="2d")
            if len(hist) >= 1:
                close_price = float(hist["Close"].iloc[-1])
                return close_price
        except Exception as e:
            print(f"⚠️ 获取行情失败，第{retry+1}次重试: {str(e)}")
            time.sleep(3)
    return None
def main():
    print("===== 纳指100回撤监控开始运行 =====")
    close_price = get_ndx_data()
    if close_price is None:
        print("❌ 多次尝试，行情获取失败，终止本次运行")
        return
    print(f"NDX最新收盘点位: {close_price:.2f}")
    last_high = load_high()
    print(f"当前记录阶段高点: {last_high:.2f}")
    # 创新高，更新高点
    if close_price > last_high:
        last_high = close_price
        save_high(last_high)
        print("✅ 创出新高，已更新阶段高点！")
    drawdown = (last_high - close_price) / last_high
    print(f"当前回撤幅度: {drawdown:.2%}")
    trigger_list = []
    for name, val in THRESHOLDS.items():
        if drawdown >= val:
            trigger_list.append(name)
    if trigger_list:
        # 【修复】提前把列表拼接成字符串，不要在模板内写Python代码
        trigger_text = ",".join(trigger_list)
        content = """
【纳指100回撤触发提醒】
阶段高点：{last_high:.2f}
当前收盘：{close_price:.2f}
当前回撤：{drawdown:.2%}
已触发加仓档位：{trigger_text}
⚠️ 收到提醒后操作检查清单：
1. 打开集思录，查看场内纳指ETF溢价率
2. 溢价＜5%，才考虑买入；溢价>5%，只记录，不买入！
"""
        # format参数增加 trigger_text，删掉 trigger_list
        content = content.format(last_high=last_high, close_price=close_price, drawdown=drawdown, trigger_text=trigger_text)
        send_email("【纳指100加仓提醒】", content)
    else:
        print("暂未触发任何加仓档位")
if __name__ == "__main__":
    main()
