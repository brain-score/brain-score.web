import json
import jwt
import os
import six

from enum import Enum

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
