import os
import time
import logging
import requests
import schedule
from statistics import median
from typing import List, Dict, Optional

# -------------------- Чтение переменных окружения --------------------
API_KEY = os.getenv("CLORE_API_KEY")
if not API_KEY:
    raise ValueError("CLORE_API_KEY не задан")

SERVER_ID = int(os.getenv("CLORE_SERVER_ID"))          # ID вашего сервера (число)
SERVER_NAME = os.getenv("CLORE_SERVER_NAME")           # Имя сервера (как в интерфейсе)
if not SERVER_NAME:
    raise ValueError("CLORE_SERVER_NAME не задан")

GPU_MODEL = os.getenv("CLORE_GPU_MODEL", "RTX 5080")
UPDATE_INTERVAL_MINUTES = int(os.getenv("CLORE_UPDATE_INTERVAL", "10"))
BASE_URL = os.getenv("CLORE_API_URL", "https://api.clore.ai/v1")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {"auth": API_KEY}

# -------------------- Функции API --------------------

def get_marketplace() -> Optional[List[Dict]]:
    """Получить список всех серверов с marketplace."""
    try:
        resp = requests.get(f"{BASE_URL}/marketplace", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("servers", [])
    except Exception as e:
        logger.error(f"Ошибка получения marketplace: {e}")
        return None

def get_spot_marketplace(server_id: int) -> Optional[Dict]:
    """Получить информацию о спотовом рынке для сервера (включая курсы)."""
    try:
        resp = requests.get(f"{BASE_URL}/spot_marketplace?market={server_id}", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("market")
    except Exception as e:
        logger.error(f"Ошибка получения spot_marketplace: {e}")
        return None

def set_server_settings(
    server_name: str,
    btc_on_demand: float,
    btc_spot: float,
    clore_on_demand: float,
    clore_spot: float,
    usd_on_demand: float,
    usd_spot: float,
    enabled_btc: bool = True,
    enabled_clore: bool = True,
    enabled_usd: bool = True,
    mrl: int = 72
) -> bool:
    """Установить настройки сервера через /v1/set_server_settings."""
    payload = {
        "name": server_name,
        "availability": True,
        "mrl": mrl,
        "bitcoin_on_demand": btc_on_demand,
        "bitcoin_spot": btc_spot,
        "CLORE-Blockchain_on_demand": clore_on_demand,
        "CLORE-Blockchain_spot": clore_spot,
        "USD-Blockchain_on_demand": usd_on_demand,
        "USD-Blockchain_spot": usd_spot,
        "enabled-USD-Blockchain": enabled_usd,
        "enabled-CLORE-Blockchain": enabled_clore,
        "enabled-bitcoin": enabled_btc,
    }
    try:
        resp = requests.post(f"{BASE_URL}/set_server_settings", headers=HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            logger.info("Настройки сервера успешно обновлены.")
            return True
        else:
            logger.error(f"Ошибка при обновлении настроек: {data}")
            return False
    except Exception as e:
        logger.error(f"Ошибка запроса set_server_settings: {e}")
        return False

# -------------------- Основная логика --------------------

def compute_median_price_usd(servers: List[Dict]) -> Optional[float]:
    """Вычислить медианную цену (USD за день) среди арендованных серверов с нужной GPU."""
    prices = []
    for s in servers:
        if not s.get("rented", False):
            continue
        specs = s.get("specs", {})
        gpu_str = specs.get("gpu", "")
        if GPU_MODEL not in gpu_str:
            continue
        price_obj = s.get("price", {})
        on_demand = price_obj.get("on_demand", {})
        usd_price = on_demand.get("USD-Blockchain")
        if usd_price is not None and usd_price > 0:
            prices.append(usd_price)
    if not prices:
        logger.warning("Нет арендованных серверов с такой GPU и ценой в USD.")
        return None
    med = median(prices)
    logger.info(f"Медианная дневная цена (Rented, {GPU_MODEL}) в USD: ${med:.3f}/день")
    return med

def update_price():
    logger.info("Запуск обновления цены...")
    servers = get_marketplace()
    if servers is None:
        return

    med_usd_day = compute_median_price_usd(servers)
    if med_usd_day is None:
        return

    # Базовая цена за день: медиана минус $0.24 (т.е. $0.01/час)
    base_price_day = med_usd_day - 0.24
    if base_price_day < 0.01:
        base_price_day = 0.01

    # Цена для CLORE на 15% выше
    clore_price_day_usd = base_price_day * 1.15

    # Получить курсы валют
    market = get_spot_marketplace(SERVER_ID)
    if market is None:
        logger.error("Не удалось получить курсы валют.")
        return
    rates = market.get("currency_rates_in_usd", {})
    rate_btc = rates.get("bitcoin")
    rate_clore = rates.get("CLORE-Blockchain")
    if rate_btc is None or rate_clore is None:
        logger.error("Не удалось получить курс BTC или CLORE.")
        return

    # Пересчёт в криптовалюты (за день)
    btc_price_day = base_price_day / rate_btc
    clore_price_day_crypto = clore_price_day_usd / rate_clore

    # Установить настройки
    success = set_server_settings(
        server_name=SERVER_NAME,
        btc_on_demand=btc_price_day,
        btc_spot=btc_price_day * 0.9,      # спот чуть ниже
        clore_on_demand=clore_price_day_crypto,
        clore_spot=clore_price_day_crypto * 0.9,
        usd_on_demand=base_price_day,
        usd_spot=base_price_day * 0.9,
        enabled_btc=True,
        enabled_clore=True,
        enabled_usd=True,
        mrl=72
    )

    if success:
        logger.info(
            f"Цены обновлены (за день): BTC={btc_price_day:.8f}, "
            f"CLORE={clore_price_day_crypto:.2f}, USD={base_price_day:.3f}"
        )
    else:
        logger.error("Не удалось обновить цены.")

# -------------------- Запуск --------------------

if __name__ == "__main__":
    logger.info(f"Бот запущен. Обновление каждые {UPDATE_INTERVAL_MINUTES} минут.")
    update_price()
    schedule.every(UPDATE_INTERVAL_MINUTES).minutes.do(update_price)
    while True:
        schedule.run_pending()
        time.sleep(1)
