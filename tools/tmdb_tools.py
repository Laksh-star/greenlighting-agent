"""
TMDB (The Movie Database) API tools for fetching movie and TV show data.
"""

import requests
from typing import Dict, Any, List, Optional
from config import TMDB_API_KEY, TMDB_BASE_URL
import time


class TMDBClient:
    """Client for interacting with TMDB API."""
    
    def __init__(self):
        self.api_key = TMDB_API_KEY
        self.base_url = TMDB_BASE_URL
        self.session = requests.Session()
        self.rate_limit_delay = 0.25  # 4 requests per second max
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Implement rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting."""
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params['api_key'] = self.api_key
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"TMDB API error: {str(e)}")
    
    def search_movie(self, query: str, year: Optional[int] = None) -> List[Dict]:
        """
        Search for movies by title.
        
        Args:
            query: Movie title to search for
            year: Optional year to filter results
            
        Returns:
            List of movie results
        """
        params = {'query': query}
        if year:
            params['year'] = year
        
        data = self._make_request('/search/movie', params)
        return data.get('results', [])
    
    def get_movie_details(self, movie_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a movie.
        
        Args:
            movie_id: TMDB movie ID
            
        Returns:
            Movie details including budget, revenue, runtime, etc.
        """
        return self._make_request(f'/movie/{movie_id}')
    
    def get_movie_credits(self, movie_id: int) -> Dict[str, Any]:
        """Get cast and crew information for a movie."""
        return self._make_request(f'/movie/{movie_id}/credits')
    
    def get_similar_movies(self, movie_id: int) -> List[Dict]:
        """Get movies similar to the specified movie."""
        data = self._make_request(f'/movie/{movie_id}/similar')
        return data.get('results', [])
    
    def get_genre_list(self) -> List[Dict]:
        """Get list of all movie genres."""
        data = self._make_request('/genre/movie/list')
        return data.get('genres', [])
    
    def discover_movies(
        self,
        genre_ids: Optional[List[int]] = None,
        year: Optional[int] = None,
        sort_by: str = 'popularity.desc'
    ) -> List[Dict]:
        """
        Discover movies based on filters.
        
        Args:
            genre_ids: List of genre IDs to filter by
            year: Release year
            sort_by: How to sort results
            
        Returns:
            List of discovered movies
        """
        params = {'sort_by': sort_by}
        
        if genre_ids:
            params['with_genres'] = ','.join(map(str, genre_ids))
        if year:
            params['year'] = year
        
        data = self._make_request('/discover/movie', params)
        return data.get('results', [])
    
    def get_trending_movies(self, time_window: str = 'week') -> List[Dict]:
        """
        Get trending movies.
        
        Args:
            time_window: 'day' or 'week'
            
        Returns:
            List of trending movies
        """
        data = self._make_request(f'/trending/movie/{time_window}')
        return data.get('results', [])
    
    def get_box_office_data(self, movie_id: int) -> Dict[str, Any]:
        """
        Get box office data for a movie.
        Returns budget and revenue information.
        """
        movie = self.get_movie_details(movie_id)
        return {
            'budget': movie.get('budget', 0),
            'revenue': movie.get('revenue', 0),
            'roi': self._calculate_roi(movie.get('budget', 0), movie.get('revenue', 0))
        }
    
    def _calculate_roi(self, budget: int, revenue: int) -> float:
        """Calculate ROI percentage."""
        if budget == 0:
            return 0.0
        return round(((revenue - budget) / budget) * 100, 2)
    
    def find_comparable_titles(
        self,
        genre: str,
        budget_range: tuple,
        year_range: tuple
    ) -> List[Dict]:
        """
        Find comparable titles based on genre, budget, and release year.
        
        Args:
            genre: Genre name
            budget_range: (min_budget, max_budget)
            year_range: (start_year, end_year)
            
        Returns:
            List of comparable movies with financial data
        """
        # This would require more sophisticated filtering
        # For now, we'll search by genre and year
        genres = self.get_genre_list()
        genre_id = next(
            (g['id'] for g in genres if g['name'].lower() == genre.lower()),
            None
        )
        
        if not genre_id:
            return []
        
        results = []
        for year in range(year_range[0], year_range[1] + 1):
            movies = self.discover_movies(genre_ids=[genre_id], year=year)
            for movie in movies[:5]:  # Top 5 per year
                details = self.get_movie_details(movie['id'])
                budget = details.get('budget', 0)
                
                # Filter by budget range
                if budget_range[0] <= budget <= budget_range[1]:
                    results.append({
                        'title': details['title'],
                        'year': details.get('release_date', '')[:4],
                        'budget': budget,
                        'revenue': details.get('revenue', 0),
                        'rating': details.get('vote_average', 0),
                        'popularity': details.get('popularity', 0)
                    })
        
        return sorted(results, key=lambda x: x['revenue'], reverse=True)[:10]


# Singleton instance
tmdb_client = TMDBClient()
