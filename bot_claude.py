import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, PreCheckoutQueryHandler, Updater, ContextTypes
from web_server import app
from config import TELEGRAM_BOT_TOKEN
from handlers import start, evaluate, feedback
from utils import user_management, paycom_integration
from database import migrate_database
from utils.paycom_integration import create_transaction
from config import PAYCOM_MERCHANT_ID
from handlers.start import handle_contact_shared
from user import add_balance, deduct_balance, get_user, add_referral
import threading
import asyncio

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

async def pre_checkout_update(update: Updater, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the pre-checkout update event."""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def invoice_callback(update: Updater, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the invoice callback event."""
    # Get the necessary information from the callback data
    callback_data = update.callback_query.data
    invoice_id = callback_data.split('_')[-1]
    
    try:
        # Retrieve the invoice details from the database or any other storage
        invoice = user_management.get_invoice(invoice_id)
        if not invoice:
            await update.callback_query.answer(text="Invoice not found. Please try again.", show_alert=True)
            return

        # Create the invoice using the Payme API
        transaction_data = await create_transaction(invoice['amount'], invoice['order_id'])
        print(f"Transaction Data: {transaction_data}")  # Debugging log

        if transaction_data.get('result'):
            transaction_id = transaction_data['result']['transaction']
            payment_url = f"https://checkout.paycom.uz/{PAYCOM_MERCHANT_ID}/{transaction_id}"

            # Send the invoice to the user with the payment URL
            await update.callback_query.answer(url=payment_url)
        else:
            error_message = f"Failed to create the invoice: {transaction_data.get('error', 'Unknown error')}"
            print(error_message)  # Error log
            await update.callback_query.answer(text=error_message, show_alert=True)
    except Exception as e:
        error_message = f"Exception during invoice creation: {e}"
        print(error_message)  # Exception log
        await update.callback_query.answer(text=error_message, show_alert=True)

def main() -> None:
    """Start the bot."""
    # Run database migration
    migrate_database()
    
    # Run Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start.handle_start))
    application.add_handler(CommandHandler("evaluate", evaluate.handle_evaluate))
    application.add_handler(CommandHandler("feedback", feedback.handle_feedback))
    application.add_handler(CommandHandler("check_uses", user_management.handle_check_remaining_uses))
    application.add_handler(CommandHandler("purchase", user_management.show_purchase_options))
    application.add_handler(CommandHandler("verify_payment", user_management.verify_payment))
    application.add_handler(CommandHandler("balance", handle_balance))

    application.add_handler(MessageHandler(filters.Regex('^Evaluate$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.Regex('^Feedback$'), user_management.handle_message))
    application.add_handler(MessageHandler(filters.Regex('^Check Remaining Uses$'), user_management.handle_check_remaining_uses))
    application.add_handler(MessageHandler(filters.Regex('^Purchase More Uses$'), user_management.show_purchase_options))
    application.add_handler(MessageHandler(filters.Regex('^Verify Payment$'), user_management.verify_payment))
    application.add_handler(MessageHandler(filters.CONTACT, user_management.handle_contact))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact_shared))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_management.handle_message))

    # Add the callback query handler for the "Pay Now" button click event
    application.add_handler(CallbackQueryHandler(user_management.handle_purchase_callback, pattern='^purchase_'))
    application.add_handler(CallbackQueryHandler(invoice_callback, pattern='^invoice_'))

    # Add the pre-checkout query handler
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_update))

    application.run_polling()

async def handle_balance(update: Updater, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /balance command."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user:
        balance = user[5]  # Assuming balance is at index 5 in the user tuple
        await update.message.reply_text(f"Your current balance is: {balance}")
    else:
        await update.message.reply_text("User not found. Please start the bot with /start command.")

if __name__ == '__main__':
    main()
