const { Telegraf } = require('telegraf');

exports.handler = async (event) => {
  const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);

  if (event.httpMethod !== 'POST') {
    return { statusCode: 200, body: 'Send POST request to use the bot.' };
  }

  try {
    const update = JSON.parse(event.body);
    await bot.handleUpdate(update);
    return { statusCode: 200, body: 'OK' };
  } catch (error) {
    console.error('Error:', error);
    return { statusCode: 500, body: 'Error processing update' };
  }
};