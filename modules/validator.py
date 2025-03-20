import yfinance as yf
from datetime import datetime, timedelta
from scipy.interpolate import interp1d
import numpy as np
import pandas as pd


def filter_dates(dates):
    today = datetime.today().date()
    cutoff_date = today + timedelta(days=45)

    sorted_dates = sorted(datetime.strptime(date, "%Y-%m-%d").date() for date in dates)

    arr = []
    for i, date in enumerate(sorted_dates):
        if date >= cutoff_date:
            arr = [d.strftime("%Y-%m-%d") for d in sorted_dates[: i + 1]]
            break

    if len(arr) > 0:
        if arr[0] == today.strftime("%Y-%m-%d"):
            return arr[1:]
        return arr

    raise ValueError("No date 45 days or more in the future found.")


def yang_zhang(price_data, window=30, trading_periods=252, return_last_only=True):
    log_ho = (price_data["High"] / price_data["Open"]).apply(np.log)
    log_lo = (price_data["Low"] / price_data["Open"]).apply(np.log)
    log_co = (price_data["Close"] / price_data["Open"]).apply(np.log)

    log_oc = (price_data["Open"] / price_data["Close"].shift(1)).apply(np.log)
    log_oc_sq = log_oc**2

    log_cc = (price_data["Close"] / price_data["Close"].shift(1)).apply(np.log)
    log_cc_sq = log_cc**2

    rs = log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)

    close_vol = log_cc_sq.rolling(window=window, center=False).sum() * (
        1.0 / (window - 1.0)
    )

    open_vol = log_oc_sq.rolling(window=window, center=False).sum() * (
        1.0 / (window - 1.0)
    )

    window_rs = rs.rolling(window=window, center=False).sum() * (1.0 / (window - 1.0))

    k = 0.34 / (1.34 + ((window + 1) / (window - 1)))
    result = (open_vol + k * close_vol + (1 - k) * window_rs).apply(np.sqrt) * np.sqrt(
        trading_periods
    )

    if return_last_only:
        return result.iloc[-1]
    else:
        return result.dropna()


def build_term_structure(days, ivs):
    days = np.array(days)
    ivs = np.array(ivs)

    sort_idx = days.argsort()
    days = days[sort_idx]
    ivs = ivs[sort_idx]

    spline = interp1d(days, ivs, kind="linear", fill_value="extrapolate")

    def term_spline(dte):
        if dte < days[0]:
            return ivs[0]
        elif dte > days[-1]:
            return ivs[-1]
        else:
            return float(spline(dte))

    return term_spline


def get_current_price(ticker):
    todays_data = ticker.history(period="1d")
    return todays_data["Close"].iloc[0]


def determine_calendar_strategy(call_iv, put_iv, ts_slope_0_45, iv30_rv30, vix_level):
    if put_iv - call_iv > 0.02:
        strategy = "P"
    elif call_iv - put_iv > 0.02:
        strategy = "C"
    else:
        strategy = "N/A"

    if ts_slope_0_45 < -0.004 or iv30_rv30 > 1.5:
        longer_expiration = 60
    elif ts_slope_0_45 < -0.002:
        longer_expiration = 45
    else:
        longer_expiration = 30

    if vix_level > 25 and longer_expiration > 30:
        longer_expiration = 30

    return strategy, longer_expiration


def check_iv_percentile(stock):
    iv_history = stock.history(period="1y")["Close"].rolling(30).std().dropna()
    current_iv30 = (
        stock.option_chain(stock.options[-1]).calls["impliedVolatility"].mean()
    )
    iv_percentile = (current_iv30 - iv_history.min()) / (
        iv_history.max() - iv_history.min()
    )
    return round(iv_percentile * 100, 2)


def get_closest_trading_day(date, price_history, direction="before"):
    """
    Finds the closest trading day before or after the given date in price_history.

    Parameters:
        date (pd.Timestamp): The date to search from.
        price_history (pd.Series): The stock's price history with dates as index.
        direction (str): "before" to get the last available date before, "after" for the next available date.

    Returns:
        pd.Timestamp or None: The closest valid trading day, or None if not found.
    """
    date = (
        pd.Timestamp(date).tz_localize(None).normalize()
    )  # Convert to timezone-naive & remove time

    if direction == "before":
        while date not in price_history.index and date >= price_history.index.min():
            date -= timedelta(days=1)  # Move backward to find a valid trading day
    else:  # direction == "after"
        while date not in price_history.index and date <= price_history.index.max():
            date += timedelta(days=1)  # Move forward to find a valid trading day

    return (
        date if date in price_history.index else None
    )  # Return None if no valid date is found


