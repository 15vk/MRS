from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from .models import User, MovieComment, FriendRequest, Friendship, Genre, WatchedMovie, WishlistMovie
from . import db
import requests
from fuzzywuzzy import fuzz,process
import re  # For password validation

main = Blueprint('main', __name__)

TMDB_API_KEY = "e508d75277a707b73ee8bb0698caa1fd"
TMDB_TRENDING_URL = f"https://api.themoviedb.org/3/trending/movie/week?api_key={TMDB_API_KEY}"
TMDB_SUGGESTED_URL = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&language=en-US&page=1"
TMDB_MOVIE_DETAILS_URL = "https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&language=en-US"
TMDB_MOVIE_CREDITS_URL = "https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={api_key}"
TMDB_GENRES_URL = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}&language=en-US"


@main.route('/search1')
def search1():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'movies': []})  # Return an empty list if no query is provided

    try:
        # Fetch movies from TMDB API
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&include_adult=false"
        response = requests.get(search_url)
        if response.status_code == 200:
            movies = response.json().get('results', [])
            return jsonify({'movies': movies})  # Return movies as JSON
        else:
            return jsonify({'movies': [], 'error': 'Failed to fetch movies from TMDB API'}), 500
    except Exception as e:
        return jsonify({'movies': [], 'error': str(e)}), 500
    
@main.route('/search')
def search():
    query = request.args.get('query', '').strip()
    if not query:
        return render_template('search_results.html', query='', movies=[])

    try:
        # First attempt with original query
        movies = search_movies_api(query)
        
        # If no results or very few results, try fuzzy matching
        if len(movies) < 3:
            # Get popular movies to use as reference set
            popular_movies = get_popular_movies()
            movie_titles = {movie['id']: movie['title'] for movie in popular_movies}
            
            # Perform fuzzy matching
            matches = process.extract(query, movie_titles.values(), limit=5, scorer=fuzz.token_sort_ratio)
            best_matches = [(movie_id, score) for title, score, movie_id in 
                           [(title, score, id) for (id, title), (_, score) in 
                            zip(movie_titles.items(), matches)] if score > 65]
            
            if best_matches:
                # Get detailed information for each match
                fuzzy_movies = []
                for movie_id, score in best_matches:
                    for movie in popular_movies:
                        if movie['id'] == movie_id:
                            fuzzy_movies.append(movie)
                            break
                
                # If we found better matches through fuzzy search
                if len(fuzzy_movies) > len(movies):
                    if len(movies) == 0:
                        flash(f'No exact matches found for "{query}". Showing similar results.', 'info')
                    else:
                        flash(f'Showing additional similar results for "{query}".', 'info')
                    
                    # Combine results, prioritizing exact matches
                    seen_ids = {movie['id'] for movie in movies}
                    for movie in fuzzy_movies:
                        if movie['id'] not in seen_ids:
                            movies.append(movie)
                            seen_ids.add(movie['id'])
        
        # Get genre information for display
        genres = get_genres()
        genre_map = {genre['id']: genre['name'] for genre in genres}
        
        return render_template('search_results.html', 
                              query=query, 
                              movies=movies, 
                              genre_map=genre_map)
    
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return render_template('search_results.html', query=query, movies=[])

def search_movies_api(query):
    """Search for movies using TMDB API"""
    api_key = "e508d75277a707b73ee8bb0698caa1fd"  # Your TMDB API key
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}&include_adult=false"
    
    response = requests.get(search_url)
    if response.status_code == 200:
        results = response.json().get('results', [])
        # Sort by popularity and limit results
        results.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        return results[:20]
    return []

def get_popular_movies():
    """Get popular movies from TMDB API for reference"""
    api_key = "e508d75277a707b73ee8bb0698caa1fd"
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}"
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('results', [])
    return []

def get_genres():
    """Get all movie genres from TMDB API"""
    api_key = "e508d75277a707b73ee8bb0698caa1fd"
    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={api_key}"
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('genres', [])
    return []




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
        # Delete associated data
        MovieComment.query.filter_by(user_id=user_id).delete()
        WatchedMovie.query.filter_by(user_id=user_id).delete()
        WishlistMovie.query.filter_by(user_id=user_id).delete()
        FriendRequest.query.filter((FriendRequest.sender_id == user_id) | (FriendRequest.receiver_id == user_id)).delete()
        Friendship.query.filter((Friendship.user_id1 == user_id) | (Friendship.user_id2 == user_id)).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        flash('User and all associated data deleted successfully.', 'success')
    else:
        flash('User not found.', 'danger')
    
    return redirect(url_for('main.admin'))

