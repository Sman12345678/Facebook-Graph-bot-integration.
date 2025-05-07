from flask import Flask, request, jsonify, render_template
import requests
import json
import os
import logging

'''We are still going to change it to our name
like you always do, import .... as Àrch'''

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This is your secret handshake... don't lose it!
APP_ID = os.environ.get('FB_APP_ID', 'YOUR_APP_ID')
APP_SECRET = os.environ.get('FB_APP_SECRET', 'YOUR_APP_SECRET')
VERIFY_TOKEN = os.environ.get('FB_VERIFY_TOKEN', 'YOUR_VERIFY_TOKEN')

# Store page access tokens for multiple users/pages in memory as {page_id: access_token}
page_tokens = {}

@app.route('/')
def home():
    return render_template('home.html')

# Endpoint 1: Receive short-lived token, exchange it for long-lived one
@app.route('/fb_login', methods=['POST'])
def fb_login():
    data = request.get_json()
    user_access_token = data.get('access_token')
    if not user_access_token:
        logger.warning("No token, no fun!")
        return jsonify({'error': 'No token, no fun!'}), 400

    logger.info("Exchanging short-lived token... for the long-term relationship!")
    token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': APP_ID,
        'client_secret': APP_SECRET,
        'fb_exchange_token': user_access_token
    }
    try:
        response = requests.get(token_url, params=params)
        response.raise_for_status()
        data = response.json()
        if 'access_token' not in data:
            logger.error("No access_token in response: %s", data)
            return jsonify({'error': 'No access_token in response'}), 500
        return jsonify({'long_lived_token': data.get('access_token')})
    except Exception as e:
        logger.exception("Failed to exchange token: %s", e)
        return jsonify({'error': 'Failed to exchange token'}), 500

# Endpoint 2: Use long-lived token to get Page access token
@app.route('/get_page_token', methods=['POST'])
def get_page_token():
    data = request.get_json()
    long_lived_token = data.get('long_lived_token')
    if not long_lived_token:
        logger.warning("Token missing!")
        return jsonify({'error': 'Token missing!'}), 400

    logger.info("Fetching user's pages... let’s peek behind the curtain!")
    pages_url = "https://graph.facebook.com/v19.0/me/accounts"
    try:
        pages_response = requests.get(pages_url, params={'access_token': long_lived_token})
        pages_response.raise_for_status()
        pages_data = pages_response.json()
        if not pages_data.get('data'):
            logger.warning("No pages found. Create a page, human!")
            return jsonify({'error': 'No pages found. Create a page, human!'}), 404

        page_info = pages_data['data'][0]
        page_id = page_info['id']
        page_access_token = page_info['access_token']

        # Subscribe app to page (make chatbot official)
        subscribe_app_to_page(page_id, page_access_token)

        # Save page access token for this page_id
        page_tokens[page_id] = page_access_token

        return jsonify({'page_id': page_id, 'page_access_token': page_access_token})
    except Exception as e:
        logger.exception("Failed to get page token: %s", e)
        return jsonify({'error': 'Failed to get page token'}), 500

# Function: Subscribe the app to the page
def subscribe_app_to_page(page_id, page_access_token):
    logger.info(f"Subscribing app to page {page_id}... it’s getting serious!")
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    try:
        response = requests.post(url, params={'access_token': page_access_token})
        response.raise_for_status()
        logger.info("Subscription response: %s", response.text)
    except Exception as e:
        logger.exception("Failed to subscribe app to page: %s", e)

# Webhook verification - Like a secret knock at the door
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info("Webhook verified. Party started!")
        return challenge, 200
    else:
        logger.warning("No entry! Wrong token.")
        return 'Verification token mismatch', 403

#Seems i will use previous messageHandler
@app.route('/webhook', methods=['POST'])
def receive_message():
    data = request.get_json()
    logger.info("Incoming data from Facebook land: %s", json.dumps(data, indent=2))

    for entry in data.get('entry', []):
        for messaging_event in entry.get('messaging', []):
            sender_id = messaging_event['sender']['id']
            if 'message' in messaging_event:
                message_text = messaging_event['message'].get('text')
                logger.info(f"User said: {message_text}")

                # Try to determine the page_id for this webhook event
                page_id = entry.get('id')
                send_message(sender_id, "Hi! I'm your cheerful chatbot. How can I assist you today?", page_id=page_id)

    return 'EVENT_RECEIVED', 200

# Function to send a message back using the Messenger API
def send_message(recipient_id, message_text, page_id=None):
    logger.info(f"Sending message to {recipient_id}... hold my coffee!")

    # Determine which page access token to use
    access_token = page_tokens.get(page_id)
    if not access_token:
        logger.error("No page access token found for page_id: %s", page_id)
        return

    params = {
        'access_token': access_token
    }
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }

    try:
        response = requests.post(
            'https://graph.facebook.com/v19.0/me/messages',
            params=params,
            headers=headers,
            data=json.dumps(data)
        )
        response.raise_for_status()
        logger.info("Message response: %s", response.text)
    except Exception as e:
        logger.exception("Failed to send message: %s", e)

if __name__ == '__main__':
    logger.info("Starting Flask app... brace yourself, chatbot powers activate!")
    app.run(debug=False, host='0.0.0.0', port=3000)
