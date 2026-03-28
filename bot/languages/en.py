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
    "buy_info": f"Payment for 1 month = 99$\nWallet URL - {URL_PAYMENT}\nPayment type: TRC-20\nP.S. Payments are accepted only from exchange accounts.\nAfter payment, click the 'Paid' button and enter the payment ID.",
    "question": "After payment, click the 'Paid' button and enter the payment ID. Then the administration will verify your payment within 24 hours and activate your subscription.",
    "paid": "Great! Now you only need to enter the payment ID. Click the 'Enter payment ID' button and provide the payment ID.\nThen the administration will verify your payment within 24 hours and activate your subscription.",
    "input_payment_id": "Enter the payment ID in chat",
    "confirm_payment": "Is everything correct: {payment_id}",
    "confirm_payment_success": "Thanks for your payment! The administration will verify your payment within 24 hours and activate your subscription.",
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
  },
  "profile_btn": {
    "subscription_buy": "Buy subscription",
    "tech_support": "Tech support",
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