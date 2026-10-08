import pandas as pd

wb = pd.read_excel('cmo.xlsx', sheet_name='Monthly Prices', header=4)
wb_gold = wb[['Unnamed: 0', 'Gold']].copy()
wb_gold.columns = ['Period', 'GoldPrice']
wb_gold['Period'] = wb_gold['Period'].astype(str)
wb_gold = wb_gold[wb_gold['Period'].str.match(r'\d{4}M\d{2}')].copy()
wb_gold['Period'] = wb_gold['Period'].str.replace(r'M0', 'M', regex=True)
wb_gold = wb_gold.set_index('Period')

yf_gold = pd.read_csv('gold_prices.csv')
yf_gold['Date'] = pd.to_datetime(yf_gold['Date'], utc=True)
yf_gold = yf_gold[yf_gold['Date'].dt.year >= 2024].copy()
yf_gold['Period'] = yf_gold['Date'].dt.year.astype(str) + 'M' + yf_gold['Date'].dt.month.astype(str)
yf_gold = yf_gold.set_index('Period')

file_path = '/root/data/test-rar.xlsx'
df_imf = pd.read_excel(file_path, sheet_name='Gold price')
prices = []

for period in df_imf['Unnamed: 0']:
    if period in wb_gold.index and pd.notna(wb_gold.loc[period, 'GoldPrice']):
        prices.append(wb_gold.loc[period, 'GoldPrice'])
    elif period in yf_gold.index and pd.notna(yf_gold.loc[period, 'Close']):
        prices.append(yf_gold.loc[period, 'Close'])
    else:
        prices.append(pd.NA)

df_imf['Gold_Price'] = prices
print(df_imf[['Unnamed: 0', 'Gold_Price']].tail(20))
