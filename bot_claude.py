import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, PreCheckoutQueryHandler, ContextTypes
from web_server import app
from config import TELEGRAM_BOT_TOKEN
from handlers import start, evaluate, feedback
from utils import user_management, paycom_integration
from database import migrate_database
from utils.paycom_integration import create_transaction
from config import PAYCOM_MERCHANT_ID
from handlers.start import handle_contact_shared
from database import get_user
import asyncio
from threading import Thread
import sys

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_flask():
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)

async def error_handler(update, context):
    """Log Errors caused by Updates."""
    logger.error(f'Update "{update}" caused error "{context.error}"', exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text("An error occurred. Please try again later.")

async def pre_checkout_update(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the pre-checkout update event."""
    try:
        query = update.pre_checkout_query
        await query.answer(ok=True)
    except Exception as e:
        logger.error(f"Error in pre_checkout_update: {e}", exc_info=True)
        raise

async def start_bot():
    """Start the bot in async context."""
    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add error handler
        application.add_error_handler(error_handler)

        # Add command handlers
        application.add_handler(CommandHandler("start", start.handle_start))
        application.add_handler(CommandHandler("evaluate", evaluate.handle_evaluate))
        application.add_handler(CommandHandler("feedback", feedback.handle_feedback))
        application.add_handler(CommandHandler("check_uses", user_management.handle_check_remaining_uses))
        application.add_handler(CommandHandler("purchase", user_management.show_purchase_options))
        application.add_handler(CommandHandler("verify_payment", user_management.verify_payment))
      # application.add_handler(CommandHandler("balance", handle_balance))

        # Add message handlers
        application.add_handler(MessageHandler(filters.Regex('^Evaluate$'), user_management.handle_message))
        application.add_handler(MessageHandler(filters.Regex('^Feedback$'), user_management.handle_message))
        application.add_handler(MessageHandler(filters.Regex('^Check Remaining Uses$'), user_management.handle_check_remaining_uses))
        application.add_handler(MessageHandler(filters.Regex('^Purchase More Uses$'), user_management.show_purchase_options))
        application.add_handler(MessageHandler(filters.Regex('^Verify Payment$'), user_management.verify_payment))
        application.add_handler(MessageHandler(filters.CONTACT, user_management.handle_contact))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact_shared))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_management.handle_message))

        # Add callback handlers
        application.add_handler(CallbackQueryHandler(user_management.handle_purchase_callback, pattern='^purchase_'))
        application.add_handler(CallbackQueryHandler(invoice_callback, pattern='^invoice_'))
        application.add_handler(PreCheckoutQueryHandler(pre_checkout_update))

        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise

def main():
    """Start the bot and Flask server."""
    try:
        # Run database migration
        migrate_database()
        
        # Start Flask in a separate thread
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Run the bot in the main thread
        asyncio.run(start_bot())

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()