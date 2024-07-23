from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import user_management

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user = update.effective_user
    user_management.add_user(user.id)
    
    if user_management.get_user(user.id).phone_number:
        # User already has a phone number, show main menu
        await user_management.show_main_menu(update, context)
    else:
        # User needs to share phone number
        keyboard = [
            [KeyboardButton("📱 Share Contact", request_contact=True)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "Welcome to EssayBot! 🎓✍️\n\n"
            "To provide you with our essay evaluation service and important updates, "
            "we need your contact information.",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text(
            "📞 *Phone Number Required*\n\n"
            "To use EssayBot, please share your contact information by clicking the button below. "
            "This is a one-time process and is necessary to access our services.\n\n"
            "Thank you for your cooperation!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_contact_shared(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when user shares their contact."""
    contact = update.effective_message.contact
    user_id = update.effective_user.id
    
    if contact and contact.user_id == user_id:
        user_management.update_phone_number(user_id, contact.phone_number)
        await update.message.reply_text(
            "Thank you for sharing your contact information! You're all set to use EssayBot."
        )
        await user_management.show_main_menu(update, context)
    else:
        await update.message.reply_text(
            "I'm sorry, but I can only accept your own contact information. Please use the 'Share Contact' button to share your phone number."
        )

# Don't forget to add a handler for contact messages in your main file
# application.add_handler(MessageHandler(filters.CONTACT, handle_contact_shared))