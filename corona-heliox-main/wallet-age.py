import time
import datetime
from solana.rpc.api import Client
from solders.pubkey import Pubkey

def get_wallet_age_days(pubkey_str: str, rpc_url: str = "https://api.mainnet-beta.solana.com"):
    client = Client(rpc_url)
    pubkey = Pubkey.from_string(pubkey_str)

    before = None
    oldest_tx = None

    while True:
        resp = client.get_signatures_for_address(pubkey, before=before, limit=1000)

        result = resp.value
        if not result:
            break

        oldest_tx = result[-1]
        before = oldest_tx.signature

        if len(result) < 1000:
            break

        time.sleep(0.2)

    if not oldest_tx:
        print("No transactions found for this wallet.")
        return None

    slot = oldest_tx.slot
    bt_resp = client.get_block_time(slot)
    block_time = bt_resp.value

    if block_time is None:
        print("Block time unavailable for earliest transaction.")
        return None

    # ✅ timezone-aware UTC datetime (modern standard)
    created_at = datetime.datetime.fromtimestamp(block_time, tz=datetime.timezone.utc)
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    age_days = (now - created_at).total_seconds() / 86400
    return round(age_days, 2), created_at

if __name__ == "__main__":
    wallet = "9QsCQx9xqj1VvSHSQauXBacgXd51ZzFBzjsZdcr8RDfU"
    result = get_wallet_age_days(wallet)
    if result:
        age_days, created_at = result
        print(f"Wallet created on: {created_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Wallet age: {age_days} days")