@main.route('/movie_desc/<int:movie_id>')
def movie_desc(movie_id):
    movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)).json()
    movie_credits = requests.get(TMDB_MOVIE_CREDITS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)).json()
    cast = movie_credits.get('cast', [])[:5]  # Get top 5 cast members
    
    # Get user's feedback if logged in
    user_feedback = None
    if 'user_id' in session:
        user_feedback = MovieComment.query.filter_by(
            user_id=session['user_id'],
            movie_id=movie_id
        ).first()
    
    # Get all reviews for this movie
    reviews = MovieComment.query.filter_by(movie_id=movie_id).order_by(MovieComment.timestamp.desc()).all()
    
    # Get usernames for reviews
    review_data = []
    for review in reviews:
        user = User.query.get(review.user_id)
        if user:
            review_data.append({
                'username': user.username,
                'feedback': review.feedback,
                'rating': review.rating,
                'likes': review.likes,
                'dislikes': review.dislikes,
                'timestamp': review.timestamp,
                'id': review.id
            })
    in_wishlist = False
    if 'user_id' in session:
        wishlist_item = WishlistMovie.query.filter_by(
            user_id=session['user_id'],
            movie_id=movie_id
        ).first()
        if wishlist_item:
            in_wishlist = True
    
    return render_template('movie_desc.html', movie=movie_details, cast=cast, user_feedback=user_feedback, reviews=review_data, in_wishlist=in_wishlist)
   


@main.route('/mylist')
def mylist():
    if 'user_id' not in session:
        flash('Please log in to view your lists.', 'danger')
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    
    # Get watched movies
    watched_db = WatchedMovie.query.filter_by(user_id=user_id).all()
    watched_movies = []
    
    for item in watched_db:
        movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=item.movie_id, api_key=TMDB_API_KEY)).json()
        movie_details['user_rating'] = item.rating
        movie_details['review'] = item.review
        movie_details['timestamp'] = item.timestamp
        watched_movies.append(movie_details)
    
    # Get wishlist movies
    wishlist_db = WishlistMovie.query.filter_by(user_id=user_id).all()
    wishlist_movies = []
    
    for item in wishlist_db:
        movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=item.movie_id, api_key=TMDB_API_KEY)).json()
        movie_details['timestamp'] = item.timestamp
        wishlist_movies.append(movie_details)
    
    return render_template('mylist.html', watched_movies=watched_movies, wishlist_movies=wishlist_movies)


    
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

