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

def fetch_and_store_genres():
    response = requests.get(TMDB_GENRES_URL)
    if response.status_code == 200:
        genres_data = response.json().get('genres', [])
        for genre in genres_data:
            # Check if the genre already exists in the database
            existing_genre = Genre.query.get(genre['id'])
            if not existing_genre:
                # Add new genre to the database
                new_genre = Genre(id=genre['id'], name=genre['name'])
                db.session.add(new_genre)
        db.session.commit()
        print("Genres fetched and stored successfully!")
    else:
        print(f"Failed to fetch genres. Status code: {response.status_code}")

@main.route('/fetch-genres', methods=['GET'])
def fetch_genres():
    fetch_and_store_genres()
    return "Genres fetched and stored successfully!"

@main.route('/favorites', methods=['GET', 'POST'])
def favorites():
    genres = Genre.query.all()
    print(genres)  # Debugging: Check if genres are fetched
    return render_template('favorites.html', genres=genres)
