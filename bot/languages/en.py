from config import URL_PAYMENT, SUBSCRIPTION_PRICE_USD

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
    "buy_info": f"Payment for 1 month = {SUBSCRIPTION_PRICE_USD}$\nWallet URL - {URL_PAYMENT}\nPayment type: TRC-20\nP.S. Payments are accepted only from exchange accounts.\nAfter payment, click the 'Paid' button and enter the payment ID.",
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
    "payment_confirmed": "✅ Your payment has been confirmed! Your subscription is active.",
    "payment_rejected": "❌ Payment was not confirmed. Contact support if you have questions.",
    "prolong_confirmed": "✅ Subscription extension confirmed!",
    "prolong_rejected": "❌ Subscription extension was rejected. Contact support if you have questions.",
  },
  "subscription_btn": {
    "paid": "Paid",
    "question": "What's next?",
    "input_payment_id": "Enter payment ID",
    "confirm_payment": "Yes ✓",
    "reject_payment": "No ✗",
  }, # -------------------------------------------------------------
  "profile_text": {
    "profile_menu": "My profile 👤\nSubscription start date: {payment_date}\nSubscription type: {subscription_type}\nTrade amount: {sum_for_trades}\nAPI key provided: {api_key}\n{api_key_expiry_line}",
    "profile_menu_without_subscription": "My profile 👤\n\n🚫 Subscription is not active\n💬 Click the button below and follow the instructions to activate your subscription",
    "profile_menu_wait_sub_confirmation": "My profile 👤\n\n🎉 Thank you for your payment!\n🕒 Waiting for subscription confirmation\n💬 Please wait up to 24 hours for payment confirmation",
    "profile_settings": "⚙️ Settings \n\nAPI key: {api_key}\nAPI secret: {api_secret}\nTrade amount: {sum_for_trades}\n{api_key_expiry_line}",
    "profile_settings_api_key": "Enter the new API key",
    "profile_settings_api_secret": "Enter the new API secret",
    "api_key_instruction_caption": "📹 Guide: how to create a Bybit API key.\n\nAfter watching, tap «Enter API key».",
    "profile_settings_sum_for_trades": "Enter a trade amount\n\nRecommended amount: {recommended_usdt} USDT",
    "profile_settings_sum_for_trades_limited": (
        "Enter a trade amount\n\n"
        "Amount not higher than: {max_usdt} USDT\n"
        "({percent}% of your futures balance)\n\n"
        "This service rule helps protect your deposit: during averaging and stops the algorithm uses several orders, "
        "and an oversized trade amount sharply increases drawdown risk."
    ),
    "profile_settings_sum_for_trades_api_required": (
        "To calculate the permitted trade amount, set your API key and secret in profile settings first.\n\n"
        "After saving the keys, come back here — we will show the maximum amount per service rules."
    ),
    "profile_settings_sum_for_trades_balance_zero": (
        "Could not calculate the limit: futures balance is zero or the API key cannot read the balance.\n\n"
        "Top up your Bybit account and check API key permissions, then try again."
    ),
    "profile_settings_sum_for_trades_fallback": "Enter a trade amount",
    "profile_settings_sum_for_trades_exceeds_limit": (
        "Amount {entered_sum} USDT exceeds the permitted limit.\n\n"
        "Per project rules, the maximum trade amount is {max_usdt} USDT ({percent}% of your balance). "
        "This limit is for the safety of your trades: it reduces deposit load during a series of averaging orders.\n\n"
        "Please enter an amount not higher than {max_usdt} USDT."
    ),
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
    "profile_api_key_expiry": "🔑 API key active for {days_left} more day(s) (until {expiry_date})",
    "api_key_reminder_3d": (
        "⚠️ Attention!\n\n"
        "Your Bybit API key will expire in 3 days ({expiry_date}).\n"
        "Create a new key and update it in the bot settings."
    ),
    "api_key_reminder_1d": (
        "⚠️ Attention!\n\n"
        "Your Bybit API key will expire in 1 day ({expiry_date}).\n"
        "Create a new key and update it in the bot settings."
    ),
    "api_key_expired_today": (
        "❌ Your Bybit API key expires today ({expiry_date}).\n"
        "Create a new key and update it in the bot settings, otherwise trading will stop working."
    ),
  },
  "profile_btn": {
    "subscription_buy": "Buy subscription",
    "tech_support": "Tech support",
    "edit_api_key_secret": "🔑 API Key / Secret",
    "api_key_instruction_enter": "🔑 Enter API key",
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
    "subscribers_main_info": "Name: {name}\nTG ID: {tg_id}\nLanguage: {language}\nTrade amount limit: {trade_amount_limit_status}",
    "trade_amount_limit_unlimited": "disabled (extended mode)",
    "trade_amount_limit_standard": "standard (per service rules)",
    "toggle_unlimited_trade_added": "User can set trade amount above the limit",
    "toggle_unlimited_trade_removed": "Standard trade amount limit restored for user",
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
    "toggle_unlimited_trade_add": "🔓 Allow amount above limit",
    "toggle_unlimited_trade_remove": "🔒 Restore amount limit",
  }, # -------------------------------------------------------------
  "general": {
    "back": "⬅️ Back",
    "admin_to_main_menu": "Main menu",
  }
}