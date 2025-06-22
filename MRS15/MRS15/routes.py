from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from .models import User, MovieComment, FriendRequest, Friendship, Genre, WatchedMovie, WishlistMovie, UserListMovie, UserList, UserPreference, SavedList, SavedListMovie, Message, ReceivedList
from . import db
import requests
from fuzzywuzzy import fuzz,process
import re  # For password validation
from apscheduler.schedulers.background import BackgroundScheduler

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
            
            # Get personalized recommendations
            try:
                user_id = session['user_id']
    
                # Get personalized recommendations
                content_based_recs = get_content_based_recommendations(user_id)
                collaborative_recs = get_collaborative_recommendations(user_id)
                hybrid_recs = get_hybrid_recommendations(user_id)
                
                # Combine recommendations with weights
                final_recommendations = combine_recommendations(
                    content_based_recs, 
                    collaborative_recs, 
                    hybrid_recs
                )
                
                # Get movie details for the recommendations
                recommended_movies = []
                for movie_id, _ in final_recommendations[:12]:  # Get top 12 recommendations
                    try:
                        movie_details = requests.get(
                            TMDB_MOVIE_DETAILS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)
                        ).json()
                        recommended_movies.append(movie_details)
                    except:
                        continue
            except Exception as e:
                print(f"Error generating recommendations: {str(e)}")
                # Fallback to suggested movies if recommendations fail
                recommended_movies = requests.get(TMDB_SUGGESTED_URL).json().get('results', [])
            
            return render_template('index.html', 
                                  username=user.username, 
                                  trending_movies=trending_movies, 
                                  recommended_movies=recommended_movies)
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
   
@main.route('/get_user_lists', methods=['GET'])
def get_user_lists():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to view lists.'}), 401
    
    user_lists = UserList.query.filter_by(user_id=session['user_id']).all()
    lists_data = [{'id': list.id, 'name': list.name} for list in user_lists]
    
    return jsonify({'success': True, 'lists': lists_data})

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
    
    # Get custom lists with movies
    custom_lists = []
    user_lists = UserList.query.filter_by(user_id=user_id).all()
    
    for user_list in user_lists:
        list_movies = []
        for movie in user_list.movies:
            movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=movie.movie_id, api_key=TMDB_API_KEY)).json()
            list_movies.append(movie_details)
        
        custom_lists.append({
            'id': user_list.id,
            'name': user_list.name,
            'movies': list_movies,
            'is_saved': False
        })
    
    saved_lists = []
    saved_db = SavedList.query.filter_by(user_id=user_id).all()
    
    for saved_list in saved_db:
        # Get original list details
        original_list = UserList.query.get(saved_list.original_list_id)
        if not original_list:
            continue  # Skip corrupted entries
            
        original_owner = User.query.get(original_list.user_id)
        list_movies = []
        
        # Get movie details from original list
        original_movies = UserListMovie.query.filter_by(list_id=saved_list.original_list_id).all()
        for movie in original_movies:
            try:
                movie_details = requests.get(
                    TMDB_MOVIE_DETAILS_URL.format(movie_id=movie.movie_id, api_key=TMDB_API_KEY)
                ).json()
                list_movies.append(movie_details)
            except:
                continue

        saved_lists.append({
            'id': saved_list.id,
            'name': saved_list.name,
            'movies': list_movies,
            'original_owner': original_owner.username if original_owner else 'Deleted User',
            'original_list_id': saved_list.original_list_id
        })

    return render_template('mylist.html',
                        watched_movies=watched_movies,
                        wishlist_movies=wishlist_movies,
                        custom_lists=custom_lists,
                        saved_lists=saved_lists)
    
        

    
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

    # Get custom lists with movies
    custom_lists = []
    user_lists = UserList.query.filter_by(user_id=user_id).all()
    
    for user_list in user_lists:
        list_movies = []
        for movie in user_list.movies:
            movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=movie.movie_id, api_key=TMDB_API_KEY)).json()
            list_movies.append(movie_details)
        
        custom_lists.append({
            'id': user_list.id,
            'name': user_list.name,
            'movies': list_movies,
            'is_saved': False
        })

    return render_template('profile.html', user=user, genre_names=genre_names, custom_lists=custom_lists)

