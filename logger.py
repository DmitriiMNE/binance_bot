import logging
import sys

# Создаем логгер
logger = logging.getLogger('binance_bot')
logger.setLevel(logging.INFO)

# Создаем обработчик для вывода в консоль
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

# Создаем обработчик для записи в файл
file_handler = logging.FileHandler('bot.log')
file_handler.setLevel(logging.INFO)

# Создаем форматтер и добавляем его в обработчики
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Добавляем обработчики в логгер
logger.addHandler(stream_handler)
logger.addHandler(file_handler)

