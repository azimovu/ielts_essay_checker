from telegram import Update
from telegram.ext import ContextTypes
from utils import user_management

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user_id = update.effective_user.id
    user = user_management.get_user(user_id)

    if user is None:
        user_management.add_user(user_id)
        await user_management.request_phone_number(update, context)
    elif user.phone_number is None or user.phone_number == "":
        await user_management.request_phone_number(update, context)
    else:
        await user_management.show_main_menu(update, context)