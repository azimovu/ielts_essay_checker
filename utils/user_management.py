from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from models.user import User
import database
from handlers.evaluate import handle_essay  # Import the handle_essay function
from handlers.feedback import handle_feedback, process_feedback  # Import both feedback functions


def get_user(user_id: int) -> User:
    """Get a user from the database."""
    user_data = database.get_user(user_id)
    if user_data:
        return User(id=user_data[0], 
                    phone_number=user_data[1], 
                    usage_count=user_data[2], 
                    free_uses_left=user_data[3], 
                    purchased_uses=user_data[4])
    return None

def add_user(user_id: int) -> None:
    """Add a new user to the database."""
    database.add_user(user_id)

def update_phone_number(user_id: int, phone_number: str) -> None:
    """Update a user's phone number in the database."""
    database.update_phone_number(user_id, phone_number)

async def request_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Request the user's phone number."""
    keyboard = [[KeyboardButton("Share Contact", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Welcome! I need your phone number to proceed. Please share your contact.", reply_markup=reply_markup)
    context.user_data['state'] = 'waiting_for_phone_number'

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the shared contact information."""
    user_id = update.effective_user.id
    phone_number = update.message.contact.phone_number
    update_phone_number(user_id, phone_number)
    await show_main_menu(update, context)
    context.user_data['state'] = None

async def check_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user has any uses left (free or purchased)."""
    user_id = update.effective_user.id
    free_uses_left = database.get_free_uses_left(user_id)
    purchased_uses = database.get_purchased_uses(user_id)
    
    if free_uses_left > 0:
        database.decrement_free_uses(user_id)
        return True
    elif purchased_uses > 0:
        database.decrement_purchased_uses(user_id)
        return True
    else:
        await update.message.reply_text("You've used all your free and purchased attempts. To continue using the service, please purchase more uses.")
        await show_purchase_options(update, context)
        return False

async def show_purchase_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show options to purchase more uses."""
    keyboard = [["Purchase 5 uses", "Purchase 10 uses"], ["Back to Main Menu"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Select a purchase option:', reply_markup=reply_markup)

async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the purchase of more uses."""
    user_id = update.effective_user.id
    purchase_amount = 5 if update.message.text == "Purchase 5 uses" else 10
    
    # Simulate a successful purchase
    database.add_purchased_uses(user_id, purchase_amount)
    
    await update.message.reply_text(f"Purchase successful! You've added {purchase_amount} more uses to your account.")
    await show_main_menu(update, context)

async def handle_check_remaining_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the request to check remaining uses."""
    user_id = update.effective_user.id
    free_uses_left = database.get_free_uses_left(user_id)
    purchased_uses = database.get_purchased_uses(user_id)
    
    message = f"You have {free_uses_left} free uses left.\n"
    if purchased_uses > 0:
        message += f"You also have {purchased_uses} purchased uses available."
    else:
        message += "You haven't purchased any additional uses yet."
    
    await update.message.reply_text(message)
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu."""
    keyboard = [["Evaluate", "Feedback"], ["Check Remaining Uses"], ["Purchase More Uses"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Please choose an option:', reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages based on the current state."""
    if update.message.text == "Evaluate":
        if await check_uses(update, context):
            await update.message.reply_text('Please provide the topic for evaluation.')
            context.user_data['state'] = 'waiting_for_topic'
    elif update.message.text == "Feedback":
        await handle_feedback(update, context)  # This will set the state to 'waiting_for_feedback'
    elif update.message.text == "Check Remaining Uses":
        await handle_check_remaining_uses(update, context)
    elif update.message.text == "Purchase More Uses":
        await show_purchase_options(update, context)
    elif update.message.text in ["Purchase 5 uses", "Purchase 10 uses"]:
        await handle_purchase(update, context)
    elif update.message.text == "Back to Main Menu":
        await show_main_menu(update, context)
    elif context.user_data.get('state') == 'waiting_for_topic':
        context.user_data['topic'] = update.message.text
        await update.message.reply_text('Now, please send me the essay.')
        context.user_data['state'] = 'waiting_for_essay'
    elif context.user_data.get('state') == 'waiting_for_essay':
        await handle_essay(update, context)
        context.user_data['state'] = None
        await show_main_menu(update, context)
    elif context.user_data.get('state') == 'waiting_for_feedback':
        await process_feedback(update, context)  # Process the feedback
        await show_main_menu(update, context)
    else:
        await update.message.reply_text("I'm sorry, I didn't understand that command. Please use the menu options.")
        await show_main_menu(update, context)