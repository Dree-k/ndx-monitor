import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
import time

# ===================== 配置区（使用Github Secrets，不要硬编码！） =====================
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PWD = os.getenv("EMAIL_PWD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SNAPSHOT_FILE = "qdii_quota_snapshot.json"
MAX_RETRY = 3
# 全部场外纳指100 QDII联接基金列表
FUND_LIST = [
    {"code":"270042","name":"广发纳指100联接A"},
    {"code":"006479","name":"广发纳指100联接C"},
    {"code":"021778","name":"广发纳指100联接F"},
    {"code":"040046","name":"华安纳指100联接A"},
    {"code":"014978","name":"华安纳指100联接C"},
    {"code":"000834","name":"大成纳指100联接A"},
    {"code":"008971","name":"大成纳指100联接C"},
    {"code":"012870","name":"易方达纳指100联接C"},
    {"code":"016055","name":"博时纳指100联接A"},
    {"code":"018966","name":"汇添富纳指100联接A"},
    {"code":"019524","name":"华泰柏瑞纳指100联接A"},
]
# =====================================================================================

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
        print("✅ QDII限额邮件发送成功")
    except Exception as e:
        print(f"❌ QDII限额邮件发送失败: {str(e)}")

def get_fund_subscribe_status(fund_code):
    """调用天天基金接口，获取单只基金申购状态+限额"""
    url = f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={fund_code}&topline=10&year=&month="
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer":"https://fundf10.eastmoney.com/"
    }
    for retry in range(MAX_RETRY):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = "utf-8"
            text = resp.text
            # 解析申购状态文本
            if "暂停申购" in text:
                return {"status":"暂停申购","limit":0}
            elif "限制申购" in text or "单日" in text:
                # 简易提取限额，文字原样返回
                return {"status":"限额申购","limit":"待看公告"}
            else:
                return {"status":"开放申购","limit":"不限额"}
        except Exception as e:
            print(f"⚠️ 基金{fund_code}拉取失败，重试{retry+1}: {str(e)}")
            time.sleep(2)
    return {"status":"获取失败","limit":None}

def load_old_snapshot():
    """读取上一次保存的限额快照"""
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_snapshot(data):
    """保存本次快照到本地json"""
    with open(SNAPSHOT_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

def main():
    print("===== 场外纳指100 QDII限额监控启动 =====")
    old_data = load_old_snapshot()
    new_data = {}
    change_list = []
    output_lines = []
    output_lines.append("【场外纳指100 QDII 申购限额日报】")
    output_lines.append("-" * 50)

    for fund in FUND_LIST:
        code = fund["code"]
        name = fund["name"]
        res = get_fund_subscribe_status(code)
        new_data[code] = {
            "name":name,
            "status":res["status"],
            "limit":res["limit"]
        }
        print(f"{code} {name} : {res['status']} | {res['limit']}")
        # 和昨日对比，判断变动
        if code in old_data:
            old_status = old_data[code]["status"]
            if old_status != res["status"]:
                change_list.append(f"{name}({code})：【{old_status}】→【{res['status']}】")
        line = f"{code:8} {name:<18} | {res['status']:<8} | {res['limit']}"
        output_lines.append(line)

    output_lines.append("-" * 50)
    if change_list:
        output_lines.append("🔥【今日状态发生变动的基金】")
        for item in change_list:
            output_lines.append(item)
    else:
        output_lines.append("✅ 今日所有基金申购状态无变动")
    output_lines.append("\n提示：限额文本仅为粗略抓取，下单前务必在代销平台页面核对真实单日申购上限！")
    mail_content = "\n".join(output_lines)
    # 发送邮件
    send_email("【纳指QDII限额监控日报】", mail_content)
    # 保存最新快照
    save_snapshot(new_data)
    print("===== QDII限额监控任务结束 =====")

if __name__ == "__main__":
    main()
