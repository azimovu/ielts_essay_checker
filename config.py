import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Database configuration
DB_NAME = 'users.db'

# Click config

CLICK_MERCHANT_ID = os.getenv('CLICK_MERCHANT_ID')
CLICK_SERVICE_ID = os.getenv('CLICK_SERVICE_ID')
CLICK_SECRET_KEY = os.getenv('CLICK_SECRET_KEY')
CLICK_MERCHANT_USER_ID = os.getenv('CLICK_MERCHANT_USER_ID')

PAYCOM_TEST_URL = "https://checkout.test.paycom.uz/api"
PAYCOM_TOKEN = "371317599:TEST:1721717956046"
PAYCOM_PROD_URL = "https://checkout.paycom.uz/api"
PAYCOM_MERCHANT_KEY = "YDCIyk4ePpHEZmX4JHD15Qg%nspJ?6EgR?N4"