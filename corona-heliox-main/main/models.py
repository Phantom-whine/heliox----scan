from django.db import models
from django.contrib.auth.models import User as DjangoUser
from django.utils import timezone
import uuid


class User(models.Model):
    """Legacy user model for Telegram bot integration backwards compatibility."""
    username = models.CharField(max_length=500, blank=True, null=True)
    chat_id = models.CharField(max_length=2000, blank=True, null=True)

    def __str__(self):
        return f"TG User - {self.username}"


class UserProfile(models.Model):
    """Extended user profile for SaaS platform features."""
    user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE, related_name='profile')
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    telegram_username = models.CharField(max_length=150, blank=True, null=True)
    telegram_sync_code = models.CharField(max_length=12, blank=True, null=True)
    api_key = models.CharField(max_length=64, default=uuid.uuid4, unique=True)
    gemini_api_key = models.CharField(max_length=150, blank=True, null=True)
    is_alerts_enabled = models.BooleanField(default=True)
    min_score_alert = models.FloatField(default=7.0)
    min_market_cap_alert = models.FloatField(default=10000.0)
    plan_name = models.CharField(max_length=50, default="Free Community Alpha")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile - {self.user.username}"


class TokenCall(models.Model):
    """Scanned token calls with on-chain telemetry, AI ratings, and safety metrics."""
    meta_data = models.JSONField(default=dict)
    added_date = models.DateTimeField(default=timezone.now)
    thesis = models.TextField(default="No thesis yet")
    token_CA = models.CharField(max_length=2000, db_index=True)
    chain = models.CharField(max_length=50, default='solana')
    score = models.FloatField(default=7.0)

    class Meta:
        ordering = ['-added_date']

    def __str__(self):
        return f"{self.symbol} ({self.token_CA[:8]}...) - Score: {self.score}"

    @property
    def is_passed(self):
        """Returns True if the token passed scanner safety evaluation (score >= 7.0)."""
        return self.score >= 7.0

    @property
    def symbol(self):
        meta = self.meta_data or {}
        return meta.get('symbol') or meta.get('token_symbol') or 'COIN'

    @property
    def name(self):
        meta = self.meta_data or {}
        return meta.get('name') or meta.get('token_name') or self.symbol

    @property
    def logo(self):
        meta = self.meta_data or {}
        logo_url = meta.get('logo') or meta.get('token_logo')
        if logo_url and str(logo_url).startswith('http'):
            return logo_url
        if '0x' in str(self.token_CA).lower() or self.chain == 'bsc':
            return 'https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png'
        return 'https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png'

    @property
    def market_cap(self):
        meta = self.meta_data or {}
        val = meta.get('usd_market_cap') or meta.get('market_cap') or 0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @property
    def liquidity(self):
        meta = self.meta_data or {}
        val = meta.get('liquidity') or meta.get('liquidUsd') or 0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @property
    def launchpad(self):
        meta = self.meta_data or {}
        if meta.get('launchpad'):
            return meta.get('launchpad')
        if str(self.token_CA).endswith('pump'):
            return 'Pump.fun'
        if '0x' in str(self.token_CA).lower() or self.chain == 'bsc':
            return 'PancakeSwap'
        return 'Raydium'

    @property
    def pool_address(self):
        meta = self.meta_data or {}
        return meta.get('pool_address') or self.token_CA

    @property
    def top_10_percent(self):
        meta = self.meta_data or {}
        val = meta.get('top_10_holder_rate') or 0
        try:
            return round(float(val) * 100, 1)
        except (ValueError, TypeError):
            return 0.0

    @property
    def creator_hold_percent(self):
        meta = self.meta_data or {}
        val = meta.get('creator_balance_rate') or 0
        try:
            return round(float(val) * 100, 1)
        except (ValueError, TypeError):
            return 0.0

    @property
    def bundler_percent(self):
        meta = self.meta_data or {}
        val = meta.get('bundler_trader_amount_rate') or 0
        try:
            return round(float(val) * 100, 1)
        except (ValueError, TypeError):
            return 0.0

    @property
    def sniper_count(self):
        meta = self.meta_data or {}
        try:
            return int(meta.get('sniper_count') or 0)
        except (ValueError, TypeError):
            return 0

    @property
    def holder_count(self):
        meta = self.meta_data or {}
        try:
            return int(meta.get('holder_count') or 0)
        except (ValueError, TypeError):
            return 0

    @property
    def twitter_link(self):
        meta = self.meta_data or {}
        tw = meta.get('twitter')
        if not tw:
            return None
        if str(tw).startswith('http'):
            return tw
        return f"https://x.com/{str(tw).lstrip('@')}"

    @property
    def website_link(self):
        meta = self.meta_data or {}
        return meta.get('website')

    @property
    def telegram_link(self):
        meta = self.meta_data or {}
        tg = meta.get('telegram')
        if not tg:
            return None
        if str(tg).startswith('http'):
            return tg
        return f"https://t.me/{str(tg).lstrip('@')}"

    @property
    def padre_url(self):
        chain_slug = 'bsc' if ('0x' in str(self.token_CA).lower() or self.chain == 'bsc') else 'solana'
        return f"https://trade.padre.gg/trade/{chain_slug}/{self.pool_address}"

    @property
    def rugcheck_url(self):
        return f"https://rugcheck.xyz/tokens/{self.token_CA}"

    @property
    def price(self):
        meta = self.meta_data or {}
        p = meta.get('price') or meta.get('priceUsd')
        if p is not None:
            try:
                val = float(p)
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
        mcap = self.market_cap
        try:
            supply = float(meta.get('total_supply') or 0)
            if supply > 0 and mcap > 0:
                return mcap / supply
        except (ValueError, TypeError):
            pass
        return 0.0

    @property
    def price_formatted(self):
        p = self.price
        if p >= 1.0:
            return f"${p:,.2f}"
        elif p >= 0.01:
            return f"${p:,.4f}"
        elif p > 0:
            return f"${p:.7f}".rstrip('0')
        return "$0.00"

    @property
    def mcap_formatted(self):
        val = self.market_cap
        if val >= 1_000_000_000:
            return f"${val / 1_000_000_000:.2f}B"
        elif val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        elif val >= 1_000:
            return f"${val / 1_000:.1f}K"
        elif val > 0:
            return f"${val:.0f}"
        return "$0"

    @property
    def vol_formatted(self):
        meta = self.meta_data or {}
        vol_info = meta.get('volume') if isinstance(meta.get('volume'), dict) else {}
        val = meta.get('volume_24h') or vol_info.get('h24') or meta.get('volume_1h') or vol_info.get('h1') or meta.get('volume_6h') or 0
        try:
            val = float(val)
        except (ValueError, TypeError):
            val = 0.0
        if val >= 1_000_000_000:
            return f"${val / 1_000_000_000:.2f}B"
        elif val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        elif val >= 1_000:
            return f"${val / 1_000:.1f}K"
        elif val > 0:
            return f"${val:.0f}"
        return "$0"

    @property
    def liq_formatted(self):
        val = self.liquidity
        if val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        elif val >= 1_000:
            return f"${val / 1_000:.1f}K"
        elif val > 0:
            return f"${val:.0f}"
        return "$0"

    @property
    def age_formatted(self):
        meta = self.meta_data or {}
        created_ts = meta.get('created_timestamp')
        import time
        if created_ts:
            try:
                diff_sec = int(time.time()) - int(created_ts)
                if diff_sec >= 86400:
                    return f"{diff_sec // 86400}d"
                elif diff_sec >= 3600:
                    return f"{diff_sec // 3600}h"
                elif diff_sec >= 60:
                    return f"{diff_sec // 60}m"
                elif diff_sec >= 0:
                    return f"{diff_sec}s"
            except Exception:
                pass
        from django.utils import timezone
        diff = timezone.now() - self.added_date
        if diff.days > 0:
            return f"{diff.days}d"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}h"
        return f"{max(1, diff.seconds // 60)}m"

    @property
    def txns_formatted(self):
        meta = self.meta_data or {}
        txns_dict = meta.get('txns') if isinstance(meta.get('txns'), dict) else {}
        h24_dict = txns_dict.get('h24') or {}
        txns = (
            meta.get('swaps_24h') 
            or (h24_dict.get('buys', 0) + h24_dict.get('sells', 0))
            or meta.get('swaps_1h') 
            or (meta.get('buys_1h', 0) + meta.get('sells_1h', 0))
            or 0
        )
        try:
            val = int(txns)
            return f"{val:,}" if val > 0 else "0"
        except Exception:
            return "0"

    @property
    def traders_formatted(self):
        traders = self.holder_count
        return f"{traders:,}" if traders > 0 else "-"

    @property
    def change_5m(self):
        meta = self.meta_data or {}
        changes_dict = meta.get('priceChange') if isinstance(meta.get('priceChange'), dict) else {}
        val = meta.get('price_change_5m') or changes_dict.get('m5')
        if val is not None:
            try:
                return round(float(val), 2)
            except Exception:
                pass
        v1 = float(meta.get('volume_1m') or 0)
        nb = float(meta.get('net_buy_1m') or 0)
        if v1 > 0:
            return round((nb / v1) * 100, 2)
        return 0.0

    @property
    def change_1h(self):
        meta = self.meta_data or {}
        changes_dict = meta.get('priceChange') if isinstance(meta.get('priceChange'), dict) else {}
        val = meta.get('price_change_1h') or changes_dict.get('h1')
        if val is not None:
            try:
                return round(float(val), 2)
            except Exception:
                pass
        v = float(meta.get('volume_1h') or 0)
        nb = float(meta.get('net_buy_1h') or 0)
        if v > 0:
            return round((nb / v) * 100, 2)
        return 0.0

    @property
    def change_6h(self):
        meta = self.meta_data or {}
        changes_dict = meta.get('priceChange') if isinstance(meta.get('priceChange'), dict) else {}
        val = meta.get('price_change_6h') or changes_dict.get('h6')
        if val is not None:
            try:
                return round(float(val), 2)
            except Exception:
                pass
        v = float(meta.get('volume_6h') or 0)
        nb = float(meta.get('net_buy_6h') or 0)
        if v > 0:
            return round((nb / v) * 100, 2)
        return 0.0

    @property
    def change_24h(self):
        meta = self.meta_data or {}
        changes_dict = meta.get('priceChange') if isinstance(meta.get('priceChange'), dict) else {}
        val = meta.get('price_change_24h') or changes_dict.get('h24')
        if val is not None:
            try:
                return round(float(val), 2)
            except Exception:
                pass
        v = float(meta.get('volume_24h') or 0)
        nb = float(meta.get('net_buy_24h') or 0)
        if v > 0:
            return round((nb / v) * 100, 2)
        return 0.0


class Watchlist(models.Model):
    """User bookmarked tokens for real-time tracking."""
    user = models.ForeignKey(DjangoUser, on_delete=models.CASCADE, related_name='watchlist')
    token = models.ForeignKey(TokenCall, on_delete=models.CASCADE, related_name='favorited_by', null=True, blank=True)
    token_ca = models.CharField(max_length=255)
    token_name = models.CharField(max_length=255, default='Token')
    token_symbol = models.CharField(max_length=50, default='COIN')
    chain = models.CharField(max_length=50, default='solana')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'token_ca')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.token_symbol}"