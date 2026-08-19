"""
مراقب فتح باب التسجيل - جامعة الأزهر (PGS) - نسخة خفيفة لـ GitHub Actions
==========================================================================
النسخة دي مش محتاجة متصفح كروم خالص - بتبعت طلبات مباشرة للسيرفر
زي ما المتصفح بيعمل بالظبط، وده يخليها تشتغل بسهولة جدول زمني على GitHub Actions.

البيانات الحساسة (الإيميل/الباسورد/مفاتيح واتساب) مش بتتحط جوه الكود خالص -
بتتقرا من "GitHub Secrets" وقت التشغيل (هنشرح إزاي نظبطها في الخطوة الجاية).
"""

import os
import sys
import re
import logging
import requests
import urllib3
from bs4 import BeautifulSoup

# موقع الأزهر شهادة الأمان بتاعته ناقصة جزء (intermediate certificate) من عندهم -
# ده بيخلي بايثون يرفض الاتصال بينما المتصفح بيتغاضى عنه. بنعطل التحقق هنا كحل عملي.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("azhar_watcher")

LOGIN_URL = "https://pgs.alazharuniversity.org/web/login"
NEW_REQUEST_URL = "https://pgs.alazharuniversity.org/my/requests/new"

# البيانات دي بتتقرا من GitHub Secrets (متغيرات بيئة) - مش هتتحط هنا خالص
AZHAR_EMAIL = os.environ.get("AZHAR_EMAIL")
AZHAR_PASSWORD = os.environ.get("AZHAR_PASSWORD")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # رقم Sandbox الافتراضي

# أرقام المستلمين - كل رقم لازم يكون بالصيغة: whatsapp:+971xxxxxxxxx
WHATSAPP_RECIPIENTS = [
    v for v in [os.environ.get("WHATSAPP_TO_1"), os.environ.get("WHATSAPP_TO_2")] if v
]


def send_whatsapp_alert():
    message = (
        "🚨 تسجيل الماجستير/الدكتوراه فتح دلوقتي على موقع الأزهر!\n"
        "ادخلي حالًا: https://pgs.alazharuniversity.org/web/login"
    )
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        log.error("بيانات Twilio مش موجودة - تأكدي من GitHub Secrets")
        return
    if not WHATSAPP_RECIPIENTS:
        log.error("مفيش أرقام مستلمين مضافة (WHATSAPP_TO_1 / WHATSAPP_TO_2)")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    for to_number in WHATSAPP_RECIPIENTS:
        try:
            resp = requests.post(
                url,
                data={"From": TWILIO_WHATSAPP_FROM, "To": to_number, "Body": message},
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                timeout=15,
            )
            log.info(f"إرسال واتساب لـ {to_number} -> {resp.status_code}")
            if resp.status_code >= 300:
                log.error(f"رد Twilio: {resp.text}")
        except Exception as e:
            log.error(f"فشل إرسال واتساب لـ {to_number}: {e}")


def get_csrf_token(session):
    resp = session.get(LOGIN_URL, timeout=20)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    if not match:
        raise RuntimeError("مقدرتش ألاقي csrf_token في صفحة الدخول")
    return match.group(1)


def login(session):
    csrf_token = get_csrf_token(session)
    payload = {
        "csrf_token": csrf_token,
        "login": AZHAR_EMAIL,
        "password": AZHAR_PASSWORD,
        "redirect": "",
    }
    resp = session.post(LOGIN_URL, data=payload, timeout=20, allow_redirects=True)
    if "login" in resp.url and "web/login" in resp.url:
        raise RuntimeError("فشل تسجيل الدخول - راجعي الإيميل/الباسورد")
    log.info("تسجيل الدخول تم بنجاح")


def check_registration_open(session):
    resp = session.get(NEW_REQUEST_URL, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    select_el = soup.find("select", {"name": "faculty_id"})
    if not select_el:
        log.warning("مقدرتش ألاقي select[name='faculty_id'] - الصفحة ممكن تكون اتغيرت")
        return False
    options = select_el.find_all("option")
    real_options = [o for o in options if o.get_text(strip=True) and "select" not in o.get_text(strip=True).lower()]
    log.info(f"عدد خيارات الكلية الظاهرة: {len(real_options)}")
    return len(real_options) > 0


def main():
    if not AZHAR_EMAIL or not AZHAR_PASSWORD:
        log.error("AZHAR_EMAIL أو AZHAR_PASSWORD مش موجودين - تأكدي من GitHub Secrets")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    session.verify = False  # موقع الأزهر ناقصه جزء من شهادة الأمان (شوفي التعليق فوق)

    try:
        login(session)
        is_open = check_registration_open(session)
    except Exception as e:
        log.error(f"حصل خطأ: {e}")
        sys.exit(1)

    if is_open:
        log.info("✅ التسجيل مفتوح! جاري إرسال تنبيه واتساب...")
        send_whatsapp_alert()
    else:
        log.info("لسه مقفول.")


if __name__ == "__main__":
    main()
