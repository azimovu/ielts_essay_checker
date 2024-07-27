import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.ext.filters import Regex
from config import TELEGRAM_BOT_TOKEN
from handlers import start, evaluate, feedback
from utils import user_management
from database import migrate_database

def main():
    """Handle Telegram webhook."""
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

    application.add_handler(MessageHandler(Regex('^Evaluate$'), user_management.handle_message))
    application.add_handler(MessageHandler(Regex('^Feedback$'), user_management.handle_message))
    application.add_handler(MessageHandler(Regex('^Check Remaining Uses$'), user_management.handle_check_remaining_uses))
    application.add_handler(MessageHandler(Regex('^Purchase More Uses$'), user_management.handle_message))
    application.add_handler(MessageHandler(Regex('^Verify Payment$'), user_management.verify_payment))
    application.add_handler(MessageHandler(filters.CONTACT, user_management.handle_contact))
    application.add_handler(MessageHandler(filters.CONTACT, start.handle_contact_shared))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_management.handle_message))
    application.add_handler(CallbackQueryHandler(user_management.handle_purchase_callback))

    # Process the update
    update_json = os.environ.get('TELEGRAM_UPDATE')
    if update_json:
        update = Update.de_json(json.loads(update_json), application.bot)
        application.process_update(update)
        print("OK")
    else:
        print("No update received")

if __name__ == '__main__':
    main()