import os
from dotenv import load_dotenv

# load the environment variable
load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    DATABASE_URI = os.getenv('DATABASE_URI')
    JWT_TOKEN_LOCATION = ['headers']