import pytest
import json
from flask import session
from MRS15 import create_app, db
from MRS15.models import User, MovieComment, WishlistMovie, WatchedMovie, UserList, UserListMovie

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test_secret_key"
    })
    
    with app.app_context():
        db.create_all()
        
    yield app
    
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client):
    # Create a test user
    response = client.post('/signup', data={
        'username': 'testuser',
        'password': 'Password123'
    })
    
    # Login with test user
    client.post('/login', data={
        'username': 'testuser',
        'password': 'Password123'
    })
    
    return client

# Authentication Tests
def test_signup(client):
    """Test user registration with valid credentials"""
    response = client.post('/signup', data={
        'username': 'newuser',
        'password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'favorites' in response.data

def test_signup_existing_username(client, auth_client):
    """Test registration with existing username"""
    response = client.post('/signup', data={
        'username': 'testuser',
        'password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Username already taken' in response.data

def test_signup_invalid_password(client):
    """Test registration with invalid password"""
    response = client.post('/signup', data={
        'username': 'newuser',
        'password': 'short'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Password must be at least 6 characters' in response.data

def test_login_success(client, auth_client):
    """Test successful login"""
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Login successful' in response.data

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post('/login', data={
        'username': 'nonexistent',
        'password': 'wrongpass'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data

def test_logout(auth_client):
    """Test logout functionality"""
    response = auth_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    with auth_client.session_transaction() as sess:
        assert 'user_id' not in sess

# Search Tests
def test_search_empty_query(auth_client):
    """Test search with empty query"""
    response = auth_client.get('/search?query=')
    assert response.status_code == 200
    assert b'movies = []' in response.data

def test_search_valid_query(auth_client, mocker):
    """Test search with valid movie title"""
    # Mock the search_movies_api function
    mock_results = [
        {
            'id': 123,
            'title': 'Test Movie',
            'poster_path': '/test.jpg',
            'overview': 'Test overview',
            'release_date': '2025-01-01',
            'genre_ids': [28, 12]
        }
    ]
    mocker.patch('app.main.search_movies_api', return_value=mock_results)
    mocker.patch('app.main.get_genres', return_value=[{'id': 28, 'name': 'Action'}, {'id': 12, 'name': 'Adventure'}])
    
    response = auth_client.get('/search?query=test')
    assert response.status_code == 200
    assert b'Test Movie' in response.data

# Movie Details Tests
def test_movie_details(auth_client, mocker):
    """Test movie details page"""
    # Mock API responses
    mock_movie = {
        'id': 123,
        'title': 'Test Movie',
        'poster_path': '/test.jpg',
        'overview': 'Test overview',
        'release_date': '2025-01-01',
        'genres': [{'id': 28, 'name': 'Action'}]
    }
    mock_credits = {
        'cast': [
            {'id': 1, 'name': 'Actor 1', 'character': 'Character 1'},
            {'id': 2, 'name': 'Actor 2', 'character': 'Character 2'}
        ]
    }
    
    mocker.patch('requests.get', side_effect=[
        mocker.Mock(status_code=200, json=lambda: mock_movie),
        mocker.Mock(status_code=200, json=lambda: mock_credits)
    ])
    
    response = auth_client.get('/movie_desc/123')
    assert response.status_code == 200
    assert b'Test Movie' in response.data
    assert b'Actor 1' in response.data

# Wishlist Tests
def test_add_to_wishlist(auth_client, mocker):
    """Test adding movie to wishlist"""
    mocker.patch('app.models.WishlistMovie.query.filter_by', return_value=mocker.Mock(first=lambda: None))
    
    response = auth_client.post('/add_to_wishlist/123', 
                               data=json.dumps({}),
                               content_type='application/json')
    response_data = json.loads(response.data)
    assert response.status_code == 200
    assert response_data['success'] is True

def test_remove_from_wishlist(auth_client, app, mocker):
    """Test removing movie from wishlist"""
    with app.app_context():
        # Add a movie to wishlist first
        wishlist_item = WishlistMovie(user_id=1, movie_id=123)
        db.session.add(wishlist_item)
        db.session.commit()
        
        # Mock the query
        mock_query = mocker.Mock()
        mock_query.first.return_value = wishlist_item
        mocker.patch('app.models.WishlistMovie.query.filter_by', return_value=mock_query)
        
        response = auth_client.post('/remove_from_list/wishlist/123')
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert response_data['success'] is True

# Rating and Review Tests
def test_rate_movie(auth_client, mocker):
    """Test rating a movie"""
    # Mock movie details
    mock_movie = {
        'id': 123,
        'title': 'Test Movie',
        'poster_path': '/test.jpg',
        'overview': 'Test overview'
    }
    mocker.patch('requests.get', return_value=mocker.Mock(status_code=200, json=lambda: mock_movie))
    
    # Mock database queries
    mocker.patch('app.models.WishlistMovie.query.filter_by', return_value=mocker.Mock(first=lambda: None))
    mocker.patch('app.models.WatchedMovie.query.filter_by', return_value=mocker.Mock(first=lambda: None))
    mocker.patch('app.models.MovieComment.query.filter_by', return_value=mocker.Mock(first=lambda: None))
    
    response = auth_client.post('/rate_movie/123', data={
        'rating': '8',
        'feedback': 'Great movie!'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Your rating has been submitted' in response.data

# Custom Lists Tests
def test_create_list(auth_client):
    """Test creating a custom list"""
    response = auth_client.post('/create_list', 
                               data=json.dumps({'name': 'My Test List'}),
                               content_type='application/json')
    response_data = json.loads(response.data)
    assert response.status_code == 200
    assert response_data['success'] is True
    assert response_data['name'] == 'My Test List'

def test_add_to_list(auth_client, app, mocker):
    """Test adding a movie to a custom list"""
    with app.app_context():
        # Create a list first
        user_list = UserList(user_id=1, name='Test List')
        db.session.add(user_list)
        db.session.commit()
        
        # Mock the query
        mocker.patch('app.models.UserList.query.filter_by', 
                    return_value=mocker.Mock(first=lambda: user_list))
        mocker.patch('app.models.UserListMovie.query.filter_by', 
                    return_value=mocker.Mock(first=lambda: None))
        
        response = auth_client.post(f'/add_to_list/{user_list.id}/123')
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert response_data['success'] is True

# Admin Tests
def test_admin_login(client):
    """Test admin login with correct password"""
    response = client.post('/admin', data={
        'password': 'Vinay1505'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'admin.html' in response.data

def test_admin_login_invalid(client):
    """Test admin login with incorrect password"""
    response = client.post('/admin', data={
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid admin password' in response.data

# Friend System Tests
def test_send_friend_request(auth_client, app):
    """Test sending a friend request"""
    with app.app_context():
        # Create another user to send request to
        new_user = User(username='friend', password='Password123')
        db.session.add(new_user)
        db.session.commit()
        
        response = auth_client.post(f'/send_friend_request/{new_user.id}', 
                                  follow_redirects=True)
        assert response.status_code == 200
        assert b'Friend request sent' in response.data

def test_accept_friend_request(auth_client, app, mocker):
    """Test accepting a friend request"""
    with app.app_context():
        # Mock the friend request
        mock_request = mocker.Mock()
        mock_request.sender_id = 2
        mock_request.receiver_id = 1
        
        mocker.patch('app.models.FriendRequest.query.get', return_value=mock_request)
        
        response = auth_client.post('/accept_friend_request/1', follow_redirects=True)
        assert response.status_code == 200
        assert b'Friend request accepted' in response.data

# Recommendation Tests
def test_recommendations(auth_client, mocker):
    """Test recommendation system"""
    # Mock recommendation functions
    mock_recs = [(123, 0.9), (456, 0.8)]
    mocker.patch('app.main.get_content_based_recommendations', return_value=mock_recs)
    mocker.patch('app.main.get_collaborative_recommendations', return_value=mock_recs)
    mocker.patch('app.main.get_hybrid_recommendations', return_value=mock_recs)
    
    # Mock movie details
    mock_movie = {
        'id': 123,
        'title': 'Recommended Movie',
        'poster_path': '/rec.jpg',
        'overview': 'Recommended overview'
    }
    mocker.patch('requests.get', return_value=mocker.Mock(status_code=200, json=lambda: mock_movie))
    
    response = auth_client.get('/recommendations')
    assert response.status_code == 200
    assert b'Recommended Movie' in response.data