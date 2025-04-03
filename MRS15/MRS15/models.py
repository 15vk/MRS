from . import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    favorite_genre = db.Column(db.String(150), nullable=True)
    favorite_movies = db.Column(db.String(150), nullable=True)
    sent_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.sender_id', backref='sender', lazy='dynamic')
    received_requests = db.relationship('FriendRequest', foreign_keys='FriendRequest.receiver_id', backref='receiver', lazy='dynamic')
    friends = db.relationship('Friendship', primaryjoin='or_(User.id==Friendship.user_id1, User.id==Friendship.user_id2)', lazy='dynamic')
    watched_movies = db.relationship('WatchedMovie', backref='user', lazy='dynamic')
    wishlist = db.relationship('WishlistMovie', backref='user', lazy='dynamic')
    last_online = db.Column(db.DateTime, default=db.func.current_timestamp())

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id1 = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id2 = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class MovieComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    likes = db.Column(db.Integer, default=0, nullable=False)
    dislikes = db.Column(db.Integer, default=0, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)

    user = db.relationship('User', backref='comments')

class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Genre ID from the API
    name = db.Column(db.String(100), nullable=False)  # Genre name

class WatchedMovie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    review = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class WishlistMovie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class UserList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationship with User model
    user = db.relationship('User', backref='lists')
    
class UserListMovie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('user_list.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationship with UserList model
    user_list = db.relationship('UserList', backref='movies')

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    explicit_rating = db.Column(db.Float, nullable=True)
    implicit_rating = db.Column(db.Float, nullable=True)
    last_updated = db.Column(db.DateTime, default=db.func.current_timestamp())
    watch_count = db.Column(db.Integer, default=0)
    
    user = db.relationship('User', backref='preferences')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_read = db.Column(db.Boolean, default=False)
    shared_list_id = db.Column(db.Integer, nullable=True)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class SavedList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_list_id = db.Column(db.Integer, nullable=False)
    original_owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='saved_lists')
    original_owner = db.relationship('User', foreign_keys=[original_owner_id])

class SavedListMovie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    saved_list_id = db.Column(db.Integer, db.ForeignKey('saved_list.id'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    
    # Relationship
    saved_list = db.relationship('SavedList', backref='movies')

class ReceivedList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_list_id = db.Column(db.Integer, db.ForeignKey('user_list.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_lists')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_lists')
    original_list = db.relationship('UserList', backref='received_lists')

