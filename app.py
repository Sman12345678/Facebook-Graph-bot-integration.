from flask import Flask, request, jsonify
import requests
import json
'''We are still going to change it to our name
like you you like, import .... as Àrch'''
app = Flask(__name__)

# This is your secret handshake... don't lose it!
APP_ID = 'YOUR_APP_ID'
APP_SECRET = 'YOUR_APP_SECRET'
VERIFY_TOKEN = 'YOUR_VERIFY_TOKEN'
DEFAULT_PAGE_ACCESS_TOKEN = 'WILL_BE_UPDATED_DURING_RUNTIME'  # Used for replying

# Endpoint 1: Receive short-lived token, exchange it for long-lived one
@app.route('/fb_login', methods=['POST'])
def fb_login():
    data = request.get_json()
    user_access_token = data.get('access_token')
    if not user_access_token:
        return jsonify({'error': 'No token, no fun!'}), 400

    print("Exchanging short-lived token... for the long-term relationship!")
    token_url = f"https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': APP_ID,
        'client_secret': APP_SECRET,
        'fb_exchange_token': user_access_token
    }
    response = requests.get(token_url, params=params)
    data = response.json()
    return jsonify({'long_lived_token': data.get('access_token')})


# Endpoint 2: Use long-lived token to get Page access token
@app.route('/get_page_token', methods=['POST'])
def get_page_token():
    data = request.get_json()
    long_lived_token = data.get('long_lived_token')
    if not long_lived_token:
        return jsonify({'error': 'Token missing!'}), 400

    print("Fetching user's pages... let’s peek behind the curtain!")
    pages_url = f"https://graph.facebook.com/v19.0/me/accounts"
    pages_response = requests.get(pages_url, params={'access_token': long_lived_token}).json()
    
    if not pages_response.get('data'):
        return jsonify({'error': 'No pages found. Create a page, human!'}), 404

    page_info = pages_response['data'][0]
    page_id = page_info['id']
    page_access_token = page_info['access_token']

    # Subscribe app to page (make chatbot official)
    subscribe_app_to_page(page_id, page_access_token)

    global DEFAULT_PAGE_ACCESS_TOKEN
    DEFAULT_PAGE_ACCESS_TOKEN = page_access_token

    return jsonify({'page_id': page_id, 'page_access_token': page_access_token})


# Function: Subscribe the app to the page
def subscribe_app_to_page(page_id, page_access_token):
    print(f"Subscribing app to page {page_id}... it’s getting serious!")
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    response = requests.post(url, params={'access_token': page_access_token})
    print("Subscription response:", response.text)


# Webhook verification - Like a secret knock at the door
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("Webhook verified. Party started!")
        return challenge, 200
    else:
        print("No entry! Wrong token.")
        return 'Verification token mismatch', 403


#Seems i will use previous messageHandler
@app.route('/webhook', methods=['POST'])
def receive_message():
    data = request.get_json()
    print("Incoming data from Facebook land:", json.dumps(data, indent=2))

    for entry in data.get('entry', []):
        for messaging_event in entry.get('messaging', []):
            sender_id = messaging_event['sender']['id']
            if 'message' in messaging_event:
                message_text = messaging_event['message'].get('text')
                print(f"User said: {message_text}")
                send_message(sender_id, "Hi! I'm your cheerful chatbot. How can I assist you today?")

    return 'EVENT_RECEIVED', 200


# Function to send a message back using the Messenger API
def send_message(recipient_id, message_text):
    print(f"Sending message to {recipient_id}... hold my coffee!")
    params = {
        'access_token': DEFAULT_PAGE_ACCESS_TOKEN
    }
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'recipient': {'id': recipient_id},
        'message': {'text': message_text}
    }

    response = requests.post(
        'https://graph.facebook.com/v19.0/me/messages',
        params=params,
        headers=headers,
        data=json.dumps(data)
    )
    print("Message response:", response.text)


if __name__ == '__main__':
    print("Starting Flask app... brace yourself, chatbot powers activate!")
    app.run(debug=True,host='0.0.0.0',port=3000)
