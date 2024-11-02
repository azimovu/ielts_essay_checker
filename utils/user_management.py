from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models.user import User
import database
from handlers.evaluate import handle_evaluate, handle_essay
from handlers.feedback import handle_feedback, process_feedback
from utils.click_integration import ClickIntegration
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional
import datetime

click = ClickIntegration()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('bot.log', maxBytes=100000, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

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

async def check_invoice_status(invoice_id: str) -> Dict[str, Any]:
    """
    Check the status of a Click invoice
    """
    try:
        status_data = await click.check_invoice(invoice_id)
        return {
            'error_code': status_data.get('error_code', -1),
            'error_note': status_data.get('error_note', 'Unknown error'),
            'invoice_status': status_data.get('invoice_status'),
            'payment_id': status_data.get('payment_id')
        }
    except Exception as e:
        logger.error(f"Error checking invoice status: {str(e)}")
        return {
            'error_code': -1,
            'error_note': f"Error checking invoice: {str(e)}",
            'invoice_status': None,
            'payment_id': None
        }

async def check_payment_status(payment_id: str) -> Dict[str, Any]:
    """
    Check the status of a Click payment
    """
    try:
        status_data = await click.check_payment_status(payment_id)
        return {
            'error_code': status_data.get('error_code', -1),
            'error_note': status_data.get('error_note', 'Unknown error'),
            'payment_status': status_data.get('payment_status')
        }
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return {
            'error_code': -1,
            'error_note': f"Error checking payment: {str(e)}",
            'payment_status': None
        }

# Also add this helper function for better error handling
async def handle_payment_error(update: Update, error: Exception) -> None:
    """
    Handle payment-related errors and send appropriate messages to user
    """
    error_msg = str(error)
    logger.error(f"Payment error: {error_msg}")
    
    if "network" in error_msg.lower():
        await send_message(
            update,
            "Sorry, there seems to be a network issue. Please try again in a few minutes."
        )
    elif "timeout" in error_msg.lower():
        await send_message(
            update,
            "The request timed out. Please try again."
        )
    else:
        await send_message(
            update,
            "Sorry, there was an error processing your payment. Please try again later."
        )



async def handle_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int = None) -> None:
    """Handle the purchase process using Click with improved error handling."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user or not user.phone_number:
        await request_phone_number(update, context)
        return
    
    if amount is None:
        try:
            amount = int(update.message.text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await send_message(update, "Please enter a valid positive number.")
            return
    
    price_uzs = calculate_price(amount)
    
    try:
        # Log the initiation of payment process
        logger.info(f"Creating Click invoice for user {user_id}, amount: {price_uzs} UZS")
        
        # Create Click invoice with error handling
        invoice_id, invoice_data = await click.create_invoice(
            amount=price_uzs,
            user_id=user_id,
            phone_number=user.phone_number
        )
        
        # Log the response from Click
        logger.info(f"Click invoice response: {invoice_data}")
        
        if not invoice_data:
            raise Exception("No response received from Click API")
            
        if invoice_data.get('error_code') == 0:
            # Store more detailed payment information
            context.user_data['pending_order'] = {
                'invoice_id': invoice_id,
                'amount': amount,
                'merchant_trans_id': invoice_data.get('merchant_trans_id'),
                'service_id': invoice_data.get('service_id'),
                'merchant_id': invoice_data.get('merchant_id'),
                'created_time': datetime.now().isoformat(),
                'price_uzs': price_uzs
            }
            
            # Create payment buttons with better UX
            keyboard = [
                [InlineKeyboardButton(
                    "Pay with Click", 
                    url=f"https://my.click.uz/services/pay?service_id={invoice_data['service_id']}&merchant_id={invoice_data['merchant_id']}&amount={price_uzs}&transaction_param={invoice_data['merchant_trans_id']}")
                ],
                [InlineKeyboardButton("Check Payment Status", callback_data=f"check_payment_{invoice_id}")],
                [InlineKeyboardButton("Cancel Payment", callback_data=f"cancel_payment_{invoice_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await send_message(
                update,
                f"🛒 Purchase Details:\n"
                f"• Quantity: {amount} uses\n"
                f"• Price: {price_uzs:,} UZS\n\n"
                f"1️⃣ Click the 'Pay with Click' button to proceed\n"
                f"2️⃣ Complete the payment in Click\n"
                f"3️⃣ Return here and click 'Check Payment Status'\n\n"
                f"ℹ️ Payment will be checked automatically every 30 seconds.",
                reply_markup=reply_markup
            )
            
            # Start periodic payment check with improved error handling
            asyncio.create_task(periodic_payment_check(update, context))
            
        else:
            error_note = invoice_data.get('error_note', 'Unknown error')
            logger.error(f"Click API error: {error_note}")
            await send_message(
                update,
                f"⚠️ Error creating payment: {error_note}\n"
                "Please try again or contact support if the issue persists."
            )
    
    except Exception as e:
        logger.error(f"Error in handle_purchase: {str(e)}", exc_info=True)
        await send_message(
            update,
            "⚠️ Sorry, we encountered an error while processing your request.\n"
            "This might be due to:\n"
            "• Temporary Click service disruption\n"
            "• Network connectivity issues\n"
            "• Invalid payment parameters\n\n"
            "Please try again in a few minutes or contact support if the issue persists."
        )

async def periodic_payment_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Periodically check payment status."""
    check_interval = 30  # Check every 30 seconds
    max_checks = 20  # Maximum number of checks (10 minutes total)
    
    for _ in range(max_checks):
        await asyncio.sleep(check_interval)
        
        if 'pending_order' not in context.user_data:
            return
        
        pending_order = context.user_data['pending_order']
        try:
            # Check invoice status
            invoice_status = await check_invoice_status(pending_order['invoice_id'])
            
            if invoice_status['error_code'] == 0:
                if invoice_status['invoice_status'] == 2:  # Paid
                    # Verify payment status
                    payment_status = await check_payment_status(invoice_status['payment_id'])
                    
                    if payment_status['error_code'] == 0 and payment_status['payment_status'] == 2:
                        user_id = update.effective_user.id
                        database.add_purchased_uses(user_id, pending_order['amount'])
                        await send_message(
                            update, 
                            f"Payment successful! You've added {pending_order['amount']} more uses to your account."
                        )
                        del context.user_data['pending_order']
                        return
                elif invoice_status['invoice_status'] < 0:  # Failed/Cancelled
                    await send_message(update, "Payment was cancelled or failed. Please try again.")
                    del context.user_data['pending_order']
                    return
        except Exception as e:
            await handle_payment_error(update, e)
    
    # If we reach here, payment verification period has expired
    await send_message(
        update,
        "Payment verification period has expired. If you've made the payment, "
        "use the 'Check Payment Status' button to verify manually."
    )