@main.route('/submit_favorites', methods=['POST'])
def submit_favorites():
    data = request.get_json()
    genre_ids = data.get('genres', [])
    movie_ids = data.get('movies', [])
    
    if not movie_ids:
        return jsonify({'message': 'No movies selected'}), 400
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'User not logged in'}), 401
    
    try:
        # Fetch the user from the database
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Store the selected genres as a comma-separated string
        user.favorite_genre = ','.join(map(str, genre_ids))
        
        # Store the selected movies as a comma-separated string
        user.favorite_movies = ','.join(map(str, movie_ids))
        
        db.session.commit()
        
        return jsonify({'message': 'Favorites saved successfully'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error saving favorites: {str(e)}'}), 500

    
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
        return render_template('community.html', users=users, incoming_requests=incoming_requests, sent_requests=sent_requests, friends=friends, User=User)
    
    # Show the first 10 users when the page is opened directly
    users = User.query.filter(User.id != user.id).limit(10).all()
    return render_template('community.html', users=users, incoming_requests=incoming_requests, sent_requests=sent_requests, friends=friends, User=User)

@main.route('/send_friend_request/<receiver_id>', methods=['POST'])
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

@main.route('/accept_friend_request/<request_id>', methods=['POST'])
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

@main.route('/profile/<user_id>')
def view_profile(user_id):
    user = User.query.get(user_id)
    if user:
        return render_template('profile.html', user=user)
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('main.community'))

@main.route('/remove_friend/<friend_id>', methods=['POST'])
def remove_friend(friend_id):
    if 'user_id' not in session:
        flash('Please log in to manage your friends.', 'danger')
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    friendship = Friendship.query.filter(
        ((Friendship.user_id1 == user_id) & (Friendship.user_id2 == friend_id)) |
        ((Friendship.user_id1 == friend_id) & (Friendship.user_id2 == user_id))
    ).first()
    
    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        flash('Friend removed successfully.', 'success')
    else:
        flash('Friendship not found.', 'danger')
    
    return redirect(url_for('main.community'))

@main.route('/reject_friend_request/<request_id>', methods=['POST'])
def reject_friend_request(request_id):
    if 'user_id' not in session:
        flash('Please log in to reject friend requests.', 'danger')
        return redirect(url_for('main.login'))
    
    friend_request = FriendRequest.query.get(request_id)
    if friend_request and friend_request.receiver_id == session['user_id']:
        db.session.delete(friend_request)
        db.session.commit()
        flash('Friend request rejected.', 'success')
    else:
        flash('Invalid friend request.', 'danger')
    
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
    
@main.route('/movie/review/<int:review_id>/like', methods=['POST'])
def like_review(review_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to like reviews.'}), 401
    
    review = MovieComment.query.get_or_404(review_id)
    review.likes += 1
    db.session.commit()
    
    return jsonify({'success': True, 'likes': review.likes})

@main.route('/movie/review/<int:review_id>/dislike', methods=['POST'])
def dislike_review(review_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to dislike reviews.'}), 401
    
    review = MovieComment.query.get_or_404(review_id)
    review.dislikes += 1
    db.session.commit()
    
    return jsonify({'success': True, 'dislikes': review.dislikes})

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
    
@main.route('/rate_movie/<int:movie_id>', methods=['GET', 'POST'])
def rate_movie(movie_id):
    if 'user_id' not in session:
        flash('Please log in to rate a movie.', 'danger')
        return redirect(url_for('main.login'))
    
    movie_details_url = TMDB_MOVIE_DETAILS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)
    response = requests.get(movie_details_url)
    if response.status_code == 200:
        movie = response.json()
    else:
        movie = None
    
    if not movie:
        flash('Movie not found.', 'danger')
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        rating = request.form.get('rating')
        feedback = request.form.get('feedback')
        
        if not rating:
            flash('Please provide a rating.', 'danger')
            return render_template('rate_movie.html', movie=movie)
        
        # Save the rating and feedback to the database
        user_id = session['user_id']
        
        # Check if movie is in wishlist and remove it
        wishlist_item = WishlistMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        if wishlist_item:
            db.session.delete(wishlist_item)
        
        # Add to watched movies
        watched_movie = WatchedMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        if watched_movie:
            watched_movie.rating = rating
            watched_movie.review = feedback
        else:
            watched_movie = WatchedMovie(
                user_id=user_id, 
                movie_id=movie_id, 
                rating=rating, 
                review=feedback
            )
            db.session.add(watched_movie)
        
        # Also update the MovieComment for reviews display
        review = MovieComment.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        if review:
            review.rating = rating
            review.feedback = feedback
        else:
            review = MovieComment(
                user_id=user_id, 
                movie_id=movie_id, 
                rating=rating, 
                feedback=feedback
            )
            db.session.add(review)
        
        db.session.commit()
        flash('Your rating has been submitted and movie added to your watched list.', 'success')
        return redirect(url_for('main.movie_desc', movie_id=movie_id))
    
    return render_template('rate_movie.html', movie=movie)


@main.route('/remove_from_list/<list_type>/<int:movie_id>', methods=['POST'])
def remove_from_list(list_type, movie_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to manage your lists.'}), 401
    
    user_id = session['user_id']
    
    try:
        if list_type == 'watched':
            item = WatchedMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
            # Also delete the corresponding MovieComment
            comment = MovieComment.query.filter_by(user_id=user_id, movie_id=movie_id).first()
            if comment:
                db.session.delete(comment)
        else:
            item = WishlistMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        
        if item:
            db.session.delete(item)
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Movie not found in your list.'}), 404
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@main.route('/add_to_wishlist/<int:movie_id>', methods=['POST'])
def add_to_wishlist(movie_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to add to wishlist.'}), 401
    
    user_id = session['user_id']
    
    # Check if already in wishlist
    existing = WishlistMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
    if existing:
        return jsonify({'success': True, 'message': 'Movie already in wishlist'})
    
    # Add to wishlist
    wishlist_item = WishlistMovie(user_id=user_id, movie_id=movie_id)
    db.session.add(wishlist_item)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Added to wishlist'})




#naa istam