def compare_expected_move_to_past(stock, expected_move):
    """
    Compares expected earnings move to past actual earnings moves.
    Extracts earnings dates from stock.earnings_dates and adjusts pre/post-earnings days
    based on whether earnings were Before Market Open (BMO) or After Market Close (AMC).
    """
    try:
        earnings_data = stock.earnings_dates  # Extract full earnings data
        earnings_dates = earnings_data.index.tolist()  # Get earnings date index
    except AttributeError:
        return 1.5  # If no earnings data, return high value to avoid false signals

    # Ensure price history includes enough past data (extend period to 5y to avoid missing earnings)
    price_history = stock.history(period="2y")["Close"]
    # price_history.index = price_history.index.tz_localize(
    #     None
    # )  # Convert index to timezone-naive

    if price_history.index.tzinfo is not None:
        price_history.index = price_history.index.tz_localize(None)

    past_moves = {}

    for earnings_date in earnings_dates:
        # First, make sure we're working with a timezone-aware timestamp
        if earnings_date.tzinfo is None:
            # If timestamp has no timezone, assume it's in NY time
            earnings_date = earnings_date.tz_localize("America/New_York")

        # Convert to your local timezone if needed
        # local_tz = datetime.now().astimezone().tzinfo
        # earnings_local = earnings_date.astimezone(local_tz)

        # Determine if it's BMO (before market open) or AMC (after market close)
        # BMO is typically before 9:30 AM ET, AMC is after 4:00 PM ET
        ny_time = earnings_date.tz_convert("America/New_York").time()
        is_amc = ny_time.hour >= 16  # After 4 PM ET
        is_bmo = ny_time.hour < 9 or (
            ny_time.hour == 9 and ny_time.minute < 30
        )  # Before 9:30 AM ET

        # For timezone-naive comparison with price history
        earnings_naive = earnings_date.tz_localize(None)
        earnings_date_only = earnings_naive.normalize() + timedelta(
            1
        )  # Date only, no time

        max_history = price_history.index.max()
        # Skip future earnings (no price data available)
        if earnings_date_only >= max_history - timedelta(days=1):
            continue  # Skip this earnings date

        # Determine pre and post earnings dates based on BMO/AMC
        if is_amc:
            # For AMC (after market close), use current day as pre and next day as post
            pre_earnings = earnings_date_only
            post_earnings = earnings_date_only + timedelta(days=1)
        elif is_bmo:
            # For BMO (before market open), use previous day as pre and current day as post
            pre_earnings = earnings_date_only - timedelta(days=1)
            post_earnings = earnings_date_only
        else:
            # If we can't determine, default to using current day as pre and next day as post
            pre_earnings = earnings_date_only
            post_earnings = earnings_date_only + timedelta(days=1)

        # Get closest trading days
        pre_earnings_date = get_closest_trading_day(
            pre_earnings, price_history, "before"
        )
        post_earnings_date = get_closest_trading_day(
            post_earnings, price_history, "after"
        )

        # Calculate move if both dates exist
        if pre_earnings_date is not None and post_earnings_date is not None:
            pre_earnings_close = price_history.loc[pre_earnings_date]
            post_earnings_close = price_history.loc[post_earnings_date]
            move = (
                abs((post_earnings_close - pre_earnings_close) / pre_earnings_close)
                * 100
            )
            # past_moves.append(move)
            past_moves[pre_earnings_date.strftime("%Y-%m-%d")] = move

    # Return average move or default value if no past moves
    return past_moves


# Abejoju logika
def determine_trade_type(iv_percentile, iv30_rv30, mispriced_expected_move):
    if iv_percentile < 25 and iv30_rv30 < 1.0 and mispriced_expected_move < 0.8:
        return "Long Volatility (Buy Pre-Earnings IV, Expect IV Rise)"
    else:
        return "Short Volatility (Standard IV Crush Calendar Spread)"


