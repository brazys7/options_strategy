"""
DISCLAIMER:

This software is provided solely for educational and research purposes.
It is not intended to provide investment advice, and no investment recommendations are made herein.
The developers are not financial advisors and accept no responsibility for any financial decisions or losses resulting from the use of this software.
Always consult a professional financial advisor before making any investment decisions.
"""

# import PySimpleGUI as sg
import FreeSimpleGUI as sg
import threading
import yfinance as yf
import time
from datetime import datetime

from modules.savy_events import fetch_earnings
from modules.decision_taker import take_decision
from modules.validator import compute_recommendation

# Define theme
print(f"PySimpleGUI version: {sg.__version__}")
print(f"Has theme function: {'theme' in dir(sg)}")
sg.theme("DarkBlue")


def create_details_window(ticker_data):
    """Create a detailed window for a specific ticker"""
    recommendation = ticker_data["recommendation"]
    past_moves = recommendation.get("past_moves", {})  # Get past moves dictionary
    stock = recommendation.get("stock", {})
    stock_info = stock.fast_info if stock else {}

    # Create a more detailed layout
    details_layout = [
        [sg.Text(f"Details for {ticker_data['symbol']}", font=("Helvetica", 16))],
        [
            sg.Text(
                f"Decision: {ticker_data['decision']}",
                font=("Helvetica", 12),
                text_color="green"
                if ticker_data["decision"] in ["RECOMMEND", "RECOMMEND_BUY"]
                else "yellow"
                if ticker_data["decision"] == "CONSIDER"
                else "white",
            )
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Market Data", font=("Helvetica", 14, "bold"))],
        [sg.Text(f"Market Cap: {recommendation.get('market_cap', 'N/A')}B")],
        [sg.Text(f"Current Price: ${round(stock_info.get('last_price', 100), 2)}")],
        [
            sg.Text(
                f"52-Week Range: ${stock_info.get('year_low', 0)} - ${stock_info.get('year_high', 0)}"
            )
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Volatility Metrics", font=("Helvetica", 14, "bold"))],
        [sg.Text(f"IV30/RV30: {recommendation.get('iv30_rv30_value', 'N/A')}%")],
        [sg.Text(f"IV Percentile: {recommendation.get('iv_percentile', 'N/A')}%")],
        [
            sg.Text(
                f"Term Structure Slope: {recommendation.get('ts_slope_0_45_value', 'N/A')}%"
            )
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Strategy Information", font=("Helvetica", 14, "bold"))],
        [sg.Text(f"Recommended Strategy: {recommendation.get('strategy', 'N/A')}")],
        [sg.Text(f"Expected Move: {recommendation.get('expected_move', 'N/A')}")],
        [
            sg.Text(
                f"Recommended Expiration: {recommendation.get('expiration', 'N/A')} days"
            )
        ],
        [
            sg.Text(
                f"Average Miss: {recommendation.get('mispriced_expected_move', 'N/A')}%"
            )
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Previous Moves", font=("Helvetica", 14, "bold"))],
    ]

    # Display each date and move percentage in a new row
    for date, move in sorted(past_moves.items(), reverse=True):  # Sorting latest first
        details_layout.append([sg.Text(f"{date}: {move:.2f}%")])

    details_layout.extend(
        [
            [sg.HorizontalSeparator()],
            [sg.Button("Close")],
        ]
    )

    window = sg.Window(
        f"{ticker_data['symbol']} Details", details_layout, modal=True, finalize=True
    )

    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED or event == "Close":
            break

    window.close()


def main_gui():
    # Define the layout for the main tab
    main_tab_layout = [
        [
            sg.Text("Enter Date:"),
            sg.Input(
                key="date",
                default_text=datetime.today().strftime("%Y-%m-%d"),
                size=(20, 1),
                disabled=True,
            ),
            sg.CalendarButton(
                "Pick Date",
                target="date",
                format="%Y-%m-%d",
                close_when_date_chosen=True,
                locale="en_US",
            ),
            sg.Button("Submit", bind_return_key=True),
            sg.Button("Exit"),
        ],
        [
            sg.Text("Processing Status:", size=(15, 1)),
            sg.Text("", key="status", size=(40, 1)),
        ],
        [sg.ProgressBar(100, orientation="h", size=(40, 20), key="progress")],
    ]

    # Define layout for each category tab
    recommended_short_layout = [
        [
            sg.Listbox(
                values=[],
                size=(80, 20),
                key="recommended_short_list",
                enable_events=True,
            )
        ]
    ]

    consider_short_layout = [
        [
            sg.Listbox(
                values=[], size=(80, 20), key="consider_short_list", enable_events=True
            )
        ]
    ]

    recommended_long_layout = [
        [
            sg.Listbox(
                values=[],
                size=(80, 20),
                key="recommended_long_list",
                enable_events=True,
            )
        ]
    ]

    other_tickers_layout = [
        [
            sg.Listbox(
                values=[], size=(80, 20), key="other_tickers_list", enable_events=True
            )
        ]
    ]

    # Create the TabGroup
    tab_group_layout = [
        [sg.Tab("Main", main_tab_layout)],
        [sg.Tab("Recommended Short", recommended_short_layout)],
        [sg.Tab("Consider Short", consider_short_layout)],
        [sg.Tab("Recommended Long", recommended_long_layout)],
        [sg.Tab("Other Tickers", other_tickers_layout)],
    ]

    # Create the main layout with the TabGroup
    layout = [[sg.TabGroup(tab_group_layout, key="tab_group", enable_events=True)]]

    window = sg.Window("Earnings IV Trader", layout, resizable=True, finalize=True)

    # Dictionary to store all ticker data
    all_ticker_data = {}

    while True:
        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, "Exit"):
            break

        if event == "Submit":
            selected_date = values["date"]

            if not selected_date:
                sg.popup_error("Please select a date!")
                continue

            # Clear previous data
            window["recommended_short_list"].update([])
            window["consider_short_list"].update([])
            window["recommended_long_list"].update([])
            window["other_tickers_list"].update([])
            all_ticker_data = {}

            # Fetch earnings
            window["status"].update("Fetching earnings data...")
            earnings = fetch_earnings(selected_date)
            # earnings = [
            #     {
            #         "symbol": "WSM",
            #         "sk": "earnings#2025#q3",
            #         "earningsDate": "2025-03-20",
            #         "earningsTime": "16:15:00",
            #         "isDateConfirmed": True,
            #         "marketCap": 108434792085.97,
            #     }
            # ]

            if not earnings:
                window["status"].update("No earnings found for the selected date!")
                continue

            window["status"].update(f"Processing {len(earnings)} tickers...")
            window["progress"].update(0)

            # Process tickers
            processed_count = 0

            def process_entry(entry):
                nonlocal processed_count
                try:
                    symbol = entry["symbol"]
                    vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
                    recommendation = compute_recommendation(symbol, vix)
                    entry["recommendation"] = recommendation
                    entry["decision"] = take_decision(recommendation)

                    # Update progress
                    processed_count += 1
                    progress_value = int((processed_count / len(earnings)) * 100)
                    window.write_event_value(
                        "-PROGRESS-",
                        (
                            progress_value,
                            f"Processed {processed_count}/{len(earnings)}: {symbol}",
                        ),
                    )

                except Exception as e:
                    print(f"Error processing {entry['symbol']}: {e}")
                    window.write_event_value(
                        "-ERROR-", f"Error processing {entry['symbol']}: {e}"
                    )

            BATCH_SIZE = 40
            WAIT_TIME = 3

            # Start processing in a separate thread
            def process_all_entries():
                for i in range(0, len(earnings), BATCH_SIZE):
                    batch = earnings[i : i + BATCH_SIZE]
                    threads = []

                    for entry in batch:
                        thread = threading.Thread(target=process_entry, args=(entry,))
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()

                    if i + BATCH_SIZE < len(earnings):  # If not the last batch
                        time.sleep(WAIT_TIME)

                window.write_event_value("-PROCESSING-COMPLETE-", None)

            processing_thread = threading.Thread(target=process_all_entries)
            processing_thread.daemon = True
            processing_thread.start()

        elif event == "-PROGRESS-":
            progress_value, status_text = values["-PROGRESS-"]
            window["progress"].update(progress_value)
            window["status"].update(status_text)

        elif event == "-ERROR-":
            error_text = values["-ERROR-"]
            window["status"].update(error_text, text_color="red")

        elif event == "-PROCESSING-COMPLETE-":
            window["status"].update("Processing complete! Results available in tabs.")
            window["progress"].update(100)

            # Organize results into categories
            recommended_short = []
            consider_short = []
            recommended_long = []
            other_tickers = []

            for entry in earnings:
                symbol = entry["symbol"]
                recommendation = entry.get("recommendation", {})
                decision = entry.get("decision", "SKIP")

                # Store full ticker data
                all_ticker_data[symbol] = entry

                if isinstance(recommendation, dict):
                    display_str = (
                        f"{symbol} - Market Cap: {recommendation.get('market_cap', 'N/A')}B - "
                        f"IV/RV: {recommendation.get('iv30_rv30_value', 'N/A')}% - "
                        f"Term Structure: {recommendation.get('ts_slope_0_45_value', 'N/A')}% - "
                        f"Exp. Move: {recommendation.get('expected_move', 'N/A')}%"
                    )
                else:
                    # Handle the case where recommendation is a string or other type
                    display_str = f"{symbol} - Recommendation: {recommendation}"

                # Add to appropriate list
                if decision == "RECOMMEND":
                    recommended_short.append(display_str)
                elif decision == "CONSIDER":
                    consider_short.append(display_str)
                elif decision == "RECOMMEND_BUY":
                    recommended_long.append(display_str)
                else:
                    other_tickers.append(display_str)

            # Update the listboxes
            window["recommended_short_list"].update(recommended_short)
            window["consider_short_list"].update(consider_short)
            window["recommended_long_list"].update(recommended_long)
            window["other_tickers_list"].update(other_tickers)

            # Switch to the appropriate tab if there are results
            if recommended_short:
                window["tab_group"].Widget.select(1)  # Switch to Recommended Short tab
            elif consider_short:
                window["tab_group"].Widget.select(2)  # Switch to Consider Short tab
            elif recommended_long:
                window["tab_group"].Widget.select(3)  # Switch to Recommended Long tab

        # Handle clicking on a ticker in any of the lists
        elif event in (
            "recommended_short_list",
            "consider_short_list",
            "recommended_long_list",
            "other_tickers_list",
        ):
            if values[event]:  # If something is selected
                selected_item = values[event][0]
                symbol = selected_item.split(" ")[0]  # Extract the ticker symbol

                if symbol in all_ticker_data:
                    create_details_window(all_ticker_data[symbol])

    window.close()


def gui():
    main_gui()


if __name__ == "__main__":
    gui()
