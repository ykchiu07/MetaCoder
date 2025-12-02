import requests
import json

def _make_api_request(self, api_endpoint, params=None):
    """
    Makes an API request and returns the response.

    Args:
        api_endpoint (str): The API endpoint URL.
        params (dict, optional): Dictionary of query parameters. Defaults to None.

    Returns:
        dict: The API response as a dictionary, or None if an error occurs.

    Raises:
        Exception: For API request failures or data parsing errors.
    """
    try:
        # Handle edge case: If api_endpoint is empty or None
        if not api_endpoint:
            raise Exception("API endpoint cannot be empty.")

        # Make the API request using the requests library
        response = requests.get(api_endpoint, params=params)

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx, 5xx)

        # Parse the JSON response
        try:
            data = response.json()
            return data
        except json.JSONDecodeError:
            # Handle cases where the response is not valid JSON
            print(f"Error decoding JSON response from {api_endpoint}. Response text: {response.text}") # Log the error
            return None

    except requests.exceptions.RequestException as e:
        # Handle network errors, timeout errors, and other request-related issues
        print(f"API request failed: {e}")  # Log the error
        return None
    except Exception as e:
        # Handle any other unexpected errors
        print(f"An unexpected error occurred: {e}")  # Log the error
        return None