import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import TELEGRAM_BOT_TOKEN
from handlers import start, evaluate, feedback
from utils import user_management
from database import migrate_database
from handlers.start import handle_contact_shared

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    """Start the bot."""
    # Run database migration
    migrate_database()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start.handle_start))
    application.add_handler(MessageHandler(filters.Regex('^Evaluate$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.Regex('^Feedback$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.Regex('^Check Remaining Uses$'), user_management.handle_check_remaining_uses))
    application.add_handler(MessageHandler(filters.Regex('^Purchase More Uses$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.CONTACT, user_management.handle_contact))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact_shared))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_management.handle_message))
    application.add_handler(CallbackQueryHandler(user_management.handle_purchase_callback))
    
    application.run_polling()

if __name__ == '__main__':
    main()