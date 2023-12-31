import json
import jwt
import os
import six

from enum import Enum
from googleapiclient.errors import HttpError

import google_auth_oauthlib.flow
import google.oauth2.credentials

from cryptography.fernet import Fernet

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import models


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) + six.text_type(timestamp) +
            six.text_type(user.is_active)
        )
account_activation_token = TokenGenerator()


class AuthProvider(Enum):
    GOOGLE = 'google'

class OauthToken(models.Model):
    token = models.TextField()
    email = models.EmailField()
    provider = models.CharField(max_length=50, choices=[(tag, tag.value) for tag in AuthProvider])


    def get_token(self):
        encrypted_token_bytes = eval(self.token)
        decrypted_token_bytes = Fernet(settings.OAUTH_ENCRYPT_KEY).decrypt(encrypted_token_bytes)

        return eval(decrypted_token_bytes)


    def set_token(self, token):
        token = json.dumps(token)
        self.token = Fernet(settings.OAUTH_ENCRYPT_KEY).encrypt(token.encode('utf-8'))
        self.save()


def decode_oauth_state(state):
    decoded = jwt.decode(state, settings.JWT_ENCRYPT_KEY, algorithms=["HS256"])

    return decoded['audience'], decoded['expires_at']


def get_google_default_credentials():
    config = get_google_client_config()
    # TODO - update to use secret or env var
    token = OauthToken.objects.filter(email=settings.DEFAULT_GOOGLE_USER).first().get_token()

    return google.oauth2.credentials.Credentials(token=token['access_token'],
                                                 refresh_token=token['refresh_token'],
                                                 token_uri=config['token_uri'],
                                                 client_id=config['client_id'],
                                                 client_secret=config['client_secret'])

def get_google_client_config():
    return google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        settings.GOOGLE_CREDS_PATH,
        scopes=['https://www.googleapis.com/auth/contacts']).client_config


def handle_google_oauth_callback(request):
    oauth_flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(settings.GOOGLE_CREDS_PATH,
                                                                         scopes=['https://www.googleapis.com/auth/contacts'])
    oauth_flow.redirect_uri = f'https://{request.get_host()}/user/google/oauth/redirect'

    # google oauth flow auto parses the query params from the incoming request url
    requested_url = request.build_absolute_uri()

    # shim for local dev
    # if requested_url.find('127.0.0.1') != -1:
    #     requested_url = requested_url.replace('http://127', 'https://127')

    stored_token, is_new = OauthToken.objects.get_or_create(email=settings.DEFAULT_GOOGLE_USER, provider=AuthProvider.GOOGLE.value)

    new_token = oauth_flow.fetch_token(authorization_response=requested_url, access_type='offline', include_granted_scopes='true')
    stored_token.set_token(new_token)
