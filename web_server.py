from flask import Flask, request, jsonify
import logging
from logging.handlers import RotatingFileHandler
from waitress import serve
import traceback

app = Flask(__name__)

# Configure logging
handler = RotatingFileHandler('/var/www/essayfol/flask_app.log', maxBytes=10000000, backupCount=3)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    app.logger.error(traceback.format_exc())
    return jsonify({"error": "An internal server error occurred"}), 500

# Your existing routes here...

if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=5000, threads=4, connection_limit=1000, channel_timeout=30)