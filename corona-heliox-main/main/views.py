import json
import random
import string
import asyncio
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as DjangoUser
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view

from .models import User as LegacyTGUser, UserProfile, TokenCall, Watchlist
from .rug_bundle_check import rug_check
from .ai_analyzer import analyze_with_gemini_or_engine, algorithmic_token_evaluation
from .services import fetch_live_onchain_token
from .web_scraper import SophisticatedWebScraper
from .x_scraper import scrape_twitter_profile

try:
    import telebot
    API_TOKEN = '8333389962:AAFfGjOmZr4bqPVfzRJUIZiP9SUVHwUq7iE'
    bot = telebot.TeleBot(API_TOKEN)
except Exception:
    bot = None


def generate_sync_code():
    return ''.join(random.choices(string.digits, k=6))


# ==========================================
# PUBLIC PAGES & AUTHENTICATION
# ==========================================

def home(request):
    """Root homepage: presents the full DexScreener terminal."""
    return dashboard(request)


def signup_view(request):
    """User registration for free SaaS tier."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        telegram_username = request.POST.get('telegram_username', '').strip()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return render(request, 'signup.html')

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'signup.html')

        if DjangoUser.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already taken. Please choose another.")
            return render(request, 'signup.html')

        # Create Django User
        user = DjangoUser.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Create Profile
        sync_code = generate_sync_code()
        UserProfile.objects.create(
            user=user,
            telegram_username=telegram_username.lstrip('@') if telegram_username else None,
            telegram_sync_code=sync_code
        )

        # Auto login
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f"Welcome to Heliox, @{username}! Your free Alpha account is active.")
            return redirect('dashboard')

    return render(request, 'signup.html')


def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Ensure profile exists
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(
                    user=user,
                    telegram_sync_code=generate_sync_code()
                )
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'login.html')


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


# ==========================================
# SAAS DASHBOARD & CORE TOOLS
# ==========================================

def dashboard(request):
    """Main DexScreener-style Intelligence Terminal Dashboard."""
    profile = None
    user_watchlist_cas = set()
    is_auth = request.user.is_authenticated

    if is_auth:
        profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'telegram_sync_code': generate_sync_code()}
        )
        user_watchlist_cas = set(
            Watchlist.objects.filter(user=request.user).values_list('token_ca', flat=True)
        )

    # Filter parameters
    chain = request.GET.get('chain', 'all')
    min_score = request.GET.get('score', '')
    status_filter = request.GET.get('status', '').strip().lower()
    search = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'newest')
    timeframe = request.GET.get('timeframe', '24h')

    tokens_query = TokenCall.objects.all()

    if chain in ['solana', 'bsc']:
        tokens_query = tokens_query.filter(chain=chain)

    if status_filter == 'passed':
        tokens_query = tokens_query.filter(score__gte=7.0)
    elif status_filter == 'not_passed':
        tokens_query = tokens_query.filter(score__lt=7.0)

    if min_score:
        try:
            tokens_query = tokens_query.filter(score__gte=float(min_score))
        except ValueError:
            pass

    if search:
        tokens_query = tokens_query.filter(
            Q(token_CA__icontains=search) |
            Q(thesis__icontains=search)
        )

    # Sorting
    if sort_by == 'score_desc':
        tokens_query = tokens_query.order_by('-score', '-added_date')
    elif sort_by == 'score_asc':
        tokens_query = tokens_query.order_by('score', '-added_date')
    elif sort_by == 'gainers':
        # Handled or ordered by score / recent
        tokens_query = tokens_query.order_by('-score', '-added_date')
    else:
        tokens_query = tokens_query.order_by('-added_date')

    all_tokens = list(tokens_query[:100])

    # If sorted in python for fields stored in JSON
    if sort_by == 'gainers':
        all_tokens = sorted(all_tokens, key=lambda x: x.change_24h, reverse=True)
    elif sort_by == 'mcap_desc':
        all_tokens = sorted(all_tokens, key=lambda x: x.market_cap, reverse=True)
    elif sort_by == 'vol_desc':
        all_tokens = sorted(all_tokens, key=lambda x: (x.meta_data or {}).get('volume_24h') or (x.meta_data or {}).get('volume_1h') or 0, reverse=True)

    # Calculate real aggregate telemetry from database
    total_vol = 0.0
    total_txns = 0
    for t in all_tokens:
        meta = t.meta_data or {}
        v = meta.get('volume_24h') or meta.get('volume_1h') or 0
        try:
            total_vol += float(v)
        except Exception:
            pass
        tx = meta.get('swaps_24h') or meta.get('swaps_1h') or 0
        try:
            total_txns += int(tx)
        except Exception:
            pass

    if total_vol >= 1_000_000_000:
        total_tracked_volume = f"${total_vol / 1_000_000_000:.2f}B"
    elif total_vol >= 1_000_000:
        total_tracked_volume = f"${total_vol / 1_000_000:.2f}M"
    elif total_vol >= 1_000:
        total_tracked_volume = f"${total_vol / 1_000:.1f}K"
    else:
        total_tracked_volume = f"${total_vol:.0f}"

    total_tracked_txns = f"{total_txns:,}"

    # Metrics & Scan Engine Telemetry
    total_scanned = TokenCall.objects.count()
    passed_count = TokenCall.objects.filter(score__gte=7.0).count()
    not_passed_count = TokenCall.objects.filter(score__lt=7.0).count()
    pass_rate = round((passed_count / total_scanned) * 100, 1) if total_scanned > 0 else 0.0

    alpha_gems_count = TokenCall.objects.filter(score__gte=7.5).count()
    solana_count = TokenCall.objects.filter(chain='solana').count()
    bsc_count = TokenCall.objects.filter(chain='bsc').count()

    context = {
        'is_auth': is_auth,
        'profile': profile,
        'tokens': all_tokens,
        'user_watchlist_cas': user_watchlist_cas,
        'total_scanned': total_scanned,
        'passed_count': passed_count,
        'not_passed_count': not_passed_count,
        'pass_rate': pass_rate,
        'alpha_gems_count': alpha_gems_count,
        'solana_count': solana_count,
        'bsc_count': bsc_count,
        'total_tracked_volume': total_tracked_volume,
        'total_tracked_txns': total_tracked_txns,
        'current_chain': chain,
        'current_score': min_score,
        'current_status': status_filter,
        'current_search': search,
        'current_sort': sort_by,
        'timeframe': timeframe,
    }
    return render(request, 'dashboard.html', context)


@login_required
def token_detail(request, ca):
    """Detailed token intelligence dossier."""
    token = get_object_or_404(TokenCall, token_CA=ca)
    is_in_watchlist = Watchlist.objects.filter(user=request.user, token_ca=ca).exists()
    
    meta = token.meta_data or {}
    
    # Calculate safety scores
    top10_rate = token.top_10_percent
    creator_rate = token.creator_hold_percent
    sniper_count = token.sniper_count
    bundler_rate = token.bundler_percent

    risk_level = "LOW RISK"
    risk_color = "emerald"
    if top10_rate > 35 or creator_rate > 10 or bundler_rate > 20:
        risk_level = "HIGH RISK"
        risk_color = "rose"
    elif top10_rate > 25 or creator_rate > 5 or sniper_count > 20:
        risk_level = "MODERATE RISK"
        risk_color = "amber"

    context = {
        'token': token,
        'meta': meta,
        'is_in_watchlist': is_in_watchlist,
        'risk_level': risk_level,
        'risk_color': risk_color,
    }
    return render(request, 'token_detail.html', context)


@login_required
def manual_scan(request):
    """Interactive scanner tool where users can scan any real contract address."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    scan_result = None
    target_ca = request.GET.get('ca', '').strip()

    if request.method == 'POST':
        target_ca = request.POST.get('ca', '').strip()

    if target_ca:
        # Check if already scanned in DB
        existing_token = TokenCall.objects.filter(token_CA=target_ca).first()
        if existing_token and existing_token.thesis and existing_token.thesis != 'No thesis yet':
            scan_result = {
                'token': existing_token,
                'analysis': {
                    'score': existing_token.score,
                    'trading_thesis': existing_token.thesis,
                    'immediate_trading_thesis': "Pre-Scanned Record"
                }
            }
        else:
            # Query real live onchain telemetry from DexScreener & Solana RPC
            live_data = fetch_live_onchain_token(target_ca)
            if not live_data:
                messages.error(request, f"No active on-chain liquidity pool found on DexScreener for address: {target_ca}")
            else:
                # Run AI Analysis on 100% real on-chain telemetry
                analysis = analyze_with_gemini_or_engine(live_data, api_key=profile.gemini_api_key)
                eval_score = float(analysis.get('score', 7.0))
                passed_str = "PASSED" if eval_score >= 7.0 else "NOT PASSED"
                sym = live_data.get('symbol', 'UNKNOWN')
                chain = live_data.get('chain', 'solana')
                mcap = live_data.get('usd_market_cap', 0)

                print(f"[MANUAL SCAN] Real-time scan: ${sym} on {chain.upper()} | Score: {eval_score:.1f}/10 | Status: {passed_str} | MCAP: ${mcap:,.0f} | CA: {target_ca[:8]}...", flush=True)

                # Save or update TokenCall
                if existing_token:
                    existing_token.thesis = analysis.get('trading_thesis', '')
                    existing_token.score = eval_score
                    existing_token.meta_data = live_data
                    existing_token.save()
                    saved_token = existing_token
                else:
                    saved_token = TokenCall.objects.create(
                        token_CA=target_ca,
                        chain=chain,
                        score=eval_score,
                        thesis=analysis.get('trading_thesis', ''),
                        meta_data=live_data
                    )

                scan_result = {
                    'token': saved_token,
                    'analysis': analysis
                }

    context = {
        'scan_result': scan_result,
        'target_ca': target_ca,
        'profile': profile,
    }
    return render(request, 'scanner.html', context)


