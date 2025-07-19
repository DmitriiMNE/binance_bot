import requests
import json
from logger import logger

# --- Загрузка конфигурации ---
try:
    with open('config.json') as f:
        config = json.load(f)
    TELEGRAM_TOKEN = config.get('telegram_token')
    TELEGRAM_CHAT_ID = config.get('telegram_chat_id')
except FileNotFoundError:
    logger.error("config.json not found. Telegram notifications disabled.")
    TELEGRAM_TOKEN = None
    TELEGRAM_CHAT_ID = None
except json.JSONDecodeError:
    logger.error("Error decoding config.json. Telegram notifications disabled.")
    TELEGRAM_TOKEN = None
    TELEGRAM_CHAT_ID = None


def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"Telegram not configured. Message not sent: {text}")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        response = requests.post(url, data=data)
        response.raise_for_status()  # Проверка на ошибки HTTP
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram message: {e}")
