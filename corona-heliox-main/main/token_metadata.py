import asyncio
import aiohttp

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6ImJlM2MyOGE0LTNlMDMtNDRhMC04ZjUwLTE2MmMyN2ZiZDAxMyIsIm9yZ0lkIjoiNDcyMzU5IiwidXNlcklkIjoiNDg1OTI0IiwidHlwZUlkIjoiZDI4ZGEwY2UtMDFkNi00ZGU5LTk0YjQtZDdlMzRiM2FjYzMxIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3NTg4MDMyMDMsImV4cCI6NDkxNDU2MzIwM30.bS510HQhvjT5CJF3eEKuV9VaHSgbWpzukeX3jS2EypY"   # replace with your actual key

HEADERS = {
    "Accept": "application/json",
    "X-API-Key": API_KEY
}

BASE_URL = "https://solana-gateway.moralis.io/token/mainnet"


async def fetch(session, name, url):
    try:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            data = await response.json()
            return name, data
    except Exception as e:
        return name, {"error": str(e)}


async def main(token_ca):
    ENDPOINTS = {
        "top_holders": f"{BASE_URL}/{token_ca}/top-holders?limit=25",
        "metadata": f"{BASE_URL}/{token_ca}/metadata",
        "price": f"{BASE_URL}/{token_ca}/price",
        "pairs_stats": f"{BASE_URL}/{token_ca}/pairs/stats",
        "holders": f"{BASE_URL}/holders/{token_ca}"
    }
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, name, url) for name, url in ENDPOINTS.items()]
        results = await asyncio.gather(*tasks)
        raw = {name: data for name, data in results}

        print(raw)
        return raw


def get_metadata(token_ca):
    return asyncio.run(main(token_ca))