def fetch_and_store_genres():
    """Fetch genres from TMDB API and store them in the database"""
    try:
        # Fetch genres from TMDB API
        response = requests.get(TMDB_GENRES_URL)
        response.raise_for_status()
        
        genres_data = response.json().get('genres', [])
        
        # Store new genres
        for genre in genres_data:
            existing_genre = Genre.query.get(genre['id'])
            if not existing_genre:
                new_genre = Genre(
                    id=genre['id'],
                    name=genre['name']
                )
                db.session.add(new_genre)
        
        db.session.commit()
        return True
        
    except requests.RequestException as e:
        print(f"Error fetching genres from TMDB: {str(e)}")
        return False
    except Exception as e:
        print(f"Error storing genres in database: {str(e)}")
        db.session.rollback()
        return False

@main.route('/favorites', methods=['GET', 'POST'])
def favorites():
    if 'user_id' not in session:
        flash('Please log in to choose your favorite genres.', 'danger')
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)

    if request.method == 'POST':
        selected_genres = request.form.getlist('selected_genres')
        if selected_genres:
            genre_ids = [int(genre_id) for genre_id in selected_genres]
            user.favorite_genre = ','.join(map(str, genre_ids))
            db.session.commit()
            flash('Your favorite genres have been saved!', 'success')
        else:
            flash('No genres selected.', 'warning')
        return redirect(url_for('main.home'))

    # Fetch and store genres if needed
    genres = Genre.query.all()
    if not genres:
        if fetch_and_store_genres():
            genres = Genre.query.all()
        else:
            flash('Error fetching genres. Please try again later.', 'danger')
            return redirect(url_for('main.home'))

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
    
    # Get custom lists with movies
    custom_lists = []
    user_lists = UserList.query.filter_by(user_id=user_id).all()
    
    for user_list in user_lists:
        list_movies = []
        for movie in user_list.movies:
            movie_details = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id=movie.movie_id, api_key=TMDB_API_KEY)).json()
            list_movies.append(movie_details)
        
        custom_lists.append({
            'id': user_list.id,
            'name': user_list.name,
            'movies': list_movies,
            'is_saved': False
        })
    if user:
        return render_template('profile.html', user=user, custom_lists=custom_lists)
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

@main.route('/create_list', methods=['POST'])
def create_list():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to create a list.'}), 401
    
    data = request.get_json()
    list_name = data.get('name')
    movie_id = data.get('movie_id')
    
    if not list_name:
        return jsonify({'success': False, 'message': 'List name is required.'}), 400
    
    # Create new list
    new_list = UserList(user_id=session['user_id'], name=list_name)
    db.session.add(new_list)
    db.session.commit()
    
    # Add movie to the list if movie_id is provided
    if movie_id:
        list_movie = UserListMovie(list_id=new_list.id, movie_id=movie_id)
        db.session.add(list_movie)
        db.session.commit()
    
    return jsonify({'success': True, 'list_id': new_list.id, 'name': new_list.name})

