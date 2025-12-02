import requests
import json

def fetch_company_profile(self, ticker):
    """
    Fetches the company profile for a given ticker.

    Args:
        ticker (str): Stock ticker symbol.

    Returns:
        dict: A dictionary containing company profile information, or None if an error occurs.

    Raises:
        Exception: For API request failures or data parsing errors.
    """
    try:
        # Construct the API request URL.  Using a placeholder API for demonstration.
        api_url = f"https://example.com/api/company_profile?ticker={ticker}"  # Replace with actual API endpoint

        # Send the API request
        response = requests.get(api_url)

        # Raise an exception for bad status codes (e.g., 404, 500)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

        # Parse the JSON response
        data = response.json()

        # Basic validation of the data - check if the response is what we expect.
        if not isinstance(data, dict):
            raise Exception("Unexpected API response format: Expected a dictionary.")

        return data

    except requests.exceptions.RequestException as e:
        # Handle network errors (e.g., connection refused, timeout)
        print(f"Network error fetching company profile for {ticker}: {e}")
        return None
    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        print(f"Error decoding JSON response for {ticker}: {e}")
        return None
    except Exception as e:
        # Handle other unexpected errors
        print(f"Error fetching company profile for {ticker}: {e}")
        return None