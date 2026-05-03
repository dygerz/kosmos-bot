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
    for attempt in range(3):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
            if r.status_code == 200:
                logging.info(f"Telegram OK: {message[:40]}")
                return True
        except Exception as e:
            logging.error(f"Telegram send attempt {attempt+1}: {e}")
            time.sleep(2)
    return False

def get_telegram_updates():
    global last_update_id, current_token
    for attempt in range(3):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            r = requests.get(
                url,
                params={"offset": last_update_id + 1, "timeout": 20, "limit": 10},
                timeout=25
            )
            if r.status_code == 200:
                for update in r.json().get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {}).get("text", "")
                    chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                    logging.info(f"Mesaj alindi: '{msg[:30]}' from {chat_id}")
                    if msg and msg.startswith("/token "):
                        current_token = msg[7:].strip()
                        logging.info("Yeni token alindi!")
                        send_telegram("✅ Token güncellendi! Bot kontrol ediyor...")
                    elif msg == "/status":
                        send_telegram(f"✅ Bot calisıyor\nToken: {'var ✅' if current_token else 'yok ❌'}")
                return True
        except Exception as e:
            logging.error(f"Telegram update attempt {attempt+1}: {e}")
            time.sleep(3)
    return False

def token_is_valid():
    if not current_token:
        return False
    try:
        payload = current_token.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        remaining = data.get('exp', 0) - time.time()
        logging.info(f"Token suresi: {int(remaining/60)} dakika kaldi")
        return remaining > 300
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
                send_telegram("⚠️ Token suresi doldu!\n\n1. https://basvuru.kosmosvize.com.tr/appointmentForm\n2. Formlari doldur, takvim sayfasina gel\n3. F12 → Network → GetClosedDate → Authorization kopyala (eyJ... ile baslayan)\n4. /token eyJ... gonder")
                return
            if r.status_code == 200 and len(r.text) < 300:
                send_telegram(f"KOSMOS VIZE RANDEVU BULUNDU!\ntypeId={type_id}\n{datetime.now().strftime('%H:%M')}\n\nhttps://basvuru.kosmosvize.com.tr/appointmentForm")
        except Exception as e:
            logging.error(f"typeId={type_id}: {e}")

def telegram_listener():
    logging.info("Telegram listener basliyor...")
    while True:
        try:
            get_telegram_updates()
        except Exception as e:
            logging.error(f"Listener hata: {e}")
        time.sleep(3)

def main():
    global current_token
    logging.info("Bot baslatildi!")
    
    # Başlangıçta Telegram'a mesaj gönder
    send_telegram("✅ Kosmos Bot baslatildi!\n\nToken gondermek icin:\n1. https://basvuru.kosmosvize.com.tr/appointmentForm\n2. Takvim sayfasina kadar doldur\n3. F12 → Network → GetClosedDate → Authorization kopyala (eyJ... ile baslayan kisim)\n4. /token eyJ... seklinde gonder\n\nDurum: /status")
    
    # Telegram listener thread
    t = threading.Thread(target=telegram_listener, daemon=True)
    t.start()
    
    last_check = 0
    while True:
        if not current_token:
            logging.info("Token bekleniyor...")
            time.sleep(10)
            continue
        
        if not token_is_valid():
            logging.warning("Token suresi doldu!")
            current_token = None
            send_telegram("⚠️ Token suresi doldu! Yeni token gonderin.")
            continue
        
        now = time.time()
        if now - last_check >= CHECK_INTERVAL:
            check_appointments()
            last_check = now
            logging.info(f"Sonraki kontrol: {CHECK_INTERVAL//60} dakika sonra")
        
        time.sleep(10)

if __name__ == "__main__":
    main()
