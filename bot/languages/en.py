from config import URL_PAYMENT

EN_CONFIGURATION = {
  "start_text": {
    "greeting": "Hello! I'm ZdormanBot 👋\nI'll tell you how to get a subscription to our service 📈 and why you can trust us 😎",
  },
  "start_btn": {
    "url_tg": "Our Telegram",
    "personal_account": "Personal account",
    "subscription_buy": "Buy subscription",
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
  }, # -------------------------------------------------------------
  "admin_btn": {
    "users_list": "Users",
    "statistics": "Statistics",
  }, # -------------------------------------------------------------
  "general": {
    "back": "⬅️ Back",
    "admin_to_main_menu": "Main menu",
  }
}