from .settings import *
from decouple import Config, RepositoryEnv

config = Config(RepositoryEnv(".env_prod"))

AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME')
AWS_QUERYSTRING_AUTH = False

STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
    },
    'staticfiles': {
        'BACKEND': 'storages.backends.s3boto3.S3StaticStorage',
    },
}


#Para conectarse a una base de datos remota desde mi local
DATABASE_URL = config('DATABASE_URL', None)
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }