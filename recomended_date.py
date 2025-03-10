"""
DISCLAIMER:

This software is provided solely for educational and research purposes.
It is not intended to provide investment advice, and no investment recommendations are made herein.
The developers are not financial advisors and accept no responsibility for any financial decisions or losses resulting from the use of this software.
Always consult a professional financial advisor before making any investment decisions.
"""

import FreeSimpleGUI as sg
import threading
import yfinance as yf
import time
from datetime import datetime, timedelta

from modules.savy_events import fetch_earnings

from modules.decision_taker import take_decision
from modules.validator import compute_recommendation


def main_gui():
    main_layout = [
        [
            sg.Text("Enter Date:"),
            sg.Input(
                key="date",
                default_text=datetime.today().strftime("%Y-%m-%d"),
                size=(20, 1),
                disabled=True,
            ),  # Disabled input to avoid manual typing
            sg.CalendarButton(
                "Pick Date",
                target="date",
                format="%Y-%m-%d",
                close_when_date_chosen=True,
                locale="en_US",
            ),
        ],
        [sg.Button("Submit", bind_return_key=True), sg.Button("Exit")],
        [
            sg.Multiline(
                "",
                key="output",
                size=(50, 1),
                text_color="green",
                disabled=True,
                autoscroll=True,
            )
        ],
    ]

    window = sg.Window("Earnings by date validator", main_layout)

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break

        if event == "Submit":
            selected_date = values["date"]

            if not selected_date:
                window["output"].update("Please select a date!", text_color="red")
                continue

            earnings = fetch_earnings(selected_date)

            if not earnings:
                window["output"].update(
                    "No earnings found for the selected date!", text_color="red"
                )
                continue

            def process_entry(entry):
                try:
                    symbol = entry["symbol"]

                    vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]

                    recommendation = compute_recommendation(symbol, vix)
                    entry["recommendation"] = recommendation
                    entry["decision"] = take_decision(recommendation)
                except Exception as e:
                    # entry['recommendation'] = "ERROR"
                    # entry['decision'] = "ERROR"
                    print(f"Error processing {entry['symbol']}: {e}")

            BATCH_SIZE = 40  # Number of tickers per batch
            WAIT_TIME = 3  # Time (seconds) to wait between batches

            for i in range(0, len(earnings), BATCH_SIZE):
                batch = earnings[i : i + BATCH_SIZE]  # Get the current batch

                threads = []

                for entry in batch:
                    thread = threading.Thread(target=process_entry, args=(entry,))
                    threads.append(thread)
                    thread.start()

                # Wait for all threads in the batch to complete
                for thread in threads:
                    thread.join()

                print(
                    f"Batch {i // BATCH_SIZE + 1} completed, waiting {WAIT_TIME} seconds..."
                )
                time.sleep(WAIT_TIME)  # Prevent rate limiting

            recommended_tickers = [
                f"{entry['symbol']} ({entry['recommendation'].get('market_cap')}B) - IV:{entry['recommendation'].get('iv30_rv30_value')}% - ({entry['recommendation'].get('ts_slope_0_45_value')}%)  - {entry['recommendation'].get('expected_move', 'N/A')}% - {entry['recommendation'].get('expiration', 'N/A')}D, {entry['recommendation'].get('strategy', 'N/A')}"
                for entry in earnings
                if entry.get("decision") == "RECOMMEND"
            ]

            other_tickers = [
                f"{entry['symbol']}"
                for entry in earnings
                if entry.get("decision") != "RECOMMEND"
            ]

            all_tickers = recommended_tickers + ["______"] + other_tickers

            tickers_str = "\n".join(all_tickers)

            new_height = len(all_tickers) + 1

            window["output"].update(
                f"Earnings found for the selected date:\n{tickers_str}"
            )
            window["output"].Widget.config(height=new_height)

    window.close()


def gui():
    main_gui()


if __name__ == "__main__":
    gui()
