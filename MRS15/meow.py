from MRS15.models import Genre
from MRS15 import db
import requests
from MRS15 import create_app

TMDB_GENRES_URL = "https://api.themoviedb.org/3/genre/movie/list?api_key=e508d75277a707b73ee8bb0698caa1fd&language=en-US"

def fetch_and_store_genres():
    response = requests.get(TMDB_GENRES_URL)
    if response.status_code == 200:
        genres_data = response.json().get('genres', [])
        for genre in genres_data:
            existing_genre = Genre.query.get(genre['id'])
            if not existing_genre:
                new_genre = Genre(id=genre['id'], name=genre['name'])
                db.session.add(new_genre)
        db.session.commit()
        print("Genres fetched and stored successfully!")
    else:
        print(f"Failed to fetch genres. Status code: {response.status_code}")

# Run the function
app = create_app()
with app.app_context():
    fetch_and_store_genres()