@login_required
def watchlist_view(request):
    """User bookmarked watchlist page."""
    watchlist_items = Watchlist.objects.filter(user=request.user).select_related('token')
    context = {
        'watchlist_items': watchlist_items,
    }
    return render(request, 'watchlist.html', context)


@require_POST
def toggle_watchlist(request):
    """AJAX endpoint to add/remove token from watchlist."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'login_required', 'message': 'Please sign in to star tokens to your watchlist.'}, status=401)
    ca = request.POST.get('ca', '').strip()
    if not ca:
        return JsonResponse({'status': 'error', 'message': 'Missing CA'}, status=400)

    token = TokenCall.objects.filter(token_CA=ca).first()
    existing = Watchlist.objects.filter(user=request.user, token_ca=ca).first()

    if existing:
        existing.delete()
        return JsonResponse({'status': 'removed', 'ca': ca})
    else:
        Watchlist.objects.create(
            user=request.user,
            token=token,
            token_ca=ca,
            token_name=token.name if token else 'Custom Token',
            token_symbol=token.symbol if token else 'COIN',
            chain=token.chain if token else 'solana'
        )
        return JsonResponse({'status': 'added', 'ca': ca})


@login_required
def telegram_settings(request):
    """Telegram Bot connection & alert configuration."""
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'telegram_sync_code': generate_sync_code()}
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_preferences':
            profile.is_alerts_enabled = 'is_alerts_enabled' in request.POST
            profile.min_score_alert = float(request.POST.get('min_score_alert', 7.0))
            profile.min_market_cap_alert = float(request.POST.get('min_market_cap_alert', 10000.0))
            profile.telegram_chat_id = request.POST.get('telegram_chat_id', '').strip() or None
            profile.save()
            messages.success(request, "Telegram alert preferences updated.")
        elif action == 'regenerate_code':
            profile.telegram_sync_code = generate_sync_code()
            profile.save()
            messages.info(request, f"New sync code generated: {profile.telegram_sync_code}")

    context = {
        'profile': profile,
    }
    return render(request, 'telegram.html', context)


@login_required
def profile_settings(request):
    """User account settings & developer API credentials."""
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'telegram_sync_code': generate_sync_code()}
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            email = request.POST.get('email', '').strip()
            gemini_key = request.POST.get('gemini_api_key', '').strip()
            request.user.email = email
            request.user.save()
            profile.gemini_api_key = gemini_key or None
            profile.save()
            messages.success(request, "Profile updated successfully.")
        elif action == 'regenerate_api_key':
            import uuid
            profile.api_key = str(uuid.uuid4())
            profile.save()
            messages.info(request, "Your API key has been regenerated.")

    context = {
        'profile': profile,
    }
    return render(request, 'profile.html', context)


@login_required
def api_docs(request):
    """Developer API Documentation page."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    context = {
        'profile': profile,
    }
    return render(request, 'api_docs.html', context)


