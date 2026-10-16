import requests
import json
import os
import re
import smtplib
from email.mime.text import MIMEText
import time
import random

# ===================== 配置区域，使用Github Secrets =====================
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PWD = os.getenv("EMAIL_PWD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SNAPSHOT_FILE = "qdii_quota_snapshot.json"
MAX_RETRY = 3
# 完整41只场外纳指100 QDII基金清单（来自你提供的列表）
FUND_LIST = [
    {"code":"021778","name":"广发纳斯达克100ETF联接人民币(QDII)F"},
    {"code":"021000","name":"南方纳斯达克100指数发起(QDII)I"},
    {"code":"160213","name":"国泰纳斯达克100指数(QDII)"},
    {"code":"000834","name":"大成纳斯达克100ETF联接(QDII)A"},
    {"code":"006479","name":"广发纳斯达克100ETF联接人民币(QDII)C"},
    {"code":"008971","name":"大成纳斯达克100ETF联接(QDII)C"},
    {"code":"012752","name":"建信纳斯达克100指数(QDII)C人民币"},
    {"code":"016452","name":"南方纳斯达克100指数发起(QDII)A"},
    {"code":"016453","name":"南方纳斯达克100指数发起(QDII)C"},
    {"code":"018966","name":"汇添富纳斯达克100ETF发起式联接(QDII)人民币A"},
    {"code":"018967","name":"汇添富纳斯达克100ETF发起式联接(QDII)人民币C"},
    {"code":"019172","name":"摩根纳斯达克100指数(QDII)人民币A"},
    {"code":"019173","name":"摩根纳斯达克100指数(QDII)人民币C"},
    {"code":"019441","name":"万家纳斯达克100指数发起式(QDII)A"},
    {"code":"019442","name":"万家纳斯达克100指数发起式(QDII)C"},
    {"code":"019547","name":"招商纳斯达克100ETF发起式联接(QDII)A"},
    {"code":"019548","name":"招商纳斯达克100ETF发起式联接(QDII)C"},
    {"code":"019736","name":"宝盈纳斯达克100指数发起(QDII)A人民币"},
    {"code":"019737","name":"宝盈纳斯达克100指数发起(QDII)C人民币"},
    {"code":"021773","name":"汇添富纳斯达克100ETF发起式联接(QDII)人民币E"},
    {"code":"023422","name":"建信纳斯达克100指数(QDII)D人民币"},
    {"code":"270042","name":"广发纳斯达克100ETF联接人民币(QDII)A"},
    {"code":"539001","name":"建信纳斯达克100指数(QDII)A人民币"},
    {"code":"014978","name":"华安纳斯达克100ETF联接(QDII)C"},
    {"code":"019524","name":"华泰柏瑞纳斯达克100ETF发起式联接(QDII)A"},
    {"code":"019525","name":"华泰柏瑞纳斯达克100ETF发起式联接(QDII)C"},
    {"code":"022664","name":"华泰柏瑞纳斯达克100ETF发起式联接(QDII)I"},
    {"code":"040046","name":"华安纳斯达克100ETF联接(QDII)A"},
    {"code":"022525","name":"天弘纳斯达克100指数发起(QDII)D"},
    {"code":"012870","name":"易方达纳斯达克100ETF联接(QDII-LOF)C(人民币)"},
    {"code":"015299","name":"华夏纳斯达克100ETF发起式联接(QDII)A人民币"},
    {"code":"015300","name":"华夏纳斯达克100ETF发起式联接(QDII)C"},
    {"code":"016055","name":"博时纳斯达克100ETF发起式联接(QDII)A人民币"},
    {"code":"016057","name":"博时纳斯达克100ETF发起式联接(QDII)C人民币"},
    {"code":"016532","name":"嘉实纳斯达克100ETF发起联接(QDII)A人民币"},
    {"code":"016533","name":"嘉实纳斯达克100ETF发起联接(QDII)C人民币"},
    {"code":"018043","name":"天弘纳斯达克100指数发起(QDII)A"},
    {"code":"018044","name":"天弘纳斯达克100指数发起(QDII)C"},
    {"code":"021838","name":"嘉实纳斯达克100ETF发起联接(QDII)I人民币"},
    {"code":"024237","name":"博时纳斯达克100ETF发起式联接(QDII)I人民币"},
    {"code":"161130","name":"易方达纳斯达克100ETF联接(QDII-LOF)A(人民币)"},
]
# ========================================================================

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

def get_fund_quota_info(fund_code):
    """抓取天天基金jjfl交易状态页面，提取申购状态、日累计申购限额"""
    url = f"https://fundf10.eastmoney.com/jjfl_{fund_code}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://fundf10.eastmoney.com/"
    }
    for retry in range(MAX_RETRY):
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            resp.encoding = "utf-8"
            html_text = resp.text

            # 正则提取申购状态
            status_pattern = re.search(r'申购状态[:：](.*?)(?=赎回状态)', html_text)
            status = status_pattern.group(1).strip() if status_pattern else "未知"

            # 正则提取日累计申购限额
            quota_pattern = re.search(r'日累计申购限额[:：](.*?)(?=</td>)', html_text)
            quota = quota_pattern.group(1).strip() if quota_pattern else "未知"

            return {"status": status, "quota": quota}
        except Exception as e:
            print(f"⚠️ 基金{fund_code}拉取失败，重试{retry+1}: {str(e)}")
            time.sleep(1.2)
    return {"status": "获取失败", "quota": "获取失败"}

