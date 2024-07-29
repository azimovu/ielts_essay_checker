import database
from telegram import Update
from telegram.ext import ContextTypes

async def check_and_decrement_uses(user_id: int) -> bool:
    """Check if the user has any uses left, decrement if true, and increment usage count."""
    free_uses_left = database.get_free_uses_left(user_id)
    purchased_uses = database.get_purchased_uses(user_id)
    
    if free_uses_left > 0:
        database.decrement_free_uses(user_id)
        database.increment_usage_count(user_id)
        return True
    elif purchased_uses > 0:
        database.decrement_purchased_uses(user_id)
        database.increment_usage_count(user_id)
        return True
    return False

async def handle_insufficient_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("You've used all your free and purchased attempts. To continue using the service, please purchase more uses.")
   