# Update verify_payment to use the new functions
async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually verify payment status."""
    if 'pending_order' not in context.user_data:
        await send_message(update, "No pending order found. Please start a new purchase.")
        return
    
    pending_order = context.user_data['pending_order']
    try:
        invoice_status = await check_invoice_status(pending_order['invoice_id'])
        
        if invoice_status['error_code'] == 0:
            if invoice_status['invoice_status'] == 2:  # Paid
                payment_status = await check_payment_status(invoice_status['payment_id'])
                
                if payment_status['error_code'] == 0 and payment_status['payment_status'] == 2:
                    user_id = update.effective_user.id
                    database.add_purchased_uses(user_id, pending_order['amount'])
                    await send_message(
                        update,
                        f"Payment verified! You've added {pending_order['amount']} more uses to your account."
                    )
                    del context.user_data['pending_order']
                else:
                    await send_message(update, "Payment verification failed. Please try again later.")
            elif invoice_status['invoice_status'] < 0:
                await send_message(update, "Payment was cancelled or failed. Please try again.")
                del context.user_data['pending_order']
            else:
                await send_message(update, "Payment is still pending. Please try again later.")
        else:
            await send_message(
                update,
                f"Error checking payment status: {invoice_status['error_note']}"
            )
    
    except Exception as e:
        await handle_payment_error(update, e)

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages based on the current state."""
    if update.message.text == "Evaluate":
        await handle_evaluate(update, context)
    elif update.message.text == "Feedback":
        await handle_feedback(update, context)
    elif update.message.text == "Check Remaining Uses":
        await handle_check_remaining_uses(update, context)
    elif update.message.text == "Purchase More Uses":
        await show_purchase_options(update, context)
    elif update.message.text == "Verify Payment":
        await verify_payment(update, context)
    elif update.message.text == "Back to Main Menu":
        await show_main_menu(update, context)
    elif context.user_data.get('state') == 'waiting_for_custom_amount':
        await handle_purchase(update, context)
    elif context.user_data.get('state') == 'waiting_for_topic':
        context.user_data['topic'] = update.message.text
        await update.message.reply_text('Now, please send me the essay.')
        context.user_data['state'] = 'waiting_for_essay'
    elif context.user_data.get('state') == 'waiting_for_essay':
        await handle_essay(update, context)
    elif context.user_data.get('state') == 'waiting_for_feedback':
        await process_feedback(update, context)
    else:
        await update.message.reply_text("I'm sorry, I didn't understand that command. Please use the menu options.")
        await show_main_menu(update, context)

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