# ==========================================
# REST API ENDPOINTS (BOT & SCANNERS)
# ==========================================

@api_view(['POST'])
def scan_coin(request):
    """
    Scans a coin CA.
    Accepts: { 'ca': '...', 'chat_id': '...' }
    Returns analysis JSON and broadcasts to Telegram if chat_id provided.
    """
    token_ca = request.data.get('ca')
    chat_id = request.data.get('chat_id')

    if not token_ca:
        return Response({"error": "Missing contract address ('ca')"}, status=status.HTTP_400_BAD_REQUEST)

    coin = TokenCall.objects.filter(token_CA=token_ca).first()
    coin_info = coin.meta_data if coin else {}
    
    token_name = coin.name if coin else coin_info.get('name', 'Unknown')
    token_symbol = coin.symbol if coin else coin_info.get('symbol', 'COIN')
    market_cap = coin.market_cap if coin else coin_info.get('usd_market_cap', 25000)
    token_logo = coin.logo if coin else coin_info.get('logo', '')

    final_data = {
        "token_name": token_name,
        "token_symbol": token_symbol,
        "market_cap": market_cap,
        "token_ca": token_ca,
        "top_10_holder_rate": coin_info.get('top_10_holder_rate', 0.20),
        "creator_balance_rate": coin_info.get('creator_balance_rate', 0.04),
        "bundler_trader_amount_rate": coin_info.get('bundler_trader_amount_rate', 0.0),
        "sniper_count": coin_info.get('sniper_count', 0),
        "website": coin_info.get('website'),
        "twitter": coin_info.get('twitter'),
    }

    # Run AI analysis
    ai_response = analyze_with_gemini_or_engine(final_data)

    # Save to database
    if coin:
        coin.thesis = ai_response.get('trading_thesis', '')
        coin.score = float(ai_response.get('score', 7.0))
        coin.save()
    else:
        chain = 'bsc' if ('0x' in str(token_ca).lower()) else 'solana'
        coin = TokenCall.objects.create(
            token_CA=token_ca,
            chain=chain,
            thesis=ai_response.get('trading_thesis', ''),
            score=float(ai_response.get('score', 7.0)),
            meta_data=final_data
        )

    # Send telegram alert if bot and chat_id are present
    if bot and chat_id:
        try:
            caption = (
                f"*${token_symbol} Analysis (Heliox)*\n\n"
                f"*Score*: `{ai_response.get('score', 7.0)}/10`\n"
                f"*Market Cap*: `${market_cap:,.0f}`\n"
                f"*CA*: `{token_ca}`\n\n"
                f"*Thesis*: {ai_response.get('trading_thesis', 'N/A')}\n"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            chain_slug = 'bsc' if ('0x' in str(token_ca).lower()) else 'solana'
            markup.add(
                telebot.types.InlineKeyboardButton("View on Padre", url=f"https://trade.padre.gg/trade/{chain_slug}/{token_ca}"),
                telebot.types.InlineKeyboardButton("Heliox Terminal", url=f"http://127.0.0.1:8000/token/{token_ca}/")
            )
            if token_logo and str(token_logo).startswith('http'):
                bot.send_photo(chat_id, token_logo, caption=caption, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.send_message(chat_id, caption, parse_mode='Markdown', reply_markup=markup)
        except Exception as e:
            print(f"[Telegram notify error]: {e}")

    return Response({
        "status": "success",
        "coin_data": final_data,
        "analysis": ai_response
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def kabal_coin_check(request):
    """Kabal cluster check for Solana tokens."""
    token_ca = request.data.get('token_ca') or request.data.get('ca')
    if not token_ca:
        return Response({"error": "Missing token_ca"}, status=status.HTTP_400_BAD_REQUEST)

    rug_bundle_result = rug_check([token_ca])

    return Response({
        "token_ca": token_ca,
        "kabal_coin_percentage": rug_bundle_result,
        "risk_level": "High" if rug_bundle_result > 30 else "Safe"
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def register_user(request):
    """Registers a Telegram chat ID with Heliox API."""
    username = request.data.get('username')
    chat_id = request.data.get('chat_id')

    if not chat_id:
        return Response({"error": "Missing chat_id"}, status=status.HTTP_400_BAD_REQUEST)

    user = LegacyTGUser.objects.filter(chat_id=chat_id).first()
    if user:
        return Response({"message": "User already registered"}, status=status.HTTP_200_OK)
    
    LegacyTGUser.objects.create(username=username, chat_id=chat_id)
    return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def sync_telegram_account(request):
    """
    Syncs a Telegram chat ID to a Web SaaS user account using their 6-digit sync code.
    Called by the Telegram Bot command `/sync <code>`.
    """
    sync_code = request.data.get('code')
    chat_id = request.data.get('chat_id')
    tg_username = request.data.get('username')

    if not sync_code or not chat_id:
        return Response({"error": "Missing sync code or chat_id"}, status=status.HTTP_400_BAD_REQUEST)

    profile = UserProfile.objects.filter(telegram_sync_code=sync_code).first()
    if not profile:
        return Response({"error": "Invalid or expired sync code. Check your Heliox dashboard."}, status=status.HTTP_404_NOT_FOUND)

    profile.telegram_chat_id = str(chat_id)
    if tg_username:
        profile.telegram_username = tg_username
    # Generate fresh code for future security
    profile.telegram_sync_code = generate_sync_code()
    profile.save()

    # Also record in legacy table
    LegacyTGUser.objects.get_or_create(chat_id=str(chat_id), defaults={'username': tg_username})

    return Response({
        "status": "success",
        "message": f"Successfully linked Telegram to Heliox user @{profile.user.username}!",
        "username": profile.user.username
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_chat_ids(request):
    """Returns all registered Telegram chat IDs for scanner broadcast."""
    legacy_ids = list(LegacyTGUser.objects.values_list('chat_id', flat=True))
    profile_ids = list(UserProfile.objects.filter(is_alerts_enabled=True, telegram_chat_id__isnull=False).values_list('telegram_chat_id', flat=True))
    all_chat_ids = list(set([str(cid) for cid in legacy_ids + profile_ids if cid]))
    return Response({"chat_ids": all_chat_ids}, status=status.HTTP_200_OK)


@api_view(['POST'])
def save_coin_info(request):
    """Saves newly scanned token from external Playwright/API scanner."""
    ca = request.data.get('ca')
    coin_info = request.data.get('coin_info') or {}

    if not ca:
        return Response({"error": "Missing ca"}, status=status.HTTP_400_BAD_REQUEST)

    token_call = TokenCall.objects.filter(token_CA=ca).first()
    if token_call:
        return Response({"message": "Token info already saved"}, status=status.HTTP_200_OK)

    chain = 'bsc' if ('0x' in str(ca).lower()) else 'solana'
    
    # Calculate initial score
    eval_result = algorithmic_token_evaluation(coin_info)
    score = eval_result.get('score', 7.0)
    passed_str = "PASSED" if score >= 7.0 else "NOT PASSED"
    sym = coin_info.get('symbol', 'COIN')
    name = coin_info.get('name', 'Unknown')
    mcap = coin_info.get('usd_market_cap', 0)

    print(f"[SCANNER WORKER] Scanned ${sym} ({name}) on {chain.upper()} | Score: {score:.1f}/10 | Status: {passed_str} | MCAP: ${mcap:,.0f} | CA: {ca[:8]}...", flush=True)

    new_token = TokenCall.objects.create(
        token_CA=ca,
        chain=chain,
        meta_data=coin_info,
        thesis=eval_result.get('trading_thesis', 'Analyzed by Heliox Alpha Radar'),
        score=score
    )

    # Automatically broadcast Telegram alert if token PASSED filter (score >= 7.0)
    if bot and score >= 7.0:
        try:
            legacy_ids = list(LegacyTGUser.objects.values_list('chat_id', flat=True))
            profile_ids = list(UserProfile.objects.filter(is_alerts_enabled=True, min_score_alert__lte=score, telegram_chat_id__isnull=False).values_list('telegram_chat_id', flat=True))
            all_chat_ids = list(set([str(cid) for cid in legacy_ids + profile_ids if cid]))

            caption = (
                f"*New Alpha Token Detected (Passed Filter)*\n\n"
                f"*Token*: `${sym}` ({name})\n"
                f"*Chain*: `{chain.upper()}`\n"
                f"*Score*: `{score:.1f}/10`\n"
                f"*Market Cap*: `${mcap:,.0f}`\n"
                f"*CA*: `{ca}`\n\n"
                f"*Thesis*: {eval_result.get('trading_thesis', 'Passed algorithmic on-chain audit.')}\n"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton("View on Padre", url=f"https://trade.padre.gg/trade/{chain}/{new_token.pool_address}"),
                telebot.types.InlineKeyboardButton("Heliox Terminal", url=f"http://127.0.0.1:8000/token/{ca}/")
            )

            token_logo = new_token.logo
            for cid in all_chat_ids:
                try:
                    if token_logo and str(token_logo).startswith('http'):
                        bot.send_photo(cid, token_logo, caption=caption, parse_mode='Markdown', reply_markup=markup)
                    else:
                        bot.send_message(cid, caption, parse_mode='Markdown', reply_markup=markup)
                    print(f"[TELEGRAM ALERT] Push alert sent for ${sym} to chat {cid}", flush=True)
                except Exception as tg_err:
                    print(f"[TELEGRAM ALERT ERROR] Failed sending to {cid}: {tg_err}", flush=True)
        except Exception as bcast_err:
            print(f"[TELEGRAM BROADCAST ERROR]: {bcast_err}", flush=True)

    return Response({
        "message": "Token info saved successfully",
        "id": new_token.id,
        "score": new_token.score,
        "is_passed": score >= 7.0
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def api_tokens(request):
    """Developer API: List and filter scanned tokens."""
    chain = request.GET.get('chain')
    min_score = request.GET.get('min_score')
    limit = int(request.GET.get('limit', 50))

    query = TokenCall.objects.all()
    if chain:
        query = query.filter(chain=chain)
    if min_score:
        try:
            query = query.filter(score__gte=float(min_score))
        except ValueError:
            pass

    tokens = query[:min(limit, 100)]
    data = []
    for t in tokens:
        data.append({
            "ca": t.token_CA,
            "name": t.name,
            "symbol": t.symbol,
            "chain": t.chain,
            "score": t.score,
            "market_cap": t.market_cap,
            "liquidity": t.liquidity,
            "top_10_percent": t.top_10_percent,
            "creator_hold_percent": t.creator_hold_percent,
            "thesis": t.thesis,
            "added_date": t.added_date.isoformat(),
            "padre_url": t.padre_url,
            "rugcheck_url": t.rugcheck_url
        })

    return Response({"count": len(data), "tokens": data}, status=status.HTTP_200_OK)