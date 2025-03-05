import requests

def fetch_earnings(from_date, to_date):
    api_key = "nWe6FVkGfhspsF7BZijEJuzfSK9c63ky"
    # today = datetime.date.today().strftime('%Y-%m-%d')
    url = f"https://financialmodelingprep.com/stable/earnings-calendar?from={from_date}&to={to_date}&apikey={api_key}"

    response = requests.get(url)
    earnings = response.json()

    filtered_tickets = filter_tickets(earnings)

    return filtered_tickets

def filter_tickets(earnings):
    filtered_tickers = [entry for entry in earnings if '.' not in entry['symbol']]

    return filtered_tickers