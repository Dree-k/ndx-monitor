from playwright.sync_api import sync_playwright
import json
import time
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
import os

# --------------------------配置区--------------------------
# 监控基金列表，自行增删纳指QDII
fund_list = [
    {"code": "021778", "name": "广发纳指100ETF联接人民币F"},
    {"code": "270042", "name": "广发纳斯达克100ETF联接A"},
]
snapshot_file = Path("fund_snapshot.json")
sleep_interval = 3

# 从GitHub Secrets读取环境变量，不要写死在代码！
mail_host = "smtp.qq.com"
mail_port = 465
mail_sender = os.getenv("MAIL_SENDER")
mail_auth_code = os.getenv("MAIL_AUTH_CODE")
mail_receiver = os.getenv("MAIL_RECEIVER")
# -----------------------------------------------------------

def send_email(change_text):
    msg = MIMEText(change_text, "plain", "utf-8")
    msg["Subject"] = "【纳指基金监控告警】检测到申购状态/限额变动"
    msg["From"] = mail_sender
    msg["To"] = mail_receiver
    try:
        server = smtplib.SMTP_SSL(mail_host, mail_port)
        server.login(mail_sender, mail_auth_code)
        server.sendmail(mail_sender, mail_receiver, msg.as_string())
        server.quit()
        print("\n📧 告警邮件发送成功！")
    except Exception as e:
        print(f"\n❌ 邮件发送失败：{str(e)}")

def get_fund_info(code):
    url = f"https://fundf10.eastmoney.com/jjfl_{code}.html"
    with sync_playwright() as p:
        # Linux云端必须增加启动参数
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage"]
        )
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # 抓取交易状态
        try:
            trade_locator = page.locator('xpath=//label[contains(text(),"交易状态：")]/span[1]').first
            trade_state = trade_locator.inner_text().strip() if trade_locator.count() > 0 else "【未匹配】"
        except Exception as e:
            trade_state = f"【抓取异常:{str(e)}】"

        # 抓取日累计申购限额
        try:
            quota_locator = page.locator('xpath=//td[contains(text(),"日累计申购限额")]/following-sibling::td').first
            quota_text = quota_locator.inner_text().strip() if quota_locator.count() > 0 else "【未找到限额】"
        except Exception as e:
            quota_text = f"【抓取异常:{str(e)}】"

        browser.close()
    return {"trade_state": trade_state, "quota": quota_text}

def load_old_snapshot():
    if snapshot_file.exists():
        with open(snapshot_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_snapshot(data):
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    old_snapshot = load_old_snapshot()
    new_snapshot = {}
    change_list = []

    print("===== 开始采集基金数据 =====\n")
    for fund in fund_list:
        code = fund["code"]
        name = fund["name"]
        print(f"正在采集：{name}({code})")
        info = get_fund_info(code)
        new_snapshot[code] = {
            "name": name,
            "trade_state": info["trade_state"],
            "quota": info["quota"]
        }

        if code in old_snapshot:
            old = old_snapshot[code]
            if old["trade_state"] != info["trade_state"] or old["quota"] != info["quota"]:
                change_list.append({
                    "name": name,
                    "code": code,
                    "old_trade": old["trade_state"],
                    "new_trade": info["trade_state"],
                    "old_quota": old["quota"],
                    "new_quota": info["quota"]
                })
        time.sleep(sleep_interval)

    save_snapshot(new_snapshot)

    # 汇总输出
    print("\n===== 本次采集结果汇总 =====")
    for code, item in new_snapshot.items():
        print(f"{item['name']}({code}) | 交易状态：{item['trade_state']} | 日累计申购限额：{item['quota']}")

    if change_list:
        change_text = "🔥 检测到纳指基金状态变动！\n"
        print("\n🔥 检测到状态变动！！")
        for item in change_list:
            line = f"{item['name']}({item['code']})\n交易状态：{item['old_trade']} → {item['new_trade']}\n限额：{item['old_quota']} → {item['new_quota']}\n"
            print(line)
            change_text += line
        send_email(change_text)
    else:
        print("\n✅ 本次扫描：所有基金状态无变化")

if __name__ == "__main__":
    main()
