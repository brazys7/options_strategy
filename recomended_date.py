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
from datetime import datetime, timedelta

from modules.events_fetcher import fetch_earnings
from modules.validator import compute_recommendation
from modules.decision_taker import take_decision


def main_gui():
    main_layout = [
        [sg.Text("Enter Date:"), 
         sg.Input(key="date", size=(20, 1), disabled=True),  # Disabled input to avoid manual typing
         sg.CalendarButton("Pick Date", target="date", format="%Y-%m-%d", close_when_date_chosen=True, locale='en_US')],
        [sg.Button("Submit", bind_return_key=True), sg.Button("Exit")],
        [sg.Multiline("", key="output", size=(50, 1), text_color="green", disabled=True, autoscroll=True)]  
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

            # next_day = selected_date + timedelta(days=1)
            next_day = datetime.strptime(selected_date, "%Y-%m-%d").date() + timedelta(days=1)

            earnings = fetch_earnings(selected_date, next_day.strftime("%Y-%m-%d"))

            if not earnings:
                window["output"].update("No earnings found for the selected date!", text_color="red")
                continue

            tickers = [entry['symbol'] for entry in earnings]
            
            recommendations = yf.Tickers(tickers)
            # def process_entry(entry):
            #     try:
            #         symbol = entry['symbol']

            #         if symbol == "TGT":
            #             print("Processing TGT")

            #         recommendation = compute_recommendation(symbol)
            #         entry['recommendation'] = recommendation
            #         entry['decision'] = take_decision(recommendation) 
            #     except Exception as e:
            #         # entry['recommendation'] = "ERROR"
            #         # entry['decision'] = "ERROR"
            #         print(f"Error processing {entry['symbol']}: {e}")                    

            # threads = []

            # for entry in earnings:
            #     thread = threading.Thread(target=process_entry, args=(entry,))
            #     threads.append(thread)
            #     thread.start()

            # for thread in threads:
            #     thread.join()
                   

            recommended_tickers = [
                f"{entry['symbol']} - {entry['recommendation'].get('expected_move', 'N/A')}"                
                for entry in earnings if entry.get('decision') == "RECOMMEND"                
            ]

            tickers_str = "\n".join(recommended_tickers)

            new_height = len(recommended_tickers) + 1

            window["output"].update(f"Earnings found for the selected date:\n{tickers_str}")
            window["output"].Widget.config(height=new_height)
            # window["output"].update(f"Selected Date: {selected_date}", text_color="green")
                
    
    window.close()

def gui():
    main_gui()

if __name__ == "__main__":
    gui()