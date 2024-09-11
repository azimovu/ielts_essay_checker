from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models.user import User
import database
from handlers.evaluate import handle_evaluate, handle_essay
from handlers.feedback import handle_feedback, process_feedback
from utils.paycom_integration import create_transaction, check_transaction
from config import PAYCOM_MERCHANT_ID
import asyncio
import uuid


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages based on the current state."""
    if update.message.text == "Evaluate":
        context.user_data['state'] = 'waiting_for_topic'
        await handle_evaluate(update, context)
    elif update.message.text == "Feedback":
        context.user_data['state'] = 'waiting_for_feedback'
        await handle_feedback(update, context)
    elif update.message.text == "Check Remaining Uses":
        await handle_check_remaining_uses(update, context)
    elif update.message.text == "Purchase More Uses":
        await show_purchase_options(update, context)
    elif update.message.text == "Verify Payment":
        await verify_payment(update, context)
    elif update.message.text == "Back to Main Menu":
        context.user_data['state'] = None
        await show_main_menu(update, context)
    elif context.user_data.get('state') == 'waiting_for_topic':
        context.user_data['topic'] = update.message.text
        await update.message.reply_text('Now, please send me the essay.')
        context.user_data['state'] = 'waiting_for_essay'
    elif context.user_data.get('state') == 'waiting_for_essay':
        await handle_essay(update, context)
        context.user_data['state'] = None  # Reset state after handling essay
    elif context.user_data.get('state') == 'waiting_for_feedback':
        await process_feedback(update, context)
        context.user_data['state'] = None  # Reset state after processing feedback
    elif context.user_data.get('state') == 'waiting_for_custom_amount':
        await handle_purchase(update, context)
    else:
        await update.message.reply_text("I'm sorry, I didn't understand that command. Please use the menu options.")
        context.user_data['state'] = None  # Reset state if command not recognized
        await show_main_menu(update, context)

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
    """Check if the user has any uses left (free or purchased) and increment usage count."""
    user_id = update.effective_user.id
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
    else:
        await update.message.reply_text("You've used all your free and purchased attempts. To continue using the service, please purchase more uses.")
        await show_purchase_options(update, context)
        return False



def calculate_price(uses: int) -> int:
    """Calculate the price based on the number of uses."""
    if uses == 5:
        return 5000
    elif uses == 10:
        return 10000
    elif uses == 20:
        return 16000
    else:
        return uses * 1000

async def show_purchase_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show options to purchase more uses with an inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("5 uses - 5,000 UZS", callback_data="purchase_5"),
            InlineKeyboardButton("10 uses - 10,000 UZS", callback_data="purchase_10")
        ],
        [
            InlineKeyboardButton("20 uses - 16,000 UZS", callback_data="purchase_20"),
            InlineKeyboardButton("Custom amount", callback_data="purchase_custom")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Select a purchase option or choose a custom amount:', reply_markup=reply_markup)
    context.user_data['state'] = 'waiting_for_purchase_selection'


async def handle_purchase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the callback from the inline keyboard."""
    query = update.callback_query
    await query.answer()

    if query.data == "purchase_custom":
        await query.edit_message_text("Please enter the number of uses you'd like to purchase:")
        context.user_data['state'] = 'waiting_for_custom_amount'
    else:
        amount = int(query.data.split('_')[1])
        await handle_purchase(update, context, amount)

async def periodic_payment_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    check_interval = 60  # Check every 60 seconds
    max_checks = 10  # Maximum number of checks (10 minutes total)
    
    for _ in range(max_checks):
        await asyncio.sleep(check_interval)
        
        if 'pending_order' not in context.user_data:
            return  # No pending order, stop checking
        
        pending_order = context.user_data['pending_order']
        transaction_status = await check_transaction(pending_order['transaction_id'])
        
        if transaction_status.get('result'):
            if transaction_status['result']['state'] == 2:  # 2 means paid
                user_id = update.effective_user.id
                database.add_purchased_uses(user_id, pending_order['amount'])
                await send_message(update, f"Payment successful! You've added {pending_order['amount']} more uses to your account.")
                del context.user_data['pending_order']
                return  # Payment successful, stop checking
    
    
    # If we've reached this point, the payment wasn't completed within the maximum check time
    await send_message(update, "The payment verification period has expired. If you've made the payment, please use the /verify_payment command to manually check the status.")



async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int = None) -> None:
    if amount is None:
        if context.user_data.get('state') != 'waiting_for_custom_amount':
            await update.message.reply_text("Please select a purchase option first.")
            return
        try:
            amount = int(update.message.text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Please enter a valid positive number.")
            return

    user_id = update.effective_user.id
    user = get_user(user_id)
    
    price_uzs = calculate_price(amount)
    
    # Create a unique order ID
    order_id = str(uuid.uuid4())
    
    # Create a transaction using Payme API
    transaction_data = await create_transaction(price_uzs, order_id)
    
    if transaction_data.get('result'):
        transaction_id = transaction_data['result']['transaction']
        payment_url = f"https://checkout.paycom.uz/{PAYCOM_MERCHANT_ID}/{transaction_id}"
        
        context.user_data['pending_order'] = {
            'transaction_id': transaction_id,
            'amount': amount,
            'order_id': order_id
        }
        
        keyboard = [[InlineKeyboardButton("Pay Now", url=payment_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"Great! You're purchasing {amount} uses for {price_uzs} UZS. "
                f"Click the button below to proceed with the payment:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"Great! You're purchasing {amount} uses for {price_uzs} UZS. "
                f"Click the button below to proceed with the payment:",
                reply_markup=reply_markup
            )
        
        # Start periodic payment check
        asyncio.create_task(periodic_payment_check(update, context))
    else:
        error_message = "Sorry, there was an error creating the transaction. Please try again later."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)

    context.user_data['state'] = None  # Reset state after handling purchase

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'pending_order' not in context.user_data:
        await send_message(update, "No pending order found. Please start a new purchase.")
        return
    
    pending_order = context.user_data['pending_order']
    transaction_status = await check_transaction(pending_order['transaction_id'])
    
    if transaction_status.get('result'):
        if transaction_status['result']['state'] == 2:  # 2 means paid
            user_id = update.effective_user.id
            database.add_purchased_uses(user_id, pending_order['amount'])
            await send_message(update, f"Payment successful! You've added {pending_order['amount']} more uses to your account.")
            del context.user_data['pending_order']
        else:
            await send_message(update, "Payment not yet completed. Please try again later or start a new purchase.")
    else:
        await send_message(update, "Payment verification failed. Please contact support if you believe this is an error.")



async def send_message(update: Update, text: str, reply_markup=None):
    """Send a message in both callback query and normal message contexts."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)



async def handle_check_remaining_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the request to check remaining uses and total usage count."""
    user_id = update.effective_user.id
    free_uses_left = database.get_free_uses_left(user_id)
    purchased_uses = database.get_purchased_uses(user_id)
    usage_count = database.get_usage_count(user_id)
    
    message = f"You have used the service {usage_count} times in total.\n"
    message += f"You have {free_uses_left} free uses left.\n"
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