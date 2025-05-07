from flask import Flask, request, jsonify, redirect, url_for,render_template
import requests
import os

app = Flask(__name__)

FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')
REDIRECT_URI = 'YOUR_REDIRECT_URI'  # Should match the redirect URI configured in your Facebook App settings
WEBHOOK_VERIFY_TOKEN = 'YOUR_WEBHOOK_VERIFY_TOKEN' # A secret token for webhook verification

@app.route('/')
def home():
    return render_template('home.html')
    
@app.route('/facebook_login')
def facebook_login():
    auth_url = f'https://www.facebook.com/v23.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={REDIRECT_URI}&scope=public_profile,email,pages_manage_posts,pages_read_engagement'
    return redirect(auth_url)

@app.route('/facebook_callback')
def facebook_callback():
    code = request.args.get('code')
    if code:
        # Exchange the authorization code for an access token
        token_url = 'https://graph.facebook.com/v23.0/oauth/access_token'
        token_params = {
            'client_id': FACEBOOK_APP_ID,
            'client_secret': FACEBOOK_APP_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        token_response = requests.get(token_url, params=token_params)
        token_data = token_response.json()
        user_access_token = token_data.get('access_token')

        if user_access_token:
            # Get the list of managed pages
            pages_url = f'https://graph.facebook.com/v23.0/me/accounts'
            pages_params = {'access_token': user_access_token}
            pages_response = requests.get(pages_url, params=pages_params)
            pages_data = pages_response.json().get('data', [])

            # Here you would typically store the user access token and present
            # the list of pages to the user to select one.

            return jsonify({'pages': pages_data, 'user_access_token': user_access_token})
        else:
            return jsonify({'error': 'Failed to retrieve access token'})
    else:
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        return jsonify({'error': error, 'error_description': error_description})

@app.route('/get_page_token/<page_id>')
def get_page_token(page_id):
    user_access_token = request.args.get('user_access_token') # You'd likely retrieve this from your database
    if user_access_token and page_id:
        page_token_url = f'https://graph.facebook.com/v23.0/{page_id}'
        page_token_params = {'fields': 'access_token', 'access_token': user_access_token}
        page_token_response = requests.get(page_token_url, params=page_token_params)
        page_token_data = page_token_response.json()
        page_access_token = page_token_data.get('access_token')

        if page_access_token:
            # Now you have the Page access token. Store it securely and associate it with the user and page.
            return jsonify({'page_id': page_id, 'page_access_token': page_access_token})
        else:
            return jsonify({'error': f'Failed to retrieve page access token for page ID: {page_id}'})
    else:
        return jsonify({'error': 'Missing user access token or page ID'})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Webhook verification
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if verify_token == WEBHOOK_VERIFY_TOKEN:
            return challenge
        else:
            return 'Error, invalid verification token', 403
    elif request.method == 'POST':
        data = request.get_json()
        # Process webhook events (e.g., new messages) here
        print("Webhook received:", data)
        # You would then use the Page access token to send a response
        return 'OK', 200

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=3000)