def load_old_snapshot():
    """读取上一次快照"""
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_snapshot(data):
    """保存本次快照"""
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("===== 场外纳指100 QDII限额监控启动 =====")
    old_snapshot = load_old_snapshot()
    new_snapshot = {}
    change_list = []
    all_fund_lines = []
    available_fund_lines = []

    # 循环抓取全部基金
    for fund in FUND_LIST:
        code = fund["code"]
        name = fund["name"]
        res = get_fund_quota_info(code)
        new_snapshot[code] = {
            "name": name,
            "status": res["status"],
            "quota": res["quota"]
        }
        line_all = f"{code:<8}{name:<42}{res['status']:<12}{res['quota']}"
        all_fund_lines.append(line_all)
        # 筛选可申购基金（开放申购 / 限大额）
        if res["status"] in ["开放申购", "限大额"]:
            line_available = f"{code:<8}{name:<42}{res['quota']}"
            available_fund_lines.append(line_available)
        print(line_all)

        # 对比历史快照，判断变动
        if code in old_snapshot:
            old_status = old_snapshot[code]["status"]
            old_quota = old_snapshot[code]["quota"]
            new_status = res["status"]
            new_quota = res["quota"]
            # 条件1：暂停申购 → 变成可申购（限大额/开放申购）
            if old_status == "暂停申购" and new_status in ["限大额", "开放申购"]:
                change_list.append(f"✅【额度放开】{name}({code})：{old_status} → {new_status}，限额：{new_quota}")
            # 条件2：可申购状态下，限额金额发生变动
            if old_status in ["限大额", "开放申购"] and new_status in ["限大额", "开放申购"]:
                if old_quota != new_quota:
                    change_list.append(f"📌【限额调整】{name}({code})：{old_quota} → {new_quota}")
        # 每只基金抓取完随机延时，防止反爬
        time.sleep(random.uniform(0.8,2.2))

    # ========== 组装邮件正文 ==========
    mail_sections = []
    mail_sections.append("【纳指QDII限额监控日报】")
    mail_sections.append("="*60)

    # 区块1：今日可申购基金清单
    mail_sections.append("🔥今日可申购基金清单")
    mail_sections.append(f"{'代码':<8}{'基金名称':<42}{'日累计申购限额'}")
    mail_sections.append("-"*60)
    if available_fund_lines:
        mail_sections.extend(available_fund_lines)
    else:
        mail_sections.append("今日没有可申购基金（全部暂停申购/获取失败）")

    mail_sections.append("\n"+"="*60)
    # 区块2：变动列表
    mail_sections.append("📌相比上次快照变动列表")
    mail_sections.append("-"*60)
    if change_list:
        mail_sections.extend(change_list)
    else:
        mail_sections.append("今日无状态放开、无可申购基金限额变动")

    mail_sections.append("\n"+"="*60)
    # 区块3：全部基金完整汇总表
    mail_sections.append("📋全部基金完整汇总（含暂停申购、拉取失败）")
    mail_sections.append(f"{'代码':<8}{'基金名称':<42}{'申购状态':<12}{'日累计申购限额'}")
    mail_sections.append("-"*60)
    mail_sections.extend(all_fund_lines)

    mail_sections.append("\n备注：数据来源天天基金代销渠道；下单前请务必以APP页面实际可购买额度为准！")
    mail_body = "\n".join(mail_sections)
    send_email("【纳指QDII限额监控日报】", mail_body)
    save_snapshot(new_snapshot)
    print("===== QDII限额监控任务结束 =====")

if __name__ == "__main__":
    main()
