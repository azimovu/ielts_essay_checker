from flask import Flask, request, jsonify
from config import CLICK_SECRET_KEY
import hashlib
from database import add_purchased_uses, get_user


app = Flask(__name__)

@app.route('/click/prepare', methods=['POST'])
def prepare_payment():
    # Verify the request
    if not verify_click_request(request.form):
        return jsonify({'error': -1, 'error_note': 'Invalid signature'})

    # Check if the user exists and the amount is correct
    user_id = int(request.form['merchant_trans_id'])
    amount = float(request.form['amount'])
    user = get_user(user_id)

    if not user:
        return jsonify({'error': -5, 'error_note': 'User not found'})

    # You may want to add more checks here

    return jsonify({'error': 0, 'error_note': 'Success'})


@app.route('/click/complete', methods=['POST'])
def complete_payment():
    # Verify the request
    if not verify_click_request(request.form):
        return jsonify({'error': -1, 'error_note': 'Invalid signature'})

    # Process the payment
    user_id = int(request.form['merchant_trans_id'])
    amount = float(request.form['amount'])
    
    # Calculate the number of uses based on the amount
    uses = calculate_uses(amount)

    # Update the user's purchased uses
    add_purchased_uses(user_id, uses)

    return jsonify({'error': 0, 'error_note': 'Success'})

def verify_click_request(form_data):
    # Implement Click's signature verification logic here
    # You'll need to use the CLICK_SECRET_KEY
    # Refer to Click's documentation for the exact algorithm
    pass

def calculate_uses(amount):
    # Implement your logic to calculate the number of uses based on the amount
    pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)