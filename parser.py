import requests
from dotenv import load_dotenv
import os

load_dotenv()

API_URL = "https://gateway.abcex.io/api/v1/markets/price"
MARKET_ID = "USDTRUB"
TOKEN = os.getenv("ABCEX_TOKEN")  # токен из .env

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}


def get_market_data():
    try:
        response = requests.get(API_URL, headers=HEADERS, params={"marketId": MARKET_ID})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при получении данных с ABCEX: {e}")
        return None


async def get_usdt_buy_price() -> float:
    data = get_market_data()
    return float(data["askPrice"]) if data and "askPrice" in data else 0.0


async def get_usdt_sell_price() -> float:
    data = get_market_data()
    return float(data["bidPrice"]) if data and "bidPrice" in data else 0.0