@main.route('/add_to_list/<int:list_id>/<int:movie_id>', methods=['POST'])
def add_to_list(list_id, movie_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to add to list.'}), 401
    
    # Check if the list belongs to the user
    user_list = UserList.query.filter_by(id=list_id, user_id=session['user_id']).first()
    if not user_list:
        return jsonify({'success': False, 'message': 'List not found.'}), 404
    
    # Check if movie is already in the list
    existing = UserListMovie.query.filter_by(list_id=list_id, movie_id=movie_id).first()
    if existing:
        return jsonify({'success': True, 'message': 'Movie already in list'})
    
    # Add movie to list
    list_movie = UserListMovie(list_id=list_id, movie_id=movie_id)
    db.session.add(list_movie)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Added to list'})

@main.route('/get_user_lists/<int:list_id>/movies', methods=['GET'])
def get_list_movies(list_id):
    # Validate user session first
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    # Get parameters with validation
    try:
        user_id = int(request.args.get('user_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid user ID format'}), 400

    # Verify friendship or ownership
    current_user_id = session['user_id']
    is_owner = (current_user_id == user_id)
    is_friend = Friendship.query.filter(
        ((Friendship.user_id1 == current_user_id) & (Friendship.user_id2 == user_id)) |
        ((Friendship.user_id1 == user_id) & (Friendship.user_id2 == current_user_id))
    ).first()

    if not is_owner and not is_friend:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403

    # Get list with validation
    user_list = UserList.query.filter_by(id=list_id, user_id=user_id).first()
    if not user_list:
        return jsonify({'success': False, 'message': 'List not found'}), 404

    # Fetch movies with error handling
    movies = []
    for movie in user_list.movies:
        try:
            response = requests.get(
                f'https://api.themoviedb.org/3/movie/{movie.movie_id}',
                params={'api_key': TMDB_API_KEY},
                timeout=10  # Add timeout to prevent hanging
            )
            response.raise_for_status()
            movie_data = response.json()
            movies.append({
                'id': movie_data.get('id'),
                'title': movie_data.get('title'),
                'poster_path': movie_data.get('poster_path'),
                'overview': movie_data.get('overview')
            })
        except requests.exceptions.RequestException as e:
            print(f"Error fetching movie {movie.movie_id}: {str(e)}")
            continue

    return jsonify({
        'success': True,
        'movies': movies,
        'list_name': user_list.name
    })

@main.route('/recommendations')
def recommendations():
    if 'user_id' not in session:
        flash('Please log in to view recommendations.', 'danger')
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    
    # Get personalized recommendations
    content_based_recs = get_content_based_recommendations(user_id)
    collaborative_recs = get_collaborative_recommendations(user_id)
    hybrid_recs = get_hybrid_recommendations(user_id)
    
    # Combine recommendations with weights
    final_recommendations = combine_recommendations(
        content_based_recs, 
        collaborative_recs, 
        hybrid_recs
    )
    
    # Get movie details for the recommendations
    recommended_movies = []
    for movie_id, _ in final_recommendations[:12]:  # Get top 12 recommendations
        try:
            movie_details = requests.get(
                TMDB_MOVIE_DETAILS_URL.format(movie_id=movie_id, api_key=TMDB_API_KEY)
            ).json()
            recommended_movies.append(movie_details)
        except:
            continue
    
    return render_template('recommendations.html', recommended_movies=recommended_movies)

@main.route('/delete_list/<int:list_id>', methods=['POST'])
def delete_list(list_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to delete lists.'}), 401
    
    user_id = session['user_id']
    
    # Check if it's a user list or saved list
    user_list = UserList.query.filter_by(id=list_id, user_id=user_id).first()
    saved_list = None
    
    if not user_list:
        saved_list = SavedList.query.filter_by(id=list_id, user_id=user_id).first()
        if not saved_list:
            return jsonify({'success': False, 'message': 'List not found.'}), 404
    
    try:
        if user_list:
            # Delete all movies in the list
            UserListMovie.query.filter_by(list_id=list_id).delete()
            # Delete the list
            db.session.delete(user_list)
        else:
            # Delete all movies in the saved list
            SavedListMovie.query.filter_by(saved_list_id=list_id).delete()
            # Delete the saved list
            db.session.delete(saved_list)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'List deleted successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500




#naa istam
def get_content_based_recommendations(user_id, n=20):
    """Get content-based recommendations based on user's favorite genres and movies"""
    user = User.query.get(user_id)
    
    # Get user's favorite genres
    favorite_genres = []
    if user.favorite_genre:
        favorite_genres = [int(genre_id) for genre_id in user.favorite_genre.split(',')]
    
    # Get user's highly rated movies
    watched_movies = WatchedMovie.query.filter_by(user_id=user_id).all()
    
    # If user has no watched movies or favorite genres, return popular movies
    if not watched_movies and not favorite_genres:
        response = requests.get(TMDB_SUGGESTED_URL)
        if response.status_code == 200:
            popular_movies = [(movie['id'], movie['popularity']) 
                             for movie in response.json().get('results', [])]
            return popular_movies[:n]
        return []
    
    # Get recommendations based on genres
    genre_recs = []
    for genre_id in favorite_genres:
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_genres={genre_id}&sort_by=popularity.desc"
        response = requests.get(url)
        if response.status_code == 200:
            movies = response.json().get('results', [])
            genre_recs.extend([(movie['id'], movie['vote_average'] * 0.5 + movie['popularity'] * 0.5) 
                              for movie in movies])
    
    # Get recommendations based on watched movies
    similar_recs = []
    for watched in watched_movies:
        if watched.rating >= 7.0:  # Only consider highly rated movies
            url = f"https://api.themoviedb.org/3/movie/{watched.movie_id}/recommendations?api_key={TMDB_API_KEY}"
            response = requests.get(url)
            if response.status_code == 200:
                movies = response.json().get('results', [])
                # Weight by user rating
                weight = watched.rating / 10.0
                similar_recs.extend([(movie['id'], movie['vote_average'] * weight) 
                                    for movie in movies])
    
    # Combine and remove duplicates
    all_recs = {}
    for movie_id, score in genre_recs + similar_recs:
        if movie_id not in all_recs:
            all_recs[movie_id] = score
        else:
            all_recs[movie_id] = max(all_recs[movie_id], score)
    
    # Sort by score
    sorted_recs = sorted(all_recs.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_recs[:n]

def get_collaborative_recommendations(user_id, n=20):
    """Get collaborative filtering recommendations based on similar users"""
    # Get all users who have watched at least one movie that the current user has watched
    user = User.query.get(user_id)
    watched_movie_ids = [movie.movie_id for movie in user.watched_movies]
    
    if not watched_movie_ids:
        return []
    
    # Find similar users
    similar_users = {}
    for movie_id in watched_movie_ids:
        watchers = WatchedMovie.query.filter_by(movie_id=movie_id).all()
        for watcher in watchers:
            if watcher.user_id != user_id:
                if watcher.user_id not in similar_users:
                    similar_users[watcher.user_id] = 1
                else:
                    similar_users[watcher.user_id] += 1
    
    # Sort users by similarity (number of common movies)
    similar_users = sorted(similar_users.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Get movies liked by similar users
    recommendations = {}
    for similar_user_id, similarity in similar_users:
        similar_user = User.query.get(similar_user_id)
        for watched in similar_user.watched_movies:
            if watched.movie_id not in watched_movie_ids and watched.rating >= 7.0:
                if watched.movie_id not in recommendations:
                    recommendations[watched.movie_id] = watched.rating * similarity
                else:
                    recommendations[watched.movie_id] += watched.rating * similarity
    
    # Sort by weighted rating
    sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_recs[:n]

def get_hybrid_recommendations(user_id, n=20):
    """Combine content-based and collaborative filtering with user behavior analysis"""
    # Get basic recommendations
    content_recs = get_content_based_recommendations(user_id, n=n)
    collab_recs = get_collaborative_recommendations(user_id, n=n)
    
    # Analyze user behavior patterns
    user = User.query.get(user_id)
    watched_movies = user.watched_movies.all()
    
    # Calculate average rating and genres distribution
    if watched_movies:
        avg_rating = sum(movie.rating for movie in watched_movies) / len(watched_movies)
        
        # Get genre distribution
        genre_counts = {}
        for movie in watched_movies:
            movie_details = requests.get(
                TMDB_MOVIE_DETAILS_URL.format(movie_id=movie.movie_id, api_key=TMDB_API_KEY)
            ).json()
            for genre in movie_details.get('genres', []):
                genre_id = genre['id']
                if genre_id not in genre_counts:
                    genre_counts[genre_id] = 1
                else:
                    genre_counts[genre_id] += 1
        
        # Get top genres
        top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top_genre_ids = [genre_id for genre_id, _ in top_genres]
        
        # Get trending movies in top genres
        trending_in_genres = []
        for genre_id in top_genre_ids:
            url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_genres={genre_id}&sort_by=popularity.desc"
            response = requests.get(url)
            if response.status_code == 200:
                movies = response.json().get('results', [])
                trending_in_genres.extend([(movie['id'], movie['popularity']) for movie in movies])
    else:
        trending_in_genres = []
    
    # Combine all recommendations
    all_recs = {}
    
    # Add content-based with weight 0.4
    for movie_id, score in content_recs:
        all_recs[movie_id] = score * 0.4
    
    # Add collaborative with weight 0.4
    for movie_id, score in collab_recs:
        if movie_id in all_recs:
            all_recs[movie_id] += score * 0.4
        else:
            all_recs[movie_id] = score * 0.4
    
    # Add trending in genres with weight 0.2
    for movie_id, score in trending_in_genres:
        if movie_id in all_recs:
            all_recs[movie_id] += score * 0.2
        else:
            all_recs[movie_id] = score * 0.2
    
    # Sort by score
    sorted_recs = sorted(all_recs.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_recs[:n]

def combine_recommendations(content_recs, collab_recs, hybrid_recs, n=12):
    """Combine different recommendation types with diversity considerations"""
    # Start with hybrid recommendations as they're already combined
    final_recs = hybrid_recs[:6]
    
    # Add some content-based recommendations for diversity
    for movie_id, score in content_recs:
        if len(final_recs) >= n:
            break
        if movie_id not in [rec[0] for rec in final_recs]:
            final_recs.append((movie_id, score))
    
    # Add some collaborative recommendations for diversity
    for movie_id, score in collab_recs:
        if len(final_recs) >= n:
            break
        if movie_id not in [rec[0] for rec in final_recs]:
            final_recs.append((movie_id, score))
    
    # Sort by score
    final_recs = sorted(final_recs, key=lambda x: x[1], reverse=True)
    
    return final_recs[:n]

# from datetime import datetime
# from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
# # Register custom template filters
# @main.app_template_filter('time_format')
# def time_format(timestamp):
#     """Format timestamp for chat messages"""
#     if isinstance(timestamp, str):
#         timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
#     return timestamp.strftime('%I:%M %p')  # Returns time in 12-hour format with AM/PM

# @main.app_template_filter('time_ago')
# def time_ago(timestamp):
#     """Convert timestamp to '2 minutes ago' format"""
#     if not timestamp:
#         return 'Never'
    
#     if isinstance(timestamp, str):
#         timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    
#     now = datetime.now()
#     diff = now - timestamp
    
#     seconds = diff.total_seconds()
#     if seconds < 60:
#         return 'Just now'
#     elif seconds < 3600:
#         minutes = int(seconds / 60)
#         return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
#     elif seconds < 86400:
#         hours = int(seconds / 3600)
#         return f'{hours} hour{"s" if hours != 1 else ""} ago'
#     else:
#         days = int(seconds / 86400)
#         return f'{days} day{"s" if days != 1 else ""} ago'


# # Main Chat Interface
# @main.route('/friends_chat')
# def friends_chat():
#     if 'user_id' not in session:
#         flash('Please log in to access chat', 'danger')
#         return redirect(url_for('main.login'))
    
#     user_id = session['user_id']
#     user = User.query.get(user_id)
    
#     # Get friends list
#     friends = [friendship.user_id1 if friendship.user_id1 != user.id else friendship.user_id2 
#                for friendship in user.friends.all()]
#     friends_list = User.query.filter(User.id.in_(friends)).all()
    
#     # Get last messages for each friend
#     friends_with_last_message = []
#     for friend in friends_list:
#         last_message = Message.query.filter(
#             ((Message.sender_id == user_id) & (Message.receiver_id == friend.id)) |
#             ((Message.sender_id == friend.id) & (Message.receiver_id == user_id))
#         ).order_by(Message.timestamp.desc()).first()
        
#         friends_with_last_message.append({
#             'friend': friend,
#             'last_message': last_message.content if last_message else None,
#             'timestamp': last_message.timestamp if last_message else None,
#             'unread': Message.query.filter_by(
#                 sender_id=friend.id,
#                 receiver_id=user_id,
#                 is_read=False
#             ).count()
#         })
    
#     return render_template('friends_chat.html',  friends=friends_with_last_message, user=user, active_friend=None)  # Add active_friend=None here


# # Individual Chat Session
# @main.route('/chat/<int:friend_id>')
# def chat(friend_id):
#     if 'user_id' not in session:
#         flash('Please log in to chat.', 'danger')
#         return redirect(url_for('main.login'))
    
#     user_id = session['user_id']
    
#     # Validate friendship
#     friendship = Friendship.query.filter(
#         ((Friendship.user_id1 == user_id) & (Friendship.user_id2 == friend_id)) |
#         ((Friendship.user_id1 == friend_id) & (Friendship.user_id2 == user_id))
#     ).first()
    
#     if not friendship:
#         flash('You are not friends with this user', 'danger')
#         return redirect(url_for('main.friends_chat'))
    
#     # Get chat history
#     messages = Message.query.filter(
#         ((Message.sender_id == user_id) & (Message.receiver_id == friend_id)) |
#         ((Message.sender_id == friend_id) & (Message.receiver_id == user_id))
#     ).order_by(Message.timestamp.asc()).limit(100).all()
    
#     # Mark messages as read
#     Message.query.filter_by(
#         sender_id=friend_id,
#         receiver_id=user_id,
#         is_read=False
#     ).update({'is_read': True})
#     db.session.commit()
    
#     return render_template('chat_window.html',  messages=messages, friend=User.query.get(friend_id))

# @main.route('/send_message/<int:friend_id>', methods=['POST'])
# def send_message(friend_id):
#     if 'user_id' not in session:
#         return jsonify({'success': False, 'message': 'Please log in to send messages.'}), 401
    
#     user_id = session['user_id']
#     data = request.get_json()
    
#     # Validate friendship
#     friendship = Friendship.query.filter(
#         ((Friendship.user_id1 == user_id) & (Friendship.user_id2 == friend_id)) |
#         ((Friendship.user_id1 == friend_id) & (Friendship.user_id2 == user_id))
#     ).first()
    
#     if not friendship:
#         return jsonify({'success': False, 'message': 'You are not friends with this user.'}), 403
    
#     # Save message to database
#     new_message = Message(
#         sender_id=user_id,
#         receiver_id=friend_id,
#         content=data.get('content', ''),
#         shared_list_id=data.get('shared_list_id', None)
#     )
    
#     db.session.add(new_message)
#     db.session.commit()
    
#     return jsonify({'success': True, 'message': 'Message sent successfully!'})

# @main.route('/get_messages/<int:friend_id>', methods=['GET'])
# def get_messages(friend_id):
#     if 'user_id' not in session:
#         return jsonify({'success': False, 'message': 'Please log in to view messages.'}), 401

#     user_id = session['user_id']
#     last_message_id = request.args.get('last_message', 0, type=int)

#     # Fetch new messages after the last_message ID
#     new_messages = Message.query.filter(
#         ((Message.sender_id == user_id) & (Message.receiver_id == friend_id)) |
#         ((Message.sender_id == friend_id) & (Message.receiver_id == user_id)),
#         Message.id > last_message_id
#     ).order_by(Message.timestamp.asc()).all()

#     # Mark messages as read
#     unread_ids = [msg.id for msg in new_messages if msg.sender_id == friend_id]
#     if unread_ids:
#         Message.query.filter(Message.id.in_(unread_ids)).update({'is_read': True})
#         db.session.commit()

#     return jsonify({
#         'success': True,
#         'messages': [
#             {
#                 'id': msg.id,
#                 'content': msg.content,
#                 'timestamp': msg.timestamp.strftime('%H:%M'),
#                 'sender_id': msg.sender_id,
#                 'is_read': msg.is_read
#             } for msg in new_messages
#         ]
#     })

@main.route('/get_friends')
def get_friends():
    if 'user_id' not in session:
        return jsonify([])
    
    user = User.query.get(session['user_id'])
    friends = [friendship.user_id1 if friendship.user_id1 != user.id else friendship.user_id2 
               for friendship in user.friends.all()]
    friends_list = User.query.filter(User.id.in_(friends)).all()
    
    return jsonify([{'id': f.id, 'username': f.username} for f in friends_list])

@main.route('/received_lists')
def received_lists():
    if 'user_id' not in session:
        flash('Please log in to view received lists.', 'danger')
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    received_lists = ReceivedList.query.filter_by(receiver_id=user_id).all()

    formatted_lists = []
    for r_list in received_lists:
        original_list = UserList.query.get(r_list.original_list_id)
        sender = User.query.get(r_list.sender_id)
        movies = []
        for movie in UserListMovie.query.filter_by(list_id=r_list.original_list_id).all():
            try:
                movie_details = requests.get(
                    TMDB_MOVIE_DETAILS_URL.format(movie_id=movie.movie_id, api_key=TMDB_API_KEY)
                ).json()
                movies.append({
                    'id': movie.movie_id,
                    'title': movie_details.get('title', ''),
                    'poster_path': movie_details.get('poster_path', '/images/poster_placeholder.jpg')
                })
            except:
                continue

        formatted_lists.append({
            'id': r_list.id,
            'name': r_list.name,
            'sender': sender.username if sender else 'Unknown',
            'timestamp': r_list.timestamp.strftime('%B %d, %Y'),
            'movies': movies
        })

    return render_template('received_lists.html', received_lists=formatted_lists)


@main.route('/save_received_list/<int:list_id>', methods=['POST'])
def save_received_list(list_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to save lists.'}), 401

    user_id = session['user_id']
    received_list = ReceivedList.query.get(list_id)

    if not received_list or received_list.receiver_id != user_id:
        return jsonify({'success': False, 'message': 'List not found or unauthorized.'}), 404

    try:
        # Save the list to the user's saved lists
        saved_list = SavedList(
            user_id=user_id,
            original_list_id=received_list.original_list_id,
            original_owner_id=received_list.sender_id,
            name=received_list.name
        )
        db.session.add(saved_list)
        db.session.commit()

        # Copy movies from original list
        original_movies = UserListMovie.query.filter_by(list_id=received_list.original_list_id).all()
        for movie in original_movies:
            db.session.add(SavedListMovie(
                saved_list_id=saved_list.id,
                movie_id=movie.movie_id
            ))
        db.session.commit()

        return jsonify({'success': True, 'message': 'List saved successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/delete_received_list/<int:list_id>', methods=['POST'])
def delete_received_list(list_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to delete lists.'}), 401

    user_id = session['user_id']
    received_list = ReceivedList.query.get(list_id)

    if not received_list or received_list.receiver_id != user_id:
        return jsonify({'success': False, 'message': 'List not found or unauthorized.'}), 404

    try:
        db.session.delete(received_list)
        db.session.commit()
        return jsonify({'success': True, 'message': 'List deleted successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/share_list/<int:list_id>', methods=['POST'])
def share_list(list_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    data = request.get_json()
    friend_id = data.get('friend_id')
    
    if not friend_id:
        return jsonify({'success': False, 'message': 'Friend ID required'}), 400

    user_id = session['user_id']
    
    # Validate list ownership
    user_list = UserList.query.filter_by(id=list_id, user_id=user_id).first()
    if not user_list:
        return jsonify({'success': False, 'message': 'List not found'}), 404
    
    # Validate friendship
    friendship = Friendship.query.filter(
        ((Friendship.user_id1 == user_id) & (Friendship.user_id2 == friend_id)) |
        ((Friendship.user_id1 == friend_id) & (Friendship.user_id2 == user_id))
    ).first()
    
    if not friendship:
        return jsonify({'success': False, 'message': 'Not friends with user'}), 403

    try:
        received_list = ReceivedList(
            sender_id=user_id,
            receiver_id=friend_id,
            original_list_id=list_id,
            name=user_list.name
        )
        db.session.add(received_list)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Shared "{user_list.name}"'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

