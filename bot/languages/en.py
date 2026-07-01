from config import URL_PAYMENT, SUBSCRIPTION_PRICE_USD

EN_CONFIGURATION = {
  "start_text": {
    "greeting": "Hello! I'm ZdormanBot 👋",
    "greeting_help": "I'll help you subscribe and set up trading on Bybit.",
    "greeting_help_first": "Let me help you subscribe and set up trading on Bybit.",
    "quick_start": "📋 Quick start:\n1. Pay for subscription\n2. Wait for confirmation (up to 24h)\n3. Add your Bybit API key\n4. Set trade amount\n5. Done — the algorithm trades automatically",
    "choose_language": "Choose language / Выберите язык:",
    "welcome_intro": (
        "Trading bot benefits:\n"
        "⚡️ Trade entry in about 1 second after a signal.\n"
        "⚡️ Fully automatic on the 1-minute timeframe.\n"
        "⚡️ Calculates the recommended position size for you.\n"
        "⚡️ Places the full sell order grid automatically.\n"
        "⚡️ Uses a trailing Take Profit to maximize profit.\n"
        "⚡️ No TradingView subscription needed for notifications.\n"
        "⚡️ All entry, exit, and system messages arrive in Telegram.\n"
        "⚡️ With recommended settings, full liquidation risk is minimized.\n\n"
        "Notes:\n"
        "• Works on Bybit only.\n"
        "• Designed exclusively for 1-minute timeframe trading."
    ),
  },
  "start_btn": {
    "url_tg": "📢 Our Telegram channel",
    "personal_account": "👤 Profile",
    "onboarding_progress": "📋 Connection progress",
    "onboarding_setup": "⚙️ Setup",
    "subscription_buy": "💳 Buy subscription",
    "prolong_subscription": "🔄 Extend subscription",
  }, # -------------------------------------------------------------
  "subscription_text": {
    "buy_info": f"Payment for 1 month = {SUBSCRIPTION_PRICE_USD}$\nWallet URL - {URL_PAYMENT}\nPayment type: TRC-20\nP.S. Payments are accepted only from exchange accounts.\nAfter payment, click the 'Paid' button and enter the payment ID.",
    "question": "After payment, click the 'Paid' button and enter the payment ID. Then the administration will verify your payment within 24 hours and activate your subscription.",
    "paid": "Great! Now you only need to enter the payment ID. Click the 'Enter payment ID' button and provide the payment ID.\nThen the administration will verify your payment within 24 hours and activate your subscription.",
    "input_payment_id": "Enter the payment ID in chat",
    "confirm_payment": "Is everything correct: {payment_id}",
    "confirm_payment_success": "Thank you! Your request has been sent.\n\nAn admin will verify payment within 24 hours. While you wait, you can set up your Bybit API key in profile settings.",
    "prolong_subscription": f"🔄 Extend subscription\n\n1️⃣ Send {SUBSCRIPTION_PRICE_USD}$ to:\n{URL_PAYMENT}\n   Network: TRC-20\n2️⃣ Tap «✅ I paid»\n3️⃣ Enter payment ID and confirm",
    "prolong_paid": "Great! Tap «Enter payment ID» and send the transfer ID in chat.",
    "prolong_question": "📋 After extension payment:\n\n1. Tap «✅ I paid»\n2. Enter payment ID\n3. Confirm\n4. Admin will extend within 24 hours",
    "prolong_confirm_payment_success": "Thank you! Extension request sent.\n\nAdmin will verify within 24 hours.",
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
    "paid": "✅ I paid",
    "question": "📋 Payment guide",
    "input_payment_id": "📝 Enter payment ID",
    "confirm_payment": "✅ Correct",
    "reject_payment": "✏️ Fix ID",
  }, # -------------------------------------------------------------
  "profile_text": {
    "profile_menu": "My profile 👤\n\nSubscription date: {payment_date}\nType: {subscription_type}\nTrade amount: {sum_for_trades} USDT\nBybit API key: {api_key}\n{api_key_expiry_line}\n\n{onboarding_checklist}",
    "profile_menu_without_subscription": (
        "Service onboarding 🚀\n\n"
        "Here you can see your progress and next steps.\n"
        "Full profile (settings, trading, statistics) unlocks after subscription activation.\n\n"
        "{onboarding_checklist}\n\n"
        "👇 Start with a subscription below"
    ),
    "profile_menu_wait_sub_confirmation": (
        "Service onboarding 🚀\n\n"
        "🎉 Payment sent for review\n"
        "🕒 Waiting for confirmation (up to 24h)\n\n"
        "{onboarding_checklist}\n\n"
        "💡 While waiting — you can set up your API key below"
    ),
    "profile_statistics": "📊 Statistics\n\nTotal trades: {total_trades}\nTotal PnL: {total_pnl}\nWinning trades: {positive_trades}\nProfit from wins: {sum_positive_trades}\nLosing trades: {negative_trades}\nLoss from losses: {sum_negative_trades}",
    "profile_settings": "⚙️ Settings\n\n🔑 API key: {api_key}\n🔐 API secret: {api_secret}\n💵 Trade amount: {sum_for_trades} USDT\n{api_key_expiry_line}\n\n{settings_hint}",
    "settings_hint_api_first": "Add your Bybit API key first — then you can set the trade amount.",
    "settings_hint_ready": "Set API key and trade amount — otherwise the algorithm cannot trade.",
    "settings_hint_sum": "Set trade amount — the last step before trading starts.",
    "onboarding_checklist_title": "📋 Your progress:",
    "onboarding_step_subscription": "Subscription payment submitted",
    "onboarding_step_wait_confirm": "Subscription activated by admin",
    "onboarding_step_api": "Bybit API key added",
    "onboarding_step_sum": "Trade amount set",
    "onboarding_step_ready": "Ready to trade",
    "onboarding_wait_confirm_hint": "💡 While waiting, you can add your API key in settings.",
    "onboarding_all_done_hint": "✅ Setup complete. Trades open automatically on service signals.",
    "feature_locked_wait_confirm": "⏳ Available after admin confirms your subscription (up to 24h).",
    "validation_sum_positive": "Trade amount must be greater than 0.",
    "validation_enter_number": "Enter a number, e.g. 25 or 25.5",
    "profile_settings_api_key": (
        "🔑 Step 1 of 2 — API key\n\n"
        "Enter your Bybit API key (Account → API Management).\n"
        "The bot is connected to: {account_mode}."
    ),
    "profile_settings_api_secret": (
        "🔐 Step 2 of 2 — API secret\n\n"
        "Enter the secret for key {api_key_preview}.\n\n"
        "The secret is shown only when the key is created. "
        "If you lost it — create a new key in Bybit and start from step 1."
    ),
    "profile_settings_api_saved_prompt_sum": "✅ API key saved. Now set your trade amount:",
    "profile_settings_api_invalid": (
        "❌ Bybit rejected the key + secret pair.\n\n"
        "Common reasons:\n"
        "• typo in key or secret;\n"
        "• key created for a different mode (you need {account_mode});\n"
        "• the key lacks Read permission for Unified / Futures.\n\n"
        "Let's start over — enter your API key again:"
    ),
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
    "trade_state_active": "active",
    "trade_state_closed": "closed",
    "trade_details_symbol": "📊 Symbol: {value}",
    "trade_details_state": "🏷️ Status: {value}",
    "trade_details_entry": "💰 Entry: {value}",
    "trade_details_entry_active": "💰 Entry price: {value}",
    "trade_details_exit": "💸 Exit: {value}",
    "trade_details_size": "📦 Size: {value}",
    "trade_details_pnl": "💵 PnL: {value}",
    "trade_details_open": "🕒 Open: {value}",
    "trade_details_close": "🕒 Close: {value}",
    "trade_details_created": "🗂️ Added: {value}",
    "trade_history_pnl": "PnL: {value}",
    "trading_menu": "📈 Trading\n\nTrades open automatically on service signals. Here you can view active positions and stop trading if needed.\n\nChoose an action:",
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
    "subscription_buy": "💳 Buy subscription",
    "tech_support": "💬 Support",
    "statistics": "📊 Statistics",
    "settings_profile": "⚙️ Settings",
    "setup_profile_early": "⚙️ Set up API in advance",
    "go_to_settings": "⚙️ Go to settings",
    "edit_api_key_secret": "🔑 Bybit API key",
    "api_key_instruction_enter": "🔑 Enter API key",
    "edit_sum_for_trades": "💵 Trade amount",
    "edit_sum_for_trades_locked": "💵 Amount (API key first)",
    "trading": "📈 Trading",
    "trading_portfolio": "💰 Balance",
    "history_trades": "📋 Trade history",
    "confirm_risk_sum_for_trades": "✅ Yes, set amount",
    "cancel_risk_sum_for_trades": "✏️ No, enter another",
    "active_trades": "🟢 Active trades",
    "stop_all_trading": "🛑 Stop all trading",
    "stop_current_trade": "🛑 Stop this trade",
  }, # -------------------------------------------------------------
  "admin_text": {
    "admin_menu": (
        "Admin panel 👨‍💻\n\n"
        "📋 Sections:\n"
        "• Users — payment confirmation and subscriber management\n"
        "• Statistics — project overview\n"
        "• Stop all trading — emergency stop for everyone\n"
        "• Server — algorithm API health check\n\n"
        "Choose an action:"
    ),
    "users_list": (
        "👥 Users\n\n"
        "• Pending confirmation — new payment requests\n"
        "• Subscribers — active clients with algorithm access\n\n"
        "Choose a section:"
    ),
    "statistics_project": "📊 Project statistics\n\nTotal users: {total_users}\nSubscribers: {total_subscribers}\nPending confirmation: {total_users_waiting_confirmation}",
    "server": "🖥 Server\n\nCheck algorithm API availability.",
    "check_health": "Server health check",
    "check_health_success": "✅ Server is up!\n\nStatus: {status}\nService: {service}",
    "check_health_error": "❌ Server unavailable\n\nResponse code: {status}",
    "stop_all_trading_success": "✅ All trading stopped\n\n{message}",
    "stop_all_trading_error": "❌ Failed to stop all trading\n\n{error}",
    "stop_all_trading_done": "Mass stop completed",
    "stop_all_trading_report": (
        "👥 Users checked: {processed}\n"
        "✅ Successfully stopped: {stopped}\n"
        "⏭️ Skipped (no API keys): {skipped}\n"
        "❌ Errors: {errors}"
    ),
    "wait_confirm": (
        "🕒 Pending confirmation\n\n"
        "• List — all requests with pagination\n"
        "• Search — by username or Telegram ID\n\n"
        "Choose a method:"
    ),
    "search_by_username_id": "🔍 Enter username or Telegram ID",
    "search_subscribers_by_username_id": "🔍 Enter subscriber username or Telegram ID",
    "user_not_search": "User not found 🚫",
    "user_not_wait_confirm": "This user is not waiting for confirmation 🚫",
    "user_not_subscriber": "User is not a subscriber 🚫",
    "user_not_confirmed_payment_bot": "ℹ️ User has not confirmed payment in the bot yet (did not tap «✅ Correct»).",
    "wait_confirm_list_title": "Waiting for subscription confirmation\n\nPage {page} of {pages} · total {total}",
    "wait_confirm_list_empty": "No one is waiting for confirmation.",
    "subscribers_list_title": "Subscribers\n\nPage {page} of {pages} · total {total}",
    "subscribers_list_empty": "No subscribers yet.",
    "user_info": "👤 User card\n\nName: {name}\nTG ID: {tg_id}\nLanguage: {language}\n\nSubscription: {subscription_status}\nCurrent price: {current_amount}\nType: {subscription_type}\nPayment date: {payment_date}\nEnd date: {end_subscription_date}",
    "subscribers": (
        "👥 Subscribers\n\n"
        "• List — all subscribers with pagination\n"
        "• Search — by username or Telegram ID\n\n"
        "Choose a method:"
    ),
    "subscription_settings": "⚙️ Subscription settings\n\nStatus: {subscription_status}\nCurrent price: {current_amount}\nTotal paid: {total_amount}\nType: {subscription_type}\nPayment date: {payment_date}\nEnd date: {end_subscription_date}",
    "edit_date_end_subs": "Enter date as yyyy.mm.dd. hh.mm.ss",
    "edit_date_end_subs_invalid_format": "Invalid date format. Use: yyyy.mm.dd. hh.mm.ss",
    "edit_date_end_subs_success": "Subscription end date updated: {end_subscription_date}",
    "bybit_settings": "⚙️ Bybit settings\n\nAPI key: {api_key}\nAPI secret: {api_secret}\nTrade amount: {sum_for_trades}\nTrading stopped: {stop_trading}",
    "edit_api_key": "Enter the new API key",
    "edit_api_secret": "Enter the new API secret",
    "edit_sum_for_trades": "Enter the new trade amount",
    "edit_api_key_success": "API key updated.",
    "edit_api_secret_success": "API secret updated.",
    "edit_sum_for_trades_success": "Trade amount updated: {sum_for_trades}",
    "statistics_info": "📊 Subscriber statistics\n\nTotal trades: {total_trades}\nTotal PnL: {total_pnl}\nWinning: {positive_trades} (+{sum_positive_trades})\nLosing: {negative_trades} (-{sum_negative_trades})",
    "subscription_status_active": "Active",
    "subscription_status_inactive": "Inactive",
    "stop_trading_yes": "Yes",
    "stop_trading_no": "No",
    "access_denied": "Access denied",
    "action_failed": "Action failed: {error}",
    "error_search_user": "Find a user first. 🚫",
    "error_user_not_found": "User not found in the database. 🚫",
    "subscribers_main_info": "👤 Subscriber card\n\nName: {name}\nTG ID: {tg_id}\nLanguage: {language}\nTrade amount limit: {trade_amount_limit_status}",
    "trade_amount_limit_unlimited": "disabled (extended mode)",
    "trade_amount_limit_standard": "standard (per service rules)",
    "toggle_unlimited_trade_added": "User can set trade amount above the limit",
    "toggle_unlimited_trade_removed": "Standard trade amount limit restored for user",
  }, # -------------------------------------------------------------
  "admin_btn": {
    "users_list": "Users 👥",
    "statistics_project": "Statistics 📊",
    "server": "Server 🖥",
    "wait_confirm": "Pending confirmation",
    "subscribers": "Subscribers",
    "wait_confirm_list": "User list",
    "subscribers_list": "Subscribers list",
    "search_by_username_id": "Search by username & ID",
    "check_health": "Server health check",
    "edit_stop_trades": "Stop/Resume trading",
    "stop_all_trading": "🛑 Stop all trading",
    "edit_api_key": "Change API key",
    "edit_api_secret": "Change API secret",
    "edit_sum_for_trades": "Change trade amount",
    "edit_stop_trading_stop_mode": "Stop trading",
    "edit_stop_trading_resume_mode": "Resume trading",
    "list_prev_page": "◀️ Prev",
    "list_next_page": "Next ▶️",
    "back_to_user_list": "Back to list",
    "proccess_search_wair_confirm": "🔍 Search again",
    "back_to_wait_confirm_menu": "⬅️ Back to pending",
    "back_to_subscribers_menu": "⬅️ Back to subscribers",
    "search_subscribers_again": "🔍 Search again",
    "back_to_subscriber_card": "⬅️ Back to user card",
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
    "main_menu": "🏠 Main menu",
    "change_language": "🌐 Change language",
    "admin_to_main_menu": "🏠 Exit to main menu",
    "admin_panel": "👨‍💻 Admin panel",
    "help_title": "❓ Bot help",
    "help_setup": (
        "📋 Steps:\n"
        "1. Buy subscription\n"
        "2. Wait for confirmation (up to 24h)\n"
        "3. Add Bybit API key in settings\n"
        "4. Set trade amount\n\n"
        "Trades open automatically on service signals — no manual launch needed."
    ),
    "help_commands": (
        "Commands:\n"
        "/start or /main_menu — main menu\n"
        "/profile — your profile\n"
        "/help — this guide"
    ),
  }
}