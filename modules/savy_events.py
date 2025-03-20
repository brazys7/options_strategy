import requests
from datetime import datetime, timedelta


def fetch_earnings(from_date):
    to_date = datetime.strptime(from_date, "%Y-%m-%d").date() + timedelta(days=1)
    url = f"https://api.savvytrader.com/pricing/assets/earnings/calendar/daily?start={from_date}&end={to_date}"

    response = requests.get(url)
    earnings = response.json()

    after_close = [
        entry
        for entry in earnings.get(from_date, [])
        if datetime.strptime(entry["earningsTime"], "%H:%M:%S").time()
        >= datetime.strptime("15:00:00", "%H:%M:%S").time()
    ]

    before_open = [
        entry
        for entry in earnings.get(to_date.strftime("%Y-%m-%d"), [])
        if datetime.strptime(entry["earningsTime"], "%H:%M:%S").time()
        < datetime.strptime("15:00:00", "%H:%M:%S").time()
    ]

    response = after_close + before_open

    # filter by marketCap
    response = [entry for entry in response if entry.get("marketCap", 0) > 1000000000]

    return response
