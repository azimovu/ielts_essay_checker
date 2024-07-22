from telegram import Update
from telegram.ext import ContextTypes

# Constants
ADMIN_USER_ID = 872765833  

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Feedback option."""
    await update.message.reply_text("Please provide your feedback on the score.")
    context.user_data['state'] = 'waiting_for_feedback'

async def process_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the received feedback and forward it to the admin with detailed user information."""
    feedback = update.message.text
    user = update.effective_user
    
    # Prepare the feedback message with detailed user information
    feedback_message = (
        f"New feedback received:\n\n"
        f"From: {user.mention_html()}\n"
        f"User ID: {user.id}\n"
        f"Username: {user.username or 'Not set'}\n"
        f"First Name: {user.first_name}\n"
        f"Last Name: {user.last_name or 'Not set'}\n\n"
        f"Feedback: {feedback}"
    )
    
    # Send the feedback to the admin
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=feedback_message, parse_mode='HTML')
        await update.message.reply_text("Thank you for your feedback! It has been sent to our team.")
    except Exception as e:
        print(f"Error sending feedback to admin: {e}")
        await update.message.reply_text("Thank you for your feedback! We've received it, but there was an issue forwarding it to our team.")
    
    # Clear the user state
    context.user_data.pop('state', None)