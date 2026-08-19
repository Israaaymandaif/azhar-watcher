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
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("azhar_watcher")

LOGIN_URL = "https://pgs.alazharuniversity.org/web/login"
NEW_REQUEST_URL = "https://pgs.alazharuniversity.org/my/requests/new"

# البيانات دي بتتقرا من GitHub Secrets (متغيرات بيئة) - مش هتتحط هنا خالص
AZHAR_EMAIL = os.environ.get("AZHAR_EMAIL")
AZHAR_PASSWORD = os.environ.get("AZHAR_PASSWORD")

CALLMEBOT_RECIPIENTS = [
    {"phone": os.environ.get("PHONE_1"), "apikey": os.environ.get("APIKEY_1")},
]
# لو عايزة تضيفي رقم تاني بعدين، هنضيف سطر زي:
# {"phone": os.environ.get("PHONE_2"), "apikey": os.environ.get("APIKEY_2")},


def send_whatsapp_alert():
    message = (
        "🚨 تسجيل الماجستير/الدكتوراه فتح دلوقتي على موقع الأزهر!\n"
        "ادخلي حالًا: https://pgs.alazharuniversity.org/web/login"
    )
    for r in CALLMEBOT_RECIPIENTS:
        if not r["phone"] or not r["apikey"]:
            continue
        try:
            resp = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": r["phone"], "text": message, "apikey": r["apikey"]},
                timeout=15,
            )
            log.info(f"إرسال واتساب لـ {r['phone']} -> {resp.status_code}")
        except Exception as e:
            log.error(f"فشل إرسال واتساب لـ {r['phone']}: {e}")


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
