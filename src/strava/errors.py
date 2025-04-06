"""Error handling utilities for Strava API"""
from typing import Union, Optional
import requests

class StravaApiError(Exception):
    """Custom exception for Strava API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)

def handle_strava_error(error: Union[requests.Response, Exception]) -> None:
    """Handle Strava API errors and raise appropriate exceptions"""
    if isinstance(error, requests.Response):
        status_code = error.status_code
        if status_code == 401:
            raise StravaApiError("Authentication error - check your tokens", status_code)
        elif status_code == 429:
            raise StravaApiError("Rate limit exceeded", status_code)
        else:
            raise StravaApiError(f"Strava API error: {error.text}", status_code)
    elif isinstance(error, requests.exceptions.RequestException):
        if error.response is not None:
            handle_strava_error(error.response)
        else:
            raise StravaApiError(f"Network error: {str(error)}")
    else:
        raise StravaApiError(f"Unexpected error: {str(error)}")