"""Isolated PostgreSQL settings for metadata tests and migration rehearsals.

Never imports production settings or retrieves secrets. The database must be
explicitly created for local testing; Django creates a separate test database.
"""
import os
import getpass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'metadata-local-tests-only'
CACHE_REFRESH_TOKEN = 'metadata-local-test-token'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes',
                  'django.contrib.sessions', 'django.contrib.messages',
                  'django.contrib.staticfiles', 'compressor', 'benchmarks']
AUTH_USER_MODEL = 'benchmarks.User'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.environ.get('METADATA_TEST_DB', 'metadata_rehearsal'),
    'HOST': os.environ.get('METADATA_TEST_HOST', '/private/tmp/pr560-postgres'),
    'PORT': os.environ.get('METADATA_TEST_PORT', '55460'),
    'USER': os.environ.get('METADATA_TEST_USER', getpass.getuser()),
    'PASSWORD': os.environ.get('METADATA_TEST_PASSWORD', ''),
}}
TEST_RUNNER = 'django.test.runner.DiscoverRunner'
ROOT_URLCONF = 'web.metadata_test_urls'
MIDDLEWARE = ['django.contrib.sessions.middleware.SessionMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware',
              'django.contrib.messages.middleware.MessageMiddleware']
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'APP_DIRS': True, 'OPTIONS': {'context_processors': [
                  'django.template.context_processors.request',
                  'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages',
              ]}}]
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
USE_TZ = True

# Optional styling for a local browser rehearsal; ordinary tests need no Node build.
if os.environ.get('METADATA_PREVIEW') == '1':
    STATIC_ROOT = '/private/tmp/pr560-preview-static'
    STATICFILES_FINDERS = ['django.contrib.staticfiles.finders.FileSystemFinder',
                          'django.contrib.staticfiles.finders.AppDirectoriesFinder',
                          'compressor.finders.CompressorFinder']
    COMPRESS_PRECOMPILERS = [('text/x-sass', f'"{BASE_DIR}/node_modules/.bin/sass" {{infile}} {{outfile}} --no-source-map --quiet')]
