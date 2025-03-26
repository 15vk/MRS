from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from .models import User, MovieComment, FriendRequest, Friendship, Genre
from . import db
import requests
from fuzzywuzzy import process
import re  # For password validation

main = Blueprint('main', __name__)

TMDB_API_KEY = "e508d75277a707b73ee8bb0698caa1fd"
TMDB_TRENDING_URL = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"
TMDB_SUGGESTED_URL = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&language=en-US&page=1"
TMDB_MOVIE_DETAILS_URL = "https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&language=en-US"
TMDB_MOVIE_CREDITS_URL = "https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={api_key}"
TMDB_GENRES_URL = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}&language=en-US"

@main.route('/search')
def search():
    query = request.args.get('query', '')
    if not query:
        flash('Please enter a search query.', 'warning')
        return redirect(url_for('main.home'))

    try:
        # Search movies from TMDB
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
        response = requests.get(search_url)
        if response.status_code == 200:
            movies = response.json().get('results', [])
            # Sort movies by popularity (descending order)
            movies.sort(key=lambda x: x.get('popularity', 0), reverse=True)
            # Limit to top 20 results
            movies = movies[:20]
        else:
            movies = []
            flash('Failed to fetch movie data.', 'danger')

        return render_template('search_results.html', query=query, movies=movies)
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('main.home'))

@main.route('/')
def home():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            trending_movies = requests.get(TMDB_TRENDING_URL).json().get('results', [])
            suggested_movies = requests.get(TMDB_SUGGESTED_URL).json().get('results', [])
            return render_template('index.html', username=user.username, trending_movies=trending_movies, suggested_movies=suggested_movies)
        else:
            flash('User not found. Please log in again.', 'danger')
            return redirect(url_for('main.logout'))
    return render_template('index.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('main.home'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')  # Stay on the login page
    
    return render_template('login.html')

@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already taken. Please choose a different one.', 'danger')
            return redirect(url_for('main.signup'))
        
        # Validate password
        if len(password) < 6 or not re.search("[a-zA-Z]", password) or not re.search("[0-9]", password):
            flash('Password must be at least 6 characters long and contain both alphabets and numbers.', 'danger')
            return redirect(url_for('main.signup'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        flash('Signup successful! Please choose your favorites.', 'success')
        return redirect(url_for('main.favorites'))
    return render_template('signup.html')

@main.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_logged_in' in session:
        users = User.query.all()
        return render_template('admin.html', users=users)
    
    if request.method == 'POST':
        password = request.form['password']
        if password == 'Vinay1505':
            session['admin_logged_in'] = True
            users = User.query.all()
            return render_template('admin.html', users=users)
        else:
            flash('Invalid admin password', 'danger')
            return redirect(url_for('main.admin'))
    return render_template('admin_login.html')

@main.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    #flash('Admin logged out successfully.', 'success')
    return redirect(url_for('main.admin'))

@main.route('/logout')
def logout():
    session.pop('user_id', None)
    #flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))

@main.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'admin_logged_in' not in session:
        flash('Please log in as admin to perform this action.', 'danger')
        return redirect(url_for('main.admin'))
    
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        #flash('User deleted successfully.', 'success')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('main.admin'))

@main.route('/movie_desc/<int:movie_id>')
def movie_desc(movie_id):
    movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)).json()
    movie_credits = requests.get(TMDB_MOVIE_CREDITS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)).json()
    cast = movie_credits.get('cast', [])[:5]  # Get top 5 cast members
    return render_template('movie_desc.html', movie=movie_details, cast=cast)

@main.route('/mylist')
def mylist():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        # Fetch user's movie lists from the database if applicable
        return render_template('mylist.html', username=user.username)
    else:
        flash('Please log in to view your lists.', 'danger')
        return redirect(url_for('main.login'))
    
@main.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'danger')
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    # Convert the comma-separated genre IDs into a list of integers
    genre_ids = [int(genre_id) for genre_id in user.favorite_genre.split(',')] if user.favorite_genre else []

    # Query the Genre table to get the genre names
    genres = Genre.query.filter(Genre.id.in_(genre_ids)).all()
    genre_names = [genre.name for genre in genres]

    return render_template('profile.html', user=user, genre_names=genre_names)

@main.route('/favorites', methods=['GET', 'POST'])
def favorites():
    if 'user_id' not in session:
        flash('Please log in to choose your favorite genres.', 'danger')
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if request.method == 'POST':
        selected_genres = request.form.getlist('selected_genres')  # Get selected genres as a list
        if selected_genres:
            genre_ids = [int(genre_id) for genre_id in selected_genres]
            user.favorite_genre = ','.join(map(str, genre_ids))  # Save as a comma-separated string
            db.session.commit()
            flash('Your favorite genres have been saved!', 'success')
        else:
            flash('No genres selected.', 'warning')
        return redirect(url_for('main.home'))  # Redirect to the index page (home)

    genres = Genre.query.all()  # Fetch genres from the database
    return render_template('favorites.html', genres=genres)


