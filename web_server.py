from flask import Flask, request, jsonify
from config import PAYCOM_MERCHANT_ID, PAYCOM_SECRET_KEY
import hashlib
import time
from database import (
    add_purchased_uses, get_user, update_transaction, get_transaction,
    get_order, add_transaction, get_free_uses_left, get_purchased_uses
)
import logging
from logging.handlers import RotatingFileHandler
from waitress import serve
import traceback

app = Flask(__name__)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = RotatingFileHandler('flask_app.log', maxBytes=100000, backupCount=3)
handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({"error": "An internal server error occurred"}), 500

def verify_paycom_request(request_data):
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return False
    
    auth_parts = auth_header.split()
    if len(auth_parts) != 2 or auth_parts[0].lower() != 'basic':
        return False
    
    try:
        provided_token = auth_parts[1].encode('utf-8')
        expected_token = f"{PAYCOM_MERCHANT_ID}:{PAYCOM_SECRET_KEY}".encode('utf-8')
        return provided_token == hashlib.md5(expected_token).hexdigest().encode('utf-8')
    except Exception as e:
        logger.error(f"Error verifying Paycom request: {str(e)}")
        return False

@app.route('/payme/complete', methods=['POST'])
def handle_paycom_request():
    logger.info(f'Received POST request to /payme/complete from {request.remote_addr}')
    logger.info(f'Request headers: {dict(request.headers)}')
    logger.info(f'Request JSON data: {request.json}')
    
    if not verify_paycom_request(request.json):
        logger.warning('Invalid authentication for Paycom request')
        #return jsonify({'error': {'code': -32504, 'message': 'Authorization failed'}})

    method = request.json.get('method')
    params = request.json.get('params', {})

    if method == 'CheckTransaction':
        return check_transaction(params)
    elif method == 'CreateTransaction':
        return create_transaction(params)
    elif method == 'PerformTransaction':
        return perform_transaction(params)
    elif method == 'CancelTransaction':
        return cancel_transaction(params)
    elif method == 'CheckPerformTransaction':
        return check_perform_transaction(params)
    elif method == 'CheckRemainingUses':
        return check_remaining_uses(params)
    else:
        logger.warning(f'Unknown method in Paycom request: {method}')
        return jsonify({'error': {'code': -32601, 'message': 'Method not found'}})

def check_remaining_uses(params):
    account = params.get('account', {})
    user_id = account.get('user_id')
    
    if not user_id:
        return jsonify({"error": {"code": -31050, "message": "User ID not provided"}})
    
    free_uses = get_free_uses_left(user_id)
    purchased_uses = get_purchased_uses(user_id)
    
    return jsonify({
        "result": {
            "free_uses": free_uses,
            "purchased_uses": purchased_uses,
            "total_uses": free_uses + purchased_uses
        }
    })

def check_perform_transaction(params):
    account = params.get('account', {})
    amount = params.get('amount')
    
    user_id = account.get('user_id')
    if not user_id:
        return jsonify({"result": {"allow": False}, "error": {"code": -31050, "message": "User ID not provided"}})
    
    user = get_user(user_id)
    if not user:
        return jsonify({"result": {"allow": False}, "error": {"code": -31050, "message": "User not found"}})
    
    total_uses = user[3] + user[4]  # free_uses_left + purchased_uses
    requested_uses = amount // 100  # Предполагаем, что 1 использование стоит 100 единиц валюты
    
    if total_uses >= requested_uses:
        return jsonify({"result": {"allow": True}})
    else:
        return jsonify({"result": {"allow": False}, "error": {"code": -31001, "message": "Insufficient uses"}})

def check_transaction(params):
    transaction_id = params.get('id')
    
    transaction = get_transaction(transaction_id)
    if not transaction:
        return jsonify({'error': {'code': -31003, 'message': 'Transaction not found'}})
    
    return jsonify({
        "result": {
            "create_time": transaction[5],
            "perform_time": transaction[6],
            "cancel_time": transaction[7],
            "transaction": transaction[0],
            "state": transaction[3],
            "reason": transaction[8]
        }
    })

def create_transaction(params):
    transaction_id = params.get('id')
    time_param = params.get('time')
    amount = params.get('amount')
    account = params.get('account', {})
    
    existing_transaction = get_transaction(transaction_id)
    if existing_transaction:
        return jsonify({
            "result": {
                "create_time": existing_transaction[4],  # Index 4 is create_time
                "transaction": existing_transaction[0],  # Index 0 is id
                "state": existing_transaction[3]         # Index 3 is state
            }
        })
    
    user_id = account.get('user_id')
    if not user_id:
        return jsonify({'error': {'code': -31050, 'message': 'User ID not provided'}})
    
    user = get_user(user_id)
    if not user:
        return jsonify({'error': {'code': -31050, 'message': 'User not found'}})
    
    # Проверяем, достаточно ли у пользователя использований
    total_uses = user[3] + user[4]  # free_uses_left + purchased_uses
    requested_uses = amount // 100  # Предполагаем, что 1 использование стоит 100 единиц валюты
    
    if total_uses < requested_uses:
        return jsonify({'error': {'code': -31001, 'message': 'Insufficient uses'}})
    
    # Создаем новую транзакцию
    add_transaction(transaction_id, user_id, amount, 1, time_param, None)
    
    return jsonify({
        "result": {
            "create_time": time_param,
            "transaction": transaction_id,
            "state": 1
        }
    })

def perform_transaction(params):
    transaction_id = params.get('id')
    
    transaction = get_transaction(transaction_id)
    if not transaction:
        return jsonify({'error': {'code': -31003, 'message': 'Transaction not found'}})
    
    if transaction[3] == 2:  # Transaction already completed
        return jsonify({
            "result": {
                "perform_time": transaction[6],
                "transaction": transaction[0],
                "state": transaction[3]
            }
        })
    
    if transaction[3] != 1:
        return jsonify({'error': {'code': -31008, 'message': 'Unable to complete operation'}})
    
    order = get_order(transaction[9])
    if not order:
        return jsonify({'error': {'code': -31050, 'message': 'Order not found'}})
    
    # Here, implement the logic to complete the order (e.g., add purchased uses)
    add_purchased_uses(order[1], order[2] // 100)  # Assuming amount is in cents
    
    perform_time = int(time.time() * 1000)
    update_transaction(transaction_id, state=2, perform_time=perform_time)
    
    return jsonify({
        "result": {
            "perform_time": perform_time,
            "transaction": transaction_id,
            "state": 2
        }
    })

def cancel_transaction(params):
    transaction_id = params.get('id')
    reason = params.get('reason')
    
    transaction = get_transaction(transaction_id)
    if not transaction:
        return jsonify({'error': {'code': -31003, 'message': 'Transaction not found'}})
    
    if transaction[3] == 2:  # Transaction already completed
        order = get_order(transaction[9])
        if not order:
            return jsonify({'error': {'code': -31007, 'message': 'Unable to cancel transaction'}})
        
        # Here, implement the logic to reverse the completed order (e.g., remove purchased uses)
        # This is commented out for now, as you mentioned you need to handle cancel purchase logic later
        # remove_purchased_uses(order[1], order[2] // 100)
    
    cancel_time = int(time.time() * 1000)
    cancel_transaction(transaction_id, reason, cancel_time)
    
    return jsonify({
        "result": {
            "cancel_time": cancel_time,
            "transaction": transaction_id,
            "state": -1  # Assuming -1 is the state for cancelled transactions
        }
    })

if __name__ == "__main__":
    serve(app, host='127.0.0.1', port=5000, threads=4, connection_limit=1000, channel_timeout=30)
