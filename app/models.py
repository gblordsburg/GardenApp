import base64
from datetime import datetime, timedelta
from time import time
from hashlib import md5
from flask import current_app, url_for
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
from sqlalchemy import desc
from app import db, login



class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = query.paginate(page, per_page, False)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page,
                                **kwargs),
                'next': url_for(endpoint, page=page + 1, per_page=per_page,
                                **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                                **kwargs) if resources.has_prev else None
            }
        }
        return data


followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

users_gardens = db.Table('users_gardens',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('garden_id', db.Integer, db.ForeignKey('garden.id'))
)



class User(PaginatedAPIMixin, UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    plants = db.relationship('Plant', backref='grower', lazy='dynamic')
    gardens = db.relationship('Garden', secondary=users_gardens, backref=db.backref('users', lazy='dynamic'))
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    #Avatar function returns URL of users avatar img, scaled to requestedd size in pixels.
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0

    def usergardens(self):
        gardens = self.gardens
        return gardens

    def user_gardens(self):
        gardens = Garden.query.join(
            users_gardens, (users_gardens.c.garden_id == Garden.id)).filter(
                users_gardens.c.user_id == self.id)
        return gardens.order_by(desc(Garden.created))

    def followed_posts(self):
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
                (followers.c.follower_id == self.id) & (Post.wall_post != True))
        own = Post.query.filter_by(user_id=self.id).filter(Post.wall_post != True)
        return followed.union(own).order_by(Post.timestamp.desc())

    def followed_plants(self):
        followed = Plant.query.join(
            followers, (followers.c.followed_id == Plant.user_id)).filter(
                followers.c.follower_id == self.id)
        own = Plant.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Plant.timestamp.desc())

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen.isoformat() + 'Z',
            'about_me': self.about_me,
            'post_count': self.posts.count(),
            'follower_count': self.followers.count(),
            'followed_count': self.followed.count(),
            '_links': {
                'self': url_for('api.get_user', id=self.id),
                'followers': url_for('api.get_followers', id=self.id),
                'followed': url_for('api.get_followed', id=self.id),
                'avatar': self.avatar(128)
            }
        }
        if include_email:
            data['email'] = self.email
        return data

    def from_dict(self, data, new_user=False):
        for field in ['username', 'email', 'about_me']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def get_token(self, expires_in=3600):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = User.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        return user



class Post(PaginatedAPIMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    wall_post = db.Column(db.Boolean, default=False)
    wall_owner_id = db.Column(db.Integer)
    reply_post = db.Column(db.Boolean, default=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    replies = db.relationship('Post', backref=db.backref('parent_comment', remote_side=[id], lazy='dynamic', uselist=True))

    def __repr__(self):
        return '<Post {}>'.format(self.body)


    def to_dict(self):
        data = {
            'id': self.id,
            'body': self.body,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'user': self.author.username,
            'user_id': self.author.id,
            'wall_post' : self.wall_post,
            'wall_owner_id' : self.wall_owner_id
        }
        return data



class Garden(PaginatedAPIMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), index=True)
    address = db.Column(db.String(200), index=True)
    lat = db.Column(db.Integer, index=True)
    lon = db.Column(db.Integer, index=True)
    created = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    plants = db.relationship('Plant', backref='garden', lazy='dynamic')

    def __repr__(self):
        return '<Garden {}>'.format(self.name)


    def to_dict(self):
        plants = self.plants
        plants_dict = []
        for plant in plants:
            plant_obj = Plant.to_dict(plant)
            plants_dict.append(plant_obj)
        data = {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'lat': self.lat,
            'lon': self.lon,
            'created': self.created.isoformat() + 'Z',
            'plants': plants_dict
        }
        return data


class Plant(PaginatedAPIMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    garden_id = db.Column(db.Integer, db.ForeignKey('garden.id'))

    def __repr__(self):
        return '<Plant {}>'.format(self.name)


    def to_dict(self):
        data = {
            'id': self.id,
            'name': self.name,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'grower': self.grower.username
        }
        if self.garden:
            data['garden'] = self.garden.name
            data['address'] = self.garden.address
            data['lat'] = self.garden.lat
            data['lon'] = self.garden.lon
        else:
            data['garden'] = None
            data['address'] = None
            data['lat'] = None
            data['lon'] = None
        return data

@login.user_loader
def load_user(id):
    return User.query.get(int(id))


