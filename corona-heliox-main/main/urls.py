from django.urls import path
from . import views

urlpatterns = [
    # SaaS Frontend Routes
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('token/<str:ca>/', views.token_detail, name='token_detail'),
    path('scanner/', views.manual_scan, name='manual_scan'),
    path('watchlist/', views.watchlist_view, name='watchlist'),
    path('watchlist/toggle/', views.toggle_watchlist, name='toggle_watchlist'),
    path('telegram/', views.telegram_settings, name='telegram_settings'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('api-docs/', views.api_docs, name='api_docs'),

    # Authentication Routes
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # REST APIs (SaaS, Telegram Bot, & Scanners)
    path('api/scan/', views.scan_coin, name='manually_scan_coin'),
    path('api/kabal_coin_check/', views.kabal_coin_check, name='kabal_coin_check'),
    path('api/register/', views.register_user, name='register_user'),
    path('api/sync_tg/', views.sync_telegram_account, name='sync_telegram_account'),
    path('api/get_chat_ids/', views.get_chat_ids, name='get_chat_ids'),
    path('api/save_coin/', views.save_coin_info, name='save_coin'),
    path('api/tokens/', views.api_tokens, name='api_tokens'),
]