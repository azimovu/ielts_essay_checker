import logging
import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.ext import Updater
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT
from handlers import start, evaluate, feedback
from utils import user_management
from database import migrate_database
from handlers.start import handle_contact_shared
from flask import Flask, request

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

def main() -> None:
    """Start the bot using webhooks."""
    # Run database migration
    migrate_database()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start.handle_start))
    application.add_handler(CommandHandler("evaluate", evaluate.handle_evaluate))
    application.add_handler(CommandHandler("feedback", feedback.handle_feedback))
    application.add_handler(CommandHandler("check_uses", user_management.handle_check_remaining_uses))
    application.add_handler(CommandHandler("purchase", user_management.show_purchase_options))
    application.add_handler(CommandHandler("verify_payment", user_management.verify_payment))


    application.add_handler(MessageHandler(filters.Regex('^Evaluate$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.Regex('^Feedback$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.Regex('^Check Remaining Uses$'), user_management.handle_check_remaining_uses))
    application.add_handler(MessageHandler(filters.Regex('^Purchase More Uses$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.CONTACT, user_management.handle_contact))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact_shared))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_management.handle_message))
    application.add_handler(CallbackQueryHandler(user_management.handle_purchase_callback))

    # Set up webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    )

    return application

# Create the Application and pass it to the handler
application = main()

@app.route("/", methods=["GET", "POST"])
def webhook():
    """Handle incoming Telegram updates."""
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), application.bot)
        application.process_update(update)
    return "OK"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))