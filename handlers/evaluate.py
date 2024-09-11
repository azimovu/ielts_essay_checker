from telegram import Update
from telegram.ext import ContextTypes
from utils import essay_analysis
from utils.usage_utils import check_and_decrement_uses, handle_insufficient_uses

async def handle_evaluate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Evaluate option."""
    await update.message.reply_text("Please send me the topic of your essay.")
    context.user_data['state'] = 'waiting_for_topic'

async def handle_essay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the essay submission and analysis."""
    user_id = update.effective_user.id
    topic = context.user_data.get('topic')
    essay = update.message.text

    # Check if the user's state is still 'waiting_for_topic'
    if context.user_data.get('state') != 'waiting_for_topic':
        return

    # Reset state
    context.user_data.clear()

    # Check and decrement uses before making the API call
    if await check_and_decrement_uses(user_id):
        analysis_result = await essay_analysis.analyze_essay(topic, essay)
        await update.message.reply_text(f"*Analysis Result:*\n\n{analysis_result}", parse_mode='Markdown')
    else:
        await handle_insufficient_uses(update, context)