@main.route('/community', methods=['GET', 'POST'])
def community():
    if 'user_id' not in session:
        flash('Please log in to manage your friends.', 'danger')
        return redirect(url_for('main.login'))
    
    user = User.query.get(session['user_id'])
    incoming_requests = user.received_requests.all()
    sent_requests = [req.receiver_id for req in user.sent_requests.all()]
    friends = [friendship.user_id1 if friendship.user_id1 != user.id else friendship.user_id2 for friendship in user.friends.all()]
    
    if request.method == 'POST':
        search_query = request.form['search_query']
        # Limit search results to 10 users and exclude the logged-in user
        users = User.query.filter(User.username.contains(search_query), User.id != user.id).limit(10).all()
        return render_template('community.html', users=users, incoming_requests=incoming_requests, sent_requests=sent_requests, friends=friends)
    
    # Show the first 10 users when the page is opened directly
    users = User.query.filter(User.id != user.id).limit(10).all()
    return render_template('community.html', users=users, incoming_requests=incoming_requests, sent_requests=sent_requests, friends=friends)

@main.route('/send_friend_request/<int:receiver_id>', methods=['POST'])
def send_friend_request(receiver_id):
    if 'user_id' not in session:
        flash('Please log in to send friend requests.', 'danger')
        return redirect(url_for('main.login'))
    
    sender_id = session['user_id']
    friend_request = FriendRequest(sender_id=sender_id, receiver_id=receiver_id)
    db.session.add(friend_request)
    db.session.commit()
    
    flash('Friend request sent!', 'success')
    return redirect(url_for('main.community'))

@main.route('/accept_friend_request/<int:request_id>', methods=['POST'])
def accept_friend_request(request_id):
    if 'user_id' not in session:
        flash('Please log in to accept friend requests.', 'danger')
        return redirect(url_for('main.login'))
    
    friend_request = FriendRequest.query.get(request_id)
    if friend_request and friend_request.receiver_id == session['user_id']:
        friendship = Friendship(user_id1=friend_request.sender_id, user_id2=friend_request.receiver_id)
        db.session.add(friendship)
        db.session.delete(friend_request)
        db.session.commit()
        
        flash('Friend request accepted!', 'success')
    else:
        flash('Invalid friend request.', 'danger')
    
    return redirect(url_for('main.community'))

@main.route('/profile/<int:user_id>')
def view_profile(user_id):
    user = User.query.get(user_id)
    if user:
        return render_template('profile.html', user=user)
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('main.community'))

# ...existing code...

@main.route('/friends/chat', methods=['GET'])
def friends_chat():
    if 'user_id' not in session:
        flash('Please log in to chat with your friends.', 'danger')
        return redirect(url_for('main.login'))
    
    user = User.query.get(session['user_id'])
    friends = [friendship.user_id1 if friendship.user_id1 != user.id else friendship.user_id2 for friendship in user.friends.all()]
    friends_list = User.query.filter(User.id.in_(friends)).all()
    
    return render_template('friends_chat.html', friends=friends_list)

# ...existing code...

@main.route('/chat/messages/<int:friend_id>', methods=['GET'])
def get_chat_messages(friend_id):
    if 'user_id' not in session:
        return jsonify({'messages': []})
    
    user_id = session['user_id']
    # Fetch messages between the logged-in user and the friend (placeholder logic)
    messages = [
        {"sender": "You", "text": "Hello!"},
        {"sender": "Friend", "text": "Hi, how are you?"}
    ]  # Replace with actual database query
    return jsonify({'messages': [f"{msg['sender']}: {msg['text']}" for msg in messages]})

@main.route('/chat/send', methods=['POST'])
def send_chat_message():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to send messages.'}), 401
    
    data = request.get_json()
    friend_id = data.get('friendId')
    message = data.get('message')
    
    # Save the message to the database (placeholder logic)
    # Replace with actual database query to save the message
    
    return jsonify({'success': True})

# ...existing code...

@main.route('/movie/<int:movie_id>/feedback', methods=['GET', 'POST'])
def movie_feedback(movie_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to provide feedback.'}), 401

    user_id = session['user_id']

    if request.method == 'GET':
        feedback = MovieComment.query.filter_by(movie_id=movie_id, user_id=user_id).first()
        if feedback:
            return jsonify({
                'feedback': feedback.feedback,
                'rating': feedback.rating
            })
        return jsonify({'feedback': None, 'rating': None})

    if request.method == 'POST':
        data = request.get_json()
        feedback_text = data.get('feedback')
        rating = data.get('rating')

        feedback = MovieComment.query.filter_by(movie_id=movie_id, user_id=user_id).first()
        if feedback:
            # Update existing feedback
            feedback.feedback = feedback_text
            feedback.rating = rating
        else:
            # Add new feedback
            feedback = MovieComment(
                user_id=user_id,
                movie_id=movie_id,
                feedback=feedback_text,
                rating=rating
            )
            db.session.add(feedback)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Feedback submitted successfully!'})