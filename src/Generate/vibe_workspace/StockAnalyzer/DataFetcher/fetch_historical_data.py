import yfinance as yf
from datetime import datetime

def fetch_historical_data(self, ticker: str, start_date: str, end_date: str) -> list:
    """Fetches historical stock data for a given ticker and date range.

    Args:
        ticker (str): Stock ticker symbol.
        start_date (str): Start date (YYYY-MM-DD).
        end_date (str): End date (YYYY-MM-DD).

    Returns:
        list: A list of historical data points (e.g., list of dictionaries), or None if an error occurs.

    Raises:
        ValueError: If start_date or end_date are invalid.
        Exception: For API request failures or data parsing errors.
    """
    try:
        # Validate date formats
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.")

    try:
        # Fetch data using yfinance
        data = yf.download(ticker, start=start_date, end=end_date)

        # Convert data to a list of dictionaries for easier handling
        data_list = []
        for index, row in data.iterrows():
            data_list.append(row.to_dict())

        return data_list

    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")  # Log the error
        return None  # Return None to indicate failure