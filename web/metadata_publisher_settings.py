"""Non-HTTP worker settings with explicitly configured target and shared cache."""

from .metadata_test_settings import *  # noqa: F403
import boto3
import json
import os

# There are no defaults for deployment targets: a worker cannot silently fall
# back from dev to production or to the disposable rehearsal database.
secret_name = os.environ["METADATA_DATABASE_SECRET"]
database_name = os.environ["METADATA_DATABASE_NAME"]
region = os.environ.get("AWS_REGION", "us-east-2")
client = boto3.client("secretsmanager", region_name=region)
secret = json.loads(client.get_secret_value(SecretId=secret_name)["SecretString"])
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": secret["username"],
        "PASSWORD": secret["password"],
        "HOST": secret["host"],
        "PORT": secret["port"],
        "OPTIONS": {
            "sslmode": "require",
            "connect_timeout": 10,
            "options": "-c lock_timeout=10000 -c statement_timeout=120000",
        },
    }
}
del secret
MODEL_METADATA_REPOSITORIES = json.loads(os.environ["MODEL_METADATA_REPOSITORIES"])
cache_secret = json.loads(
    client.get_secret_value(SecretId=os.environ["METADATA_CACHE_SECRET"])[
        "SecretString"
    ]
)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"rediss://{cache_secret['host']}:{cache_secret.get('port', 6379)}/0",
        "KEY_PREFIX": os.environ["METADATA_CACHE_PREFIX"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.pickle.PickleSerializer",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
    }
}
CACHES["redis"] = CACHES["default"]
DEBUG = False
