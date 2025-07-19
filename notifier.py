import requests
import json

def send_telegram_message(text, config):
    try:
        token = config["telegram_token"]
        chat_id = config["telegram_chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram error: {e}")