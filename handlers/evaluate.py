from telegram import Update
from telegram.ext import ContextTypes
from utils import essay_analysis

async def handle_evaluate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Evaluate option."""
    await update.message.reply_text("Please send me the topic of your essay.")
    context.user_data['state'] = 'waiting_for_topic'

async def handle_essay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the essay submission and analysis."""
    topic = context.user_data.get('topic')
    essay = update.message.text

    analysis_result = await essay_analysis.analyze_essay(topic, essay)
    await update.message.reply_text(f"*Analysis Result:*\n\n{analysis_result}", parse_mode='Markdown')

    # Reset state
    context.user_data.clear()