'# Clore.ai Auto-Pricing Bot

---

## 📖 English

### Overview

This bot automatically updates your server's rental price based on the current market median on Clore.ai.

### How It Works

1. Fetches all publicly listed servers from the Clore.ai marketplace via API.
2. Calculates the **median daily price** (in USD) among **rented** servers with the same GPU model.
3. Sets your server's price to **median - $0.01 per day** for:
   - **BTC** (on-demand and spot)
   - **USDT** (on-demand and spot)
4. Sets the **CLORE** price to **BTC/USDT price × 1.15** (i.e., +15% in USD terms).

### ⚠️ Important: Deployment

**This bot is NOT designed to run inside a Docker container on a Clore rented server.**

Clore.ai automatically terminates any third-party Docker containers running on rented machines. If you deploy this bot as a Docker service, **it will be killed**.

### Recommended Deployment Method

Use **systemd** to run the bot as a persistent background service.

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CLORE_API_KEY` | Your Clore.ai API key | `abc123...` |
| `CLORE_SERVER_ID` | Numeric ID of your server | `108181` |
| `CLORE_SERVER_NAME` | Exact server name | `my-rig-01` |
| `CLORE_GPU_MODEL` | GPU model to filter by | `RTX 5090` |
| `CLORE_UPDATE_INTERVAL` | Update interval in minutes | `30` |
| `CLORE_API_URL` | Clore.ai API base URL (optional) | `https://api.clore.ai/v1` |

### Installation

```bash
sudo mkdir -p /opt/clore-bot
sudo cp bot.py /opt/clore-bot/
cd /opt/clore-bot
python3 -m venv venv
source venv/bin/activate
pip install requests schedule
deactivate
```

Create systemd service file `/etc/systemd/system/clore-price-bot.service`:

```ini
[Unit]
Description=Clore.ai Price Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clore-bot
ExecStart=/opt/clore-bot/venv/bin/python /opt/clore-bot/bot.py
Restart=always
RestartSec=10
Environment="CLORE_API_KEY=your_api_key_here"
Environment="CLORE_SERVER_ID=your_server_id_here"
Environment="CLORE_SERVER_NAME=your_server_name_here"
Environment="CLORE_GPU_MODEL=RTX 5090"
Environment="CLORE_UPDATE_INTERVAL=30"
Environment="CLORE_API_URL=https://api.clore.ai/v1"

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clore-price-bot
sudo systemctl start clore-price-bot
```

Check logs:

```bash
sudo journalctl -u clore-price-bot -f
```

### Updating the Bot

```bash
sudo systemctl restart clore-price-bot
```

### Uninstalling

```bash
sudo systemctl stop clore-price-bot
sudo systemctl disable clore-price-bot
sudo rm /etc/systemd/system/clore-price-bot.service
sudo systemctl daemon-reload
sudo rm -rf /opt/clore-bot
```

### License

MIT

---

## 📖 Русский

### Обзор

Этот бот автоматически обновляет цену аренды вашего сервера на основе текущей медианной цены на Clore.ai.

### Как это работает

1. Получает список всех публичных серверов с маркетплейса Clore.ai через API.
2. Вычисляет **медианную дневную цену** (в USD) среди **арендованных** серверов с такой же видеокартой.
3. Устанавливает цену вашего сервера на уровне **медиана - $0.01 за день** для:
   - **BTC** (on-demand и spot)
   - **USDT** (on-demand и spot)
4. Устанавливает цену в **CLORE** на уровне **цена BTC/USDT × 1.15** (т.е. +15% в USD).

### ⚠️ Важно: Развёртывание

**Этот бот НЕ предназначен для запуска в Docker-контейнере на арендованном сервере Clore.**

Clore.ai автоматически завершает любые сторонние Docker-контейнеры. Если вы развернёте бота как Docker-сервис, **он будет убит**.

### Рекомендуемый способ развёртывания

Используйте **systemd** для запуска бота как фоновой службы.

### Переменные окружения

| Переменная | Описание | Пример |
|------------|----------|--------|
| `CLORE_API_KEY` | Ваш API-ключ Clore.ai | `abc123...` |
| `CLORE_SERVER_ID` | Числовой ID вашего сервера | `108181` |
| `CLORE_SERVER_NAME` | Точное имя сервера | `my-rig-01` |
| `CLORE_GPU_MODEL` | Модель GPU для фильтрации | `RTX 5090` |
| `CLORE_UPDATE_INTERVAL` | Интервал обновления в минутах | `30` |
| `CLORE_API_URL` | Базовый URL API Clore.ai (опционально) | `https://api.clore.ai/v1` |

### Установка

```bash
sudo mkdir -p /opt/clore-bot
sudo cp bot.py /opt/clore-bot/
cd /opt/clore-bot
python3 -m venv venv
source venv/bin/activate
pip install requests schedule
deactivate
```

Создайте файл systemd-службы `/etc/systemd/system/clore-price-bot.service`:

```ini
[Unit]
Description=Clore.ai Price Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clore-bot
ExecStart=/opt/clore-bot/venv/bin/python /opt/clore-bot/bot.py
Restart=always
RestartSec=10
Environment="CLORE_API_KEY=ваш_ключ_здесь"
Environment="CLORE_SERVER_ID=ваш_id_сервера_здесь"
Environment="CLORE_SERVER_NAME=ваше_имя_сервера_здесь"
Environment="CLORE_GPU_MODEL=RTX 5090"
Environment="CLORE_UPDATE_INTERVAL=30"
Environment="CLORE_API_URL=https://api.clore.ai/v1"

[Install]
WantedBy=multi-user.target
```

Включите и запустите службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clore-price-bot
sudo systemctl start clore-price-bot
```

Проверьте логи:

```bash
sudo journalctl -u clore-price-bot -f
```

### Обновление бота

```bash
sudo systemctl restart clore-price-bot
```

### Удаление

```bash
sudo systemctl stop clore-price-bot
sudo systemctl disable clore-price-bot
sudo rm /etc/systemd/system/clore-price-bot.service
sudo systemctl daemon-reload
sudo rm -rf /opt/clore-bot
```

### Лицензия

MIT

---

## 📄 Files

```text
clore-price-bot/
├── bot.py
├── requirements.txt
└── README.md
```

## requirements.txt

```text
requests
schedule
```

## 📞 Support / Поддержка

- Official Clore.ai Documentation: https://docs.clore.ai
- API Documentation: https://api.clore.ai/v1

© 2026 — Use at your own risk. The author assumes no responsibility for lost revenue or other consequences.

Используйте на свой страх и риск. Автор не несёт ответственности за потерянный доход или иные последствия.
