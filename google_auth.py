import dotenv
import json
import jwt
import os
import webbrowser

from urllib.parse import quote
from datetime import datetime, timedelta

import google_auth_oauthlib.flow

dotenv.load_dotenv()

# url encode the redirect uri
redirect_uri = quote("https://127.0.0.1:8000/user/google/oauth/redirect")

oauth_flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    os.getenv('GOOGLE_CREDS_PATH'),
    scopes=['https://www.googleapis.com/auth/contacts'])


state = jwt.encode({
    'audience': 'brainscore-google-default-user',
    'expires_at': (datetime.now() + timedelta(minutes=5)).timestamp()
}, os.getenv('JWT_ENCRYPT_KEY'), algorithm="HS256")

authorization_url, _state = oauth_flow.authorization_url(
    access_type='offline',
    include_granted_scopes='true',
    state=state)

webbrowser.open_new(f'{authorization_url}&redirect_uri={redirect_uri}')
