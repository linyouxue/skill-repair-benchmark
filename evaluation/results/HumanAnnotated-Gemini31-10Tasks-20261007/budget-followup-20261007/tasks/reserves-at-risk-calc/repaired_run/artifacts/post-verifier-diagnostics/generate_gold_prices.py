import yfinance as yf
import pandas as pd

try:
    gold = yf.Ticker("GC=F")
    hist = gold.history(period="max", interval="1mo")
    print(hist.head())
    print(hist.tail())
    # Save the data to be used
    hist.to_csv("gold_prices.csv")
except Exception as e:
    print(e)
