import requests
import time
import logging
import threading
import base64
import json
import os
from datetime import datetime, timedelta

TELEGRAM_TOKEN = "8793846897:AAHkIoZnRdDoiuDh8RFdoje1xns5Lh23Xkk"
TELEGRAM_CHAT_ID = "8704313789"
DEALER_ID = 1
TYPE_IDS = [14, 15, 16, 17, 18]
CHECK_INTERVAL = 15 * 60

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# Token önce environment variable'dan al, sonra Telegram'dan güncellenebilir
current_token = os.environ.get('KOSMOS_TOKEN', None)
last_update_id = 0

if current_token:
    logging.info("Token environment variable'dan alindi!")
else:
    logging.info("Token bekleniyor...")

def send_telegram(message):
    for attempt in range(3):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
            if r.status_code == 200:
                logging.info(f"Telegram OK")
                return True
        except Exception as e:
            logging.error(f"Telegram send {attempt+1}: {e}")
            time.sleep(2)
    return False

def get_telegram_updates():
    global last_update_id, current_token
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 20, "limit": 10}, timeout=25)
        if r.status_code == 200:
            for update in r.json().get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {}).get("text", "")
                logging.info(f"Mesaj: '{msg[:30]}'")
                if msg and msg.startswith("/token "):
                    current_token = msg[7:].strip()
                    logging.info("Token Telegram'dan alindi!")
                    send_telegram("✅ Token güncellendi!")
                elif msg == "/status":
                    exp_info = ""
                    if current_token:
                        try:
                            payload = current_token.split('.')[1]
                            payload += '=' * (4 - len(payload) % 4)
                            data = json.loads(base64.b64decode(payload))
                            left = int((data.get('exp', 0) - time.time()) / 60)
                            exp_info = f"\nToken: {left} dakika kaldi"
                        except:
                            pass
                    send_telegram(f"✅ Bot calisiyor\nToken: {'var ✅' if current_token else 'yok ❌'}{exp_info}")
    except Exception as e:
        logging.error(f"Update hatasi: {e}")

def token_is_valid():
    if not current_token:
        return False
    try:
        payload = current_token.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        remaining = data.get('exp', 0) - time.time()
        logging.info(f"Token: {int(remaining/60)} dk kaldi")
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
                send_telegram("⚠️ Token suresi doldu!\n\n1. https://basvuru.kosmosvize.com.tr/appointmentForm\n2. Formlari doldur, takvim sayfasina gel\n3. F12 → Network → GetClosedDate → Authorization kopyala\n4. Railway Variables'da KOSMOS_TOKEN'i guncelle\nVEYA bota /token eyJ... gonder")
                return
            if r.status_code == 200 and len(r.text) < 300:
                send_telegram(f"🚨 KOSMOS VIZE RANDEVU BULUNDU!\ntypeId={type_id}\n{datetime.now().strftime('%H:%M')}\n\nhttps://basvuru.kosmosvize.com.tr/appointmentForm")
        except Exception as e:
            logging.error(f"typeId={type_id}: {e}")

def telegram_listener():
    while True:
        try:
            get_telegram_updates()
        except Exception as e:
            logging.error(f"Listener: {e}")
        time.sleep(5)

def main():
    global current_token
    logging.info("Bot baslatildi!")
    
    if current_token:
        send_telegram("✅ Kosmos Bot baslatildi! Token mevcut, kontrol basliyor...")
    else:
        send_telegram("✅ Kosmos Bot baslatildi!\n\nToken icin Railway Variables'da KOSMOS_TOKEN ekleyin\nVEYA bota /token eyJ... gonderin")
    
    threading.Thread(target=telegram_listener, daemon=True).start()
    
    last_check = 0
    while True:
        if not current_token:
            # Environment variable'dan tekrar dene
            current_token = os.environ.get('KOSMOS_TOKEN', None)
            if not current_token:
                time.sleep(10)
                continue
        
        if not token_is_valid():
            current_token = None
            continue
        
        now = time.time()
        if now - last_check >= CHECK_INTERVAL:
            check_appointments()
            last_check = now
        
        time.sleep(10)

if __name__ == "__main__":
    main()
