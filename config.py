import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-might-guess-sometime'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    #sending errors by email
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.googlemail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or 1
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'flaskapperrors'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')or 'wgswtrq9gs'
    ADMINS = ['flaskapperrors@gmail.com']
    POSTS_PER_PAGE = 4
    PLANTS_PER_PAGE = 4
    GOOGLEMAPS_KEY = 'AIzaSyCyX0uZDxs4ekWQz-uSuhvhpABMOFf8QfI'