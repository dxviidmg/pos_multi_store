from .settings import *
from decouple import Config, RepositoryEnv

config = Config(RepositoryEnv(".env.prod"))

AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME')


#Para conectarse a una base de datos remota desde mi local
DATABASE_URL = config('DATABASE_URL', None)
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }