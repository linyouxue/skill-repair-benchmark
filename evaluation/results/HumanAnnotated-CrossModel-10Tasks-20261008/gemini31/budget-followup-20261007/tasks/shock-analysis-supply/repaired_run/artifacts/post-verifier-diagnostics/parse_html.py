import pandas as pd

try:
    dfs = pd.read_html("weo_table.html")
    print(f"Found {len(dfs)} tables")
    for i, df in enumerate(dfs):
        print(f"Table {i}")
        print(df.head())
        if 'Country' in df.columns or len(df.columns) > 10:
            df.to_csv("geo_weo.csv", index=False)
except Exception as e:
    print("Error:", e)
