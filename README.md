# Clore.ai auto-pricing bot
This bot can update price of your server up to "median_rented_price - $0.01" with your interval.
Base price is in BTC and USDT which are equal, and CLORE price = BTC/USDT price + 15% (in USD).
If you deploy this bot on the rent server, THIS DOCKER SERVICE WILL NOT WORK!!! Because Clore docker containers remove any another user's docker container. In this case you should use systemd service, its example is in "clore-price-bot.service". 
