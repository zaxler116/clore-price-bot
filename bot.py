import os
import time
import logging
import re
import schedule
import requests
from statistics import median
from typing import List, Optional
from clore_ai import CloreAI

# -------------------- Настройки --------------------
API_KEY = os.getenv("CLORE_API_KEY")
if not API_KEY:
    raise ValueError("CLORE_API_KEY не задан")

SERVER_ID = int(os.getenv("CLORE_SERVER_ID"))
SERVER_NAME = os.getenv("CLORE_SERVER_NAME")
if not SERVER_NAME:
    raise ValueError("CLORE_SERVER_NAME не задан")

GPU_MODEL = os.getenv("CLORE_GPU_MODEL", "RTX 5080")
UPDATE_INTERVAL_MINUTES = int(os.getenv("CLORE_UPDATE_INTERVAL", "2"))
BASE_URL = "https://api.clore.ai/v1"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = CloreAI(api_key=API_KEY, max_retries=5)


def extract_gpu_count(gpu_str: str) -> int:
    """Извлекает количество GPU из строки типа '1x NVIDIA...'."""
    if not gpu_str:
        return 1
    match = re.match(r'(\d+)x', gpu_str.strip())
    return int(match.group(1)) if match else 1


def compute_median_price_per_gpu(servers: List) -> Optional[float]:
    """Вычисляет медианную цену за 1 GPU в день (USD) среди арендованных серверов."""
    prices = []
    for s in servers:
        if not s.rented:
            continue
        gpu_str = s.specs.gpu if s.specs else ""
        if GPU_MODEL not in gpu_str:
            continue
        gpu_count = extract_gpu_count(gpu_str)

        price_total = None
        if s.price and s.price.on_demand:
            price_total = getattr(s.price.on_demand, 'USD_Blockchain', None)
        if price_total is None and s.price_usd is not None:
            price_total = s.price_usd * 24

        if price_total is not None and price_total > 0:
            prices.append(price_total / gpu_count)

    if not prices:
        logger.warning("Нет арендованных серверов с такой GPU.")
        return None

    med = median(prices)
    logger.info(f"Медианная цена за 1 GPU/день (Rented, {GPU_MODEL}) = ${med:.3f}")
    return med


def get_my_servers() -> dict:
    """Получить список своих серверов через REST /my_servers."""
    url = f"{BASE_URL}/my_servers"
    headers = {"auth": API_KEY}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def post_with_retry(url: str, headers: dict, json_data: dict, max_retries: int = 5) -> dict:
    """POST с повторными попытками при 429."""
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=json_data, timeout=10)
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"429, повтор через {wait} сек (попытка {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Ошибка {e}, повтор через 2 сек")
            time.sleep(2)
    return {}


def update_price():
    logger.info("=== ЗАПУСК ОБНОВЛЕНИЯ ЦЕНЫ ===")

    try:
        # 1. Получить все серверы с marketplace (через SDK)
        servers = client.marketplace(available_only=False)
        if not servers:
            logger.error("Список серверов пуст.")
            return
        logger.info(f"Получено {len(servers)} серверов")
        time.sleep(1)

        # 2. Медиана per GPU
        med_usd_day = compute_median_price_per_gpu(servers)
        if med_usd_day is None:
            return

        base_price_day = max(med_usd_day - 0.24, 0.01)
        clore_price_day_usd = base_price_day * 1.15
        logger.info(f"Базовая цена (USD/день за 1 GPU): ${base_price_day:.3f}")
        logger.info(f"Цена для CLORE (USD/день за 1 GPU): ${clore_price_day_usd:.3f}")

        # 3. Получить курсы валют (через SDK)
        spot = client.spot_marketplace(SERVER_ID)
        if not spot:
            logger.error("Не удалось получить spot_marketplace")
            return
        time.sleep(1)

        rates = spot.currency_rates_in_usd
        if not rates:
            logger.error("Нет курсов валют")
            return
        rate_btc = rates.get("bitcoin")
        rate_clore = rates.get("CLORE-Blockchain")
        if rate_btc is None or rate_clore is None:
            logger.error(f"Курсы не получены: BTC={rate_btc}, CLORE={rate_clore}")
            return
        logger.info(f"Курсы: BTC={rate_btc:.2f} USD, CLORE={rate_clore:.8f} USD")

        # Вычисляем цены в криптовалютах
        btc_price_day = base_price_day / rate_btc
        clore_price_day_crypto = clore_price_day_usd / rate_clore
        logger.info(f"Цена в BTC/день: {btc_price_day:.8f}")
        logger.info(f"Цена в CLORE/день: {clore_price_day_crypto:.2f}")

        # 4. Получить текущую конфигурацию через /my_servers (для отладки)
        my_servers_data = get_my_servers()
        servers_list = my_servers_data.get("servers", [])
        current_config = None
        for s in servers_list:
            if s.get("name") == SERVER_NAME:
                current_config = s
                break
        if not current_config:
            logger.error(f"Сервер {SERVER_NAME} не найден в my_servers")
            return
        logger.info(f"Текущая конфигурация: name={current_config.get('name')}, id={current_config.get('id')}")

        # 5. Формируем payload с autoprice для всех валют
        autoprice = {
            "bitcoin": "usd",
            "CLORE-Blockchain": "usd",
            "USD-Blockchain": "usd"
        }

        # Spot цена = On‑Demand цена (чтобы спот не был дешевле)
        usd_pricing = {
            "bitcoin": {
                "on_demand": base_price_day,
                "spot": base_price_day   # спот равен on_demand
            },
            "CLORE-Blockchain": {
                "on_demand": clore_price_day_usd,
                "spot": clore_price_day_usd
            },
            "USD-Blockchain": {
                "on_demand": base_price_day,
                "spot": base_price_day
            }
        }

        # Явные цены в криптовалютах (они игнорируются при autoprice, но для совместимости)
        payload = {
            "name": SERVER_NAME,
            "availability": True,
            "mrl": 72,
            "bitcoin_on_demand": btc_price_day,
            "bitcoin_spot": btc_price_day,   # спот = on_demand
            "CLORE-Blockchain_on_demand": clore_price_day_crypto,
            "CLORE-Blockchain_spot": clore_price_day_crypto,
            "USD-Blockchain_on_demand": base_price_day,
            "USD-Blockchain_spot": base_price_day,
            "enabled-USD-Blockchain": True,
            "enabled-CLORE-Blockchain": True,
            "enabled-bitcoin": True,
            "autoprice": autoprice,
            "usd_pricing": usd_pricing
        }

        logger.info(f"Отправка payload: {payload}")

        # 6. Отправить через POST с повторными попытками
        url = f"{BASE_URL}/set_server_settings"
        headers = {"auth": API_KEY, "Content-type": "application/json"}
        result = post_with_retry(url, headers, payload)

        logger.info(f"Ответ API: {result}")
        if result.get("code") == 0:
            logger.info("✅ ЦЕНА УСПЕШНО ОБНОВЛЕНА!")
        else:
            logger.error(f"❌ Ошибка обновления: {result}")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info(f"Бот запущен. Обновление каждые {UPDATE_INTERVAL_MINUTES} мин.")
    update_price()
    schedule.every(UPDATE_INTERVAL_MINUTES).minutes.do(update_price)
    while True:
        schedule.run_pending()
        time.sleep(1)
