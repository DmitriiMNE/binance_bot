import time
import json
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
import pandas as pd
from ta.volatility import AverageTrueRange
from logger import logger
from notifier import send_telegram_message

# --- Загрузка конфигурации ---
with open('config.json') as f:
    config = json.load(f)

API_KEY = config['api_key']
API_SECRET = config['api_secret']
SYMBOL = config['symbol']
BALANCE_PERCENT = config['balance_percent']  # Процент от баланса для торговли
TARGET_PROFIT_PERCENT = config['target_profit_percent']
COMMISSION_PERCENT = config['commission_percent']
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
SLEEP_INTERVAL = 30

client = Client(API_KEY, API_SECRET)

def get_usdt_balance():
    """Получает доступный баланс USDT"""
    try:
        account = client.get_account()
        for balance in account['balances']:
            if balance['asset'] == 'USDT':
                return float(balance['free'])
        return 0.0
    except BinanceAPIException as e:
        logger.error(f"Error getting USDT balance: {e}")
        return 0.0

def calculate_quantity(buy_price, usdt_amount):
    """Рассчитывает количество криптовалюты для покупки"""
    try:
        # Получаем информацию о символе для правильного округления
        symbol_info = client.get_symbol_info(SYMBOL)
        lot_size_filter = None
        
        for filter_item in symbol_info['filters']:
            if filter_item['filterType'] == 'LOT_SIZE':
                lot_size_filter = filter_item
                break
        
        if lot_size_filter:
            step_size = float(lot_size_filter['stepSize'])
            min_qty = float(lot_size_filter['minQty'])
            
            # Рассчитываем количество
            quantity = usdt_amount / buy_price
            
            # Округляем до правильного шага
            precision = len(str(step_size).split('.')[-1].rstrip('0'))
            quantity = round(quantity, precision)
            
            # Проверяем минимальное количество
            if quantity < min_qty:
                logger.warning(f"Calculated quantity {quantity} is less than minimum {min_qty}")
                return None
                
            return quantity
        else:
            # Если не удалось получить фильтры, используем базовую логику
            quantity = usdt_amount / buy_price
            return round(quantity, 6)  # Базовая точность для большинства символов
            
    except Exception as e:
        logger.error(f"Error calculating quantity: {e}")
        return None

def get_klines(symbol, interval='1h', limit=100):
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        df = df[['open', 'high', 'low', 'close']].astype(float)
        return df
    except BinanceAPIException as e:
        logger.error(f"Error getting klines: {e}")
        return None

def calculate_levels(df):
    if df is None or df.empty:
        return None, None
    atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=ATR_PERIOD).average_true_range()
    last_close = df['close'].iloc[-1]
    atr_value = atr.iloc[-1]

    buy_price = last_close - ATR_MULTIPLIER * atr_value
    # Sell price will be calculated based on actual buy price later
    return round(buy_price, 2), None

def place_limit_order(side, price, quantity):
    try:
        order = client.create_order(
            symbol=SYMBOL,
            side=side,
            type=ORDER_TYPE_LIMIT,
            quantity=quantity,
            price=f'{price:.2f}',
            timeInForce=TIME_IN_FORCE_GTC
        )
        logger.info(f"Placed {side} order for {quantity} {SYMBOL} at {price}")
        send_telegram_message(f"Placed {side} order for {quantity} {SYMBOL} at {price}")
        return order
    except BinanceAPIException as e:
        logger.error(f"Error placing {side} order at {price}: {e}")
        send_telegram_message(f"Error placing {side} order: {e}")
        return None

def get_order_status(order_id):
    try:
        order = client.get_order(symbol=SYMBOL, orderId=order_id)
        return order
    except BinanceAPIException as e:
        logger.error(f"Error getting order status for {order_id}: {e}")
        return None

def cancel_order(order_id):
    try:
        client.cancel_order(symbol=SYMBOL, orderId=order_id)
        logger.info(f"Canceled order {order_id}")
        send_telegram_message(f"Canceled order {order_id}")
    except BinanceAPIException as e:
        logger.error(f"Error canceling order {order_id}: {e}")

# --- Основной цикл ---
active_buy_order_id = None
active_sell_order_id = None
position_open = False
trade_quantity = None  # Хранит количество для текущей сделки

while True:
    try:
        # --- Логика покупки ---
        if not position_open and active_buy_order_id is None:
            df = get_klines(SYMBOL)
            buy_price, _ = calculate_levels(df)
            if buy_price:
                # Получаем баланс и рассчитываем количество для покупки
                usdt_balance = get_usdt_balance()
                usdt_to_trade = usdt_balance * (BALANCE_PERCENT / 100)
                
                if usdt_to_trade < 10:  # Минимальная сумма для торговли
                    logger.warning(f"Insufficient balance for trading. Available: {usdt_balance} USDT, Required: at least {10/BALANCE_PERCENT*100} USDT")
                    time.sleep(SLEEP_INTERVAL)
                    continue
                
                quantity = calculate_quantity(buy_price, usdt_to_trade)
                if quantity:
                    trade_quantity = quantity
                    order = place_limit_order(SIDE_BUY, buy_price, quantity)
                    if order:
                        active_buy_order_id = order['orderId']

        # --- Проверка исполнения ордера на покупку ---
        if active_buy_order_id:
            order_info = get_order_status(active_buy_order_id)
            if order_info and order_info['status'] == 'FILLED':
                logger.info(f"Buy order {active_buy_order_id} filled!")
                send_telegram_message(f"✅ Buy order filled at {order_info['price']}")
                
                position_open = True
                actual_buy_price = float(order_info['price'])
                active_buy_order_id = None

                # --- Расчет и установка ордера на продажу ---
                profit_margin = actual_buy_price * (TARGET_PROFIT_PERCENT / 100)
                commission = (actual_buy_price + (actual_buy_price + profit_margin)) * (COMMISSION_PERCENT / 100)
                sell_price = actual_buy_price + profit_margin + commission
                
                sell_order = place_limit_order(SIDE_SELL, sell_price, trade_quantity)
                if sell_order:
                    active_sell_order_id = sell_order['orderId']

        # --- Проверка исполнения ордера на продажу ---
        if active_sell_order_id:
            order_info = get_order_status(active_sell_order_id)
            if order_info and order_info['status'] == 'FILLED':
                logger.info(f"Sell order {active_sell_order_id} filled! Profit taken.")
                send_telegram_message(f"💰 Profit taken! Sold at {order_info['price']}")
                active_sell_order_id = None
                position_open = False
                trade_quantity = None  # Сбрасываем количество

        # --- Логика отмены, если цена ушла далеко ---
        # (Можно добавить позже)

        time.sleep(SLEEP_INTERVAL)

    except Exception as e:
        logger.error(f"Main loop error: {e}")
        send_telegram_message(f"🚨 Main loop error: {e}")
        time.sleep(60)