def compute_recommendation(ticker, vix):
    try:
        ticker = ticker.strip().upper()
        if not ticker:
            return "No stock symbol provided."

        try:
            stock = yf.Ticker(ticker)
            if len(stock.options) == 0:
                raise KeyError()
        except KeyError:
            return f"Error: No options found for stock symbol '{ticker}'."

        exp_dates = list(stock.options)
        try:
            exp_dates = filter_dates(exp_dates)
        except:
            return "Error: Not enough option data."

        options_chains = {}
        for exp_date in exp_dates:
            options_chains[exp_date] = stock.option_chain(exp_date)

        try:
            underlying_price = get_current_price(stock)
            if underlying_price is None:
                raise ValueError("No market price found.")
        except Exception:
            return "Error: Unable to retrieve underlying stock price."

        atm_iv = {}
        straddle = None
        i = 0
        for exp_date, chain in options_chains.items():
            calls = chain.calls
            puts = chain.puts

            if calls.empty or puts.empty:
                continue

            call_diffs = (calls["strike"] - underlying_price).abs()
            call_idx = call_diffs.idxmin()
            call_iv = calls.loc[call_idx, "impliedVolatility"]

            put_diffs = (puts["strike"] - underlying_price).abs()
            put_idx = put_diffs.idxmin()
            put_iv = puts.loc[put_idx, "impliedVolatility"]

            atm_iv_value = (call_iv + put_iv) / 2.0
            atm_iv[exp_date] = atm_iv_value

            if i == 0:
                call_bid = calls.loc[call_idx, "bid"]
                call_ask = calls.loc[call_idx, "ask"]
                put_bid = puts.loc[put_idx, "bid"]
                put_ask = puts.loc[put_idx, "ask"]

                if call_bid is not None and call_ask is not None:
                    call_mid = (call_bid + call_ask) / 2.0
                else:
                    call_mid = None

                if put_bid is not None and put_ask is not None:
                    put_mid = (put_bid + put_ask) / 2.0
                else:
                    put_mid = None

                if call_mid is not None and put_mid is not None:
                    straddle = call_mid + put_mid

            i += 1

        if not atm_iv:
            return "Error: Could not determine ATM IV for any expiration dates."

        today = datetime.today().date()
        dtes = []
        ivs = []
        for exp_date, iv in atm_iv.items():
            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d").date()
            days_to_expiry = (exp_date_obj - today).days
            dtes.append(days_to_expiry)
            ivs.append(iv)

        term_spline = build_term_structure(dtes, ivs)

        ts_slope_0_45 = (term_spline(45) - term_spline(dtes[0])) / (45 - dtes[0])

        price_history = stock.history(period="3mo")
        iv30_rv30 = term_spline(30) / yang_zhang(price_history)

        avg_volume = price_history["Volume"].rolling(30).mean().dropna().iloc[-1]

        expected_move = (
            round(straddle / underlying_price * 100, 2) if straddle else None
        )

        best_strategy, best_expiration = determine_calendar_strategy(
            call_iv, put_iv, ts_slope_0_45, iv30_rv30, vix
        )

        market_cap_b = round(stock.info.get("marketCap", 0) / 1000000000, 2)

        # to check LONG IV oportunities
        iv_percentile = check_iv_percentile(stock)
        past_moves = compare_expected_move_to_past(stock, expected_move)
        past_moves_values = list(past_moves.values())
        # mispri
        mispriced_expected_move = round(
            (
                sum(past_moves_values) / len(past_moves_values)
                if past_moves_values
                else 1.5
            ),
            2,
        )

        return {
            "avg_volume": avg_volume >= 1500000,
            "iv30_rv30": iv30_rv30 >= 1.25,
            "iv_percentile": iv_percentile,
            "mispriced_expected_move": mispriced_expected_move,
            "past_moves": past_moves,
            "iv30_rv30_value": round(iv30_rv30, 3),
            "ts_slope_0_45": ts_slope_0_45 <= -0.00406,
            "ts_slope_0_45_value": round(ts_slope_0_45, 3),
            "expected_move": str(expected_move) + "%",
            "strategy": best_strategy,
            "expiration": best_expiration,
            "market_cap": market_cap_b,
            "stock": stock,
        }  # Check that they are in our desired range (see video)
    except Exception as e:
        raise Exception(f"Error occured processing")
