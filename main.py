import requests
import time
import logging
import threading
import base64
import json
from datetime import datetime, timedelta

TELEGRAM_TOKEN = "8793846897:AAHkIoZnRdDoiuDh8RFdoje1xns5Lh23Xkk"
TELEGRAM_CHAT_ID = "8704313789"
DEALER_ID = 1
TYPE_IDS = [14, 15, 16, 17, 18]
CHECK_INTERVAL = 15 * 60

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

current_token = None
last_update_id = 0

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        logging.error(f"Telegram hatası: {e}")

def get_telegram_updates():
    global last_update_id, current_token
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 30}, timeout=35)
        if r.status_code == 200:
            for update in r.json().get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {}).get("text", "")
                if msg and msg.startswith("/token "):
                    current_token = msg[7:].strip()
                    logging.info("Yeni token alındı!")
                    send_telegram("✅ Token güncellendi! Bot kontrol ediyor...")
                elif msg == "/status":
                    send_telegram(f"✅ Bot çalışıyor\nToken: {'var ✅' if current_token else 'yok ❌'}")
    except Exception as e:
        logging.error(f"Update hatası: {e}")

def token_is_valid():
    global current_token
    if not current_token:
        return False
    try:
        payload = current_token.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        return data.get('exp', 0) - time.time() > 300
    except:
        return True

def check_appointments():
    global current_token
    if not current_token:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    max_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
        'Origin': 'https://basvuru.kosmosvize.com.tr',
        'Referer': 'https://basvuru.kosmosvize.com.tr/',
        'Authorization': f'Bearer {current_token}'
    })
    for type_id in TYPE_IDS:
        try:
            url = f"https://api.kosmosvize.com.tr/api/AppointmentClosedDates/GetClosedDate?dealerId={DEALER_ID}&date={today}&maxDate={max_date}&appointmentTypeId={type_id}"
            r = session.get(url, timeout=15)
            logging.info(f"typeId={type_id} -> {r.status_code} ({len(r.text)}b)")
            if r.status_code == 401:
                current_token = None
                send_telegram("⚠️ Token süresi doldu!\n\n1. https://basvuru.kosmosvize.com.tr/appointmentForm\n2. Formları doldur, takvim sayfasına gel\n3. F12 → Network → GetClosedDate → Authorization header kopyala (eyJ... ile başlayan kısım)\n4. Bana /token eyJ... gönder")
                return
            if r.status_code == 200 and len(r.text) < 300:
                send_telegram(f"🚨 KOSMOS VİZE RANDEVU BULUNDU!\ntypeId={type_id}\n⏰ {datetime.now().strftime('%H:%M')}\n\n👉 https://basvuru.kosmosvize.com.tr/appointmentForm")
        except Exception as e:
            logging.error(f"typeId={type_id}: {e}")

def telegram_listener():
    while True:
        try:
            get_telegram_updates()
        except:
            pass
        time.sleep(2)

def main():
    global current_token
    logging.info("Bot başlatıldı!")
    send_telegram("✅ Kosmos Bot başlatıldı!\n\nToken göndermek için:\n1. https://basvuru.kosmosvize.com.tr/appointmentForm\n2. Formları doldur, takvim sayfasına gel\n3. F12 → Network → GetClosedDate → Headers → Authorization değerini kopyala (eyJ... ile başlayan kısım)\n4. /token eyJ... şeklinde gönder\n\nDurum: /status")
    threading.Thread(target=telegram_listener, daemon=True).start()
    while True:
        if not current_token:
            time.sleep(30)
            continue
        if not token_is_valid():
            current_token = None
            continue
        check_appointments()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
