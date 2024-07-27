const { spawn } = require('child_process');
const path = require('path');

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 200, body: 'Send POST request to use the bot.' };
  }

  return new Promise((resolve, reject) => {
    const pythonProcess = spawn('python', [path.join(__dirname, 'bot.py')], {
      env: { ...process.env, TELEGRAM_UPDATE: event.body }
    });

    let result = '';

    pythonProcess.stdout.on('data', (data) => {
      result += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`Python Error: ${data}`);
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        console.error(`Python process exited with code ${code}`);
        resolve({ statusCode: 500, body: 'Error processing update' });
      } else {
        resolve({ statusCode: 200, body: result || 'OK' });
      }
    });
  });
};