import yfinance as yf

def fetch_current_price(self, ticker):
    """Fetches the current price of a stock.

    Args:
        ticker (str): Stock ticker symbol.

    Returns:
        float: The current price of the stock, or None if an error occurs.

    Raises:
        Exception: For API request failures or data parsing errors.
    """
    try:
        # Create a Ticker object for the given ticker symbol
        ticker_object = yf.Ticker(ticker)

        # Fetch historical data for the ticker (only need the latest price)
        history = ticker_object.history(period="1d")

        # Check if any data was returned
        if history.empty:
            print(f"No data found for ticker: {ticker}")
            return None

        # Extract the last closing price
        current_price = history['Close'].iloc[-1]

        # Return the current price
        return float(current_price)

    except Exception as e:
        # Handle potential errors during API request or data parsing
        print(f"Error fetching price for {ticker}: {e}")
        return None