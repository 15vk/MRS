function toggleNav() {
    var sidenav = document.getElementById("mySidenav");
    if (sidenav.style.width === "250px") {
        sidenav.style.width = "0";
    } else {
        sidenav.style.width = "250px";
    }
}

function searchMovie() {
    const query = document.getElementById('search').value.trim();
    if (query) {
        window.location.href = `/search?query=${encodeURIComponent(query)}`;
    } else {
        alert('Please enter a search query.');
    }
}

function search() {
    var query = document.getElementById("search").value;
    if (query.length < 3) {
        document.getElementById("search-results").innerHTML = "";
        return;
    }
    
    fetch(`/search?query=${query}`)
        .then(response => response.json())
        .then(data => {
            var results = document.getElementById("search-results");
            results.innerHTML = "";
            
            var movies = data.movies;
            var people = data.people;
            
            if (movies.length > 0) {
                var movieList = document.createElement("div");
                movieList.innerHTML = "<h3>Movies</h3>";
                movies.forEach(movie => {
                    var movieItem = document.createElement("div");
                    movieItem.className = "search-item";
                    movieItem.innerHTML = `<img src="https://image.tmdb.org/t/p/w500${movie.poster_path}" alt="${movie.title}"><p>${movie.title}</p>`;
                    movieList.appendChild(movieItem);
                });
                results.appendChild(movieList);
            }
            
            if (people.length > 0) {
                var peopleList = document.createElement("div");
                peopleList.innerHTML = "<h3>People</h3>";
                people.forEach(person => {
                    var personItem = document.createElement("div");
                    personItem.className = "search-item";
                    personItem.innerHTML = `<img src="https://image.tmdb.org/t/p/w500${person.profile_path}" alt="${person.name}"><p>${person.name}</p>`;
                    peopleList.appendChild(personItem);
                });
                results.appendChild(peopleList);
            }
        });
}

function openMovieDesc(movieId) {
    window.location.href = `/movie_desc/${movieId}`;
}

function displayMovies(movies) {
    const movieList = document.getElementById('movie-list');
    movieList.innerHTML = '';

    movies.forEach(movie => {
        const movieBox = document.createElement('div');
        movieBox.className = 'movie-box';
        movieBox.innerHTML = `
            <img class="movie-poster" src="https://image.tmdb.org/t/p/w500${movie.poster_path}" alt="${movie.title}">
            <div class="movie-info">
                <div class="movie-title">${movie.title}</div>
                <div class="movie-details">
                    <p>Release Date: ${movie.release_date}</p>
                    <p class="movie-rating">Rating: ⭐ ${movie.vote_average}/10</p>
                    <p>${movie.overview.substring(0, 100)}...</p>
                </div>
            </div>
        `;
        movieList.appendChild(movieBox);
    });
}
