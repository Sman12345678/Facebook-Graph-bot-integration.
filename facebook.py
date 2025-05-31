import requests, os

FB_APP_ID = os.environ.get('FB_APP_ID')
FB_APP_SECRET = os.environ.get('FB_APP_SECRET')
FB_REDIRECT_URI = os.environ.get('FB_REDIRECT_URI')

def exchange_code_for_token(code):
    url = "https://graph.facebook.com/v22.0/oauth/access_token"
    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": FB_REDIRECT_URI,
        "client_secret": FB_APP_SECRET,
        "code": code
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()['access_token']

def get_pages(access_token):
    url = "https://graph.facebook.com/v22.0/me/accounts"
    resp = requests.get(url, params={"access_token": access_token})
    resp.raise_for_status()
    return resp.json().get("data", [])
