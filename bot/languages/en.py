from config import URL_PAYMENT

EN_CONFIGURATION = {
  "start_text": {
    "greeting": "Hello! I'm ZdormanBot 👋\nI'll tell you how to get a subscription to our service 📈 and why you can trust us 😎",
  },
  "start_btn": {
    "url_tg": "Our Telegram",
    "personal_account": "Personal account",
    "subscription_buy": "Buy subscription",
    "prolong_subscription": "Prolong subscription",
  }, # -------------------------------------------------------------
  "subscription_text": {
    "buy_info": f"Payment for 1 month = 49$\nWallet URL - {URL_PAYMENT}\nPayment type: TRC-20\nP.S. Payments are accepted only from exchange accounts.\nAfter payment, click the 'Paid' button and enter the payment ID.",
    "question": "After payment, click the 'Paid' button and enter the payment ID. Then the administration will verify your payment within 24 hours and activate your subscription.",
    "paid": "Great! Now you only need to enter the payment ID. Click the 'Enter payment ID' button and provide the payment ID.\nThen the administration will verify your payment within 24 hours and activate your subscription.",
    "input_payment_id": "Enter the payment ID in chat",
    "confirm_payment": "Is everything correct: {payment_id}",
    "confirm_payment_success": "Thanks for your payment! The administration will verify your payment within 24 hours and activate your subscription.",
    "subscription_reminder_3d": (
        "Dear subscriber,\n\n"
        "Your subscription will expire in 3 days ({end_date}).\n"
        "Please renew in the bot so trading is not interrupted."
    ),
    "subscription_reminder_1d": (
        "Dear subscriber,\n\n"
        "Your subscription will expire in 1 day ({end_date}).\n"
        "Please renew in the bot to keep access to the algorithm."
    ),
    "subscription_expired": (
        "Dear subscriber,\n\n"
        "Your subscription has expired ({end_date}) and has been deactivated.\n"
        "Renew or purchase a subscription in the bot to continue."
    ),
  },
  "subscription_btn": {
    "paid": "Paid",
    "question": "What's next?",
    "input_payment_id": "Enter payment ID",
    "confirm_payment": "Yes ✓",
    "reject_payment": "No ✗",
  }, # -------------------------------------------------------------
  "profile_text": {
    "profile_menu": "My profile 👤\nSubscription start date: {payment_date}\nSubscription type: {subscription_type}\nTrade amount: {sum_for_trades}\nAPI key provided: {api_key}",
    "profile_menu_without_subscription": "My profile 👤\n\n🚫 Subscription is not active\n💬 Click the button below and follow the instructions to activate your subscription",
    "profile_menu_wait_sub_confirmation": "My profile 👤\n\n🎉 Thank you for your payment!\n🕒 Waiting for subscription confirmation\n💬 Please wait up to 24 hours for payment confirmation",
    "profile_settings_sum_for_trades": "Enter a new trade amount\n\nRecommended trade amount: {recommended_usdt} USDT",
    "profile_settings_sum_for_trades_fallback": "Enter a new trade amount",
    "profile_settings_sum_for_trades_risk_warning": "⚠️ Are you sure?\n\nYou entered: {entered_sum} USDT\nRecommended amount: {recommended_usdt} USDT\n\nThis value leads to higher risks when running the algorithm.",
    "profile_balance": "💰 Futures account balance: {balance} USDT",
    "profile_balance_api_missing": "❌ Could not fetch balance: API key/secret are missing in profile settings.",
    "profile_balance_error": "❌ Could not fetch balance. Please try again later.",
    "profile_history_trades_title": "📋 Trade history (last {count})",
    "profile_history_trades_page": "Page {page}/{pages} · total {total}",
    "profile_history_trades_empty": "📋 Trade history is empty.",
    "profile_history_trades_error": "❌ Could not fetch trade history. Please try again later.",
    "profile_history_trade_details_title": "📄 Trade",
    "trading_menu": "📈 Trading\n\nChoose an action:",
    "active_trades_page_title": "🟢 Active trades\nPage {page}/{pages} · total {total}",
    "active_trades_empty": "🟢 No active trades.",
    "active_trades_error": "❌ Could not fetch active trades. Please try again later.",
    "active_trade_details_title": "📄 Active trade",
    "active_trade_not_found": "❌ Could not fetch active trade data for {symbol}.",
    "active_trade_stop_success": "🛑 Trading for {symbol} stopped.\n{message}",
    "active_trade_stop_error": "❌ Could not stop trading for {symbol}.",
    "stop_all_trading_success": "🛑 All trading stopped.\n{message}",
    "stop_all_trading_error": "❌ Could not stop all trading.",
  },
  "profile_btn": {
    "subscription_buy": "Buy subscription",
    "tech_support": "Tech support",
    "confirm_risk_sum_for_trades": "✅ Yes, set amount",
    "cancel_risk_sum_for_trades": "✏️ No, enter another",
    "active_trades": "🟢 Active trades",
    "stop_all_trading": "🛑 Stop all trading",
    "stop_current_trade": "🛑 Stop current trade",
  }, # -------------------------------------------------------------
  "admin_text": {
    "admin_menu": "Admin panel 👨‍💻\n\nChoose an action:",
    "error_search_user": "Find a user first. 🚫",
    "error_user_not_found": "User not found in the database. 🚫",
    "edit_api_key": "Enter the new API key",
    "edit_api_secret": "Enter the new API secret",
    "edit_sum_for_trades": "Enter the new trade amount",
    "edit_api_key_success": "API key updated.",
    "edit_api_secret_success": "API secret updated.",
    "edit_sum_for_trades_success": "Trade amount updated: {sum_for_trades}",
    "stop_all_trading_success": "✅ All trading has been stopped\n\n{message}",
    "stop_all_trading_error": "❌ Failed to stop all trading\n\n{error}",
    "user_not_subscriber": "User is not a subscriber 🚫",
    "user_not_wait_confirm": "This user is not waiting for confirmation 🚫",
    "wait_confirm_list_title": "Waiting for subscription confirmation\n\nPage {page} of {pages} · total {total}",
    "wait_confirm_list_empty": "No one is waiting for confirmation.",
    "subscribers_list_title": "Subscribers\n\nPage {page} of {pages} · total {total}",
    "subscribers_list_empty": "No subscribers yet.",
  }, # -------------------------------------------------------------
  "admin_btn": {
    "users_list": "Users",
    "statistics": "Statistics",
    "stop_all_trading": "🛑 Stop all trading",
    "edit_api_key": "Change API key",
    "edit_api_secret": "Change API secret",
    "edit_sum_for_trades": "Change trade amount",
    "edit_stop_trading_stop_mode": "Stop trading",
    "edit_stop_trading_resume_mode": "Resume trading",
    "list_prev_page": "◀️ Prev",
    "list_next_page": "Next ▶️",
    "back_to_user_list": "Back to list",
    "proccess_search_wair_confirm": "Search again",
    "back_menu_wait_confirm": "Back to menu",
    "subscription_settings": "Subscription settings ⚙️",
    "bybit_settings": "Bybit settings ⚙️",
    "statistics_info": "Statistics 📊",
    "confirm_subscription": "Confirm subscription",
    "cancel_subscription": "Reject request",
    "prolong_subscription": "Extend subscription",
    "cancel_prolong_subscription": "Reject extension",
    "edit_subscription_true_mode": "Enable subscription",
    "edit_subscription_false_mode": "Disable subscription",
    "edit_date_end_subs": "Change subscription end date",
    "trading_list": "Trades list",
  }, # -------------------------------------------------------------
  "general": {
    "back": "⬅️ Back",
    "admin_to_main_menu": "Main menu",
  }
}