import asyncio
import aiohttp
import requests

RPC_URL = "https://api.mainnet-beta.solana.com"


async def get_sol_balance(session: aiohttp.ClientSession, pubkey_str: str) -> float:
    """Fetch SOL balance directly via Solana JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [str(pubkey_str), {"commitment": "finalized"}]
    }
    try:
        async with session.post(RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                lamports = data.get("result", {}).get("value", 0)
                return lamports / 1_000_000_000
    except Exception as e:
        print(f"[Solana RPC Error for {pubkey_str}]: {e}")
    return 0.0


def rug_bundle_check(sol_balance_list: list) -> float:
    if not sol_balance_list:
        return 0.0
    count = sum(1 for bal in sol_balance_list if bal < 0.5)
    percent = (count / len(sol_balance_list)) * 100
    return round(percent, 2)


async def check_batch_wallets(pubkeys: list):
    async with aiohttp.ClientSession() as session:
        tasks = [get_sol_balance(session, pk) for pk in pubkeys]
        balances = await asyncio.gather(*tasks)
        rug_percent = rug_bundle_check(balances)
        return rug_percent, balances


def rug_check(wallets: list) -> float:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If called in an existing event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(lambda: asyncio.run(check_batch_wallets(wallets))[0]).result()
        else:
            result = asyncio.run(check_batch_wallets(wallets))
            return result[0]
    except Exception:
        try:
            result = asyncio.run(check_batch_wallets(wallets))
            return result[0]
        except Exception as e:
            print(f"[rug_check Error]: {e}")
            return 0.0


