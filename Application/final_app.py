import streamlit as st
import sqlite3
import pandas as pd
import os
from requests import Session
import json
from datetime import datetime


st.set_page_config(layout="wide")
api_key = os.environ.get('CMC_API_KEY')

# Establish connection to database
def get_connection():
    conn = sqlite3.connect('crypto_portfolio.db')
    return conn

# Query raw responses from CMC API
def get_response_multiple(symbols):
    url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest'
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': api_key,
    }
    session = Session()
    session.headers.update(headers)
    parameters = {
        'symbol': ','.join(symbols)
    }
    response = session.get(url, params=parameters)
    return json.loads(response.text)

# Clean data returned from CMC API
def clean_response_multiple(symbols):
    data = get_response_multiple(symbols)
    df = pd.DataFrame(
        [{'symbol': symbol, **data['data'][symbol][0]['quote']['USD']} for symbol in symbols]
    )
    return df

#Update prices for all coins in portfolio
def update_prices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('delete from prices')
    results = cursor.execute("select distinct symbol from portfolio").fetchall()
    coins = [row[0] for row in results]
    df = clean_response_multiple(coins)
    for _, row in df.iterrows():
        cursor.execute(f'''
        insert into prices (symbol, price, volume_24h, volume_change_24h, percent_change_1h, percent_change_24h, 
                                percent_change_7d, percent_change_30d, percent_change_60d, percent_change_90d, 
                                market_cap, market_cap_dominance, fully_diluted_market_cap, tvl, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (row['symbol'], row['price'], row['volume_24h'], row['volume_change_24h'], row['percent_change_1h'],
            row['percent_change_24h'], row['percent_change_7d'], row['percent_change_30d'],
            row['percent_change_60d'], row['percent_change_90d'], row['market_cap'],
            row['market_cap_dominance'], row['fully_diluted_market_cap'], row['tvl'], row['last_updated']))
    conn.commit()
    conn.close()

# Add a new coin to the portfolio
def add_coin(symbol, amount, cost):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO portfolio (symbol, amount, cost) VALUES (?, ?, ?)", (symbol, amount, cost))
    conn.commit()
    conn.close()

def process_raw_df(raw_df):
    coins = raw_df[['symbol','amount','cost','price','percent_change_24h','percent_change_7d','percent_change_30d']].copy()
    coins['avg_price'] = coins['cost'] / coins['amount']
    coins['value'] = coins['amount']*coins['price']
    coins['net'] = coins['value'] - coins['cost']
    coins['%'] = (coins['net'] / coins['cost'])*100
    coins['X'] = coins['value'] / coins['cost']
    coins['1d_value'] = coins['value']/((coins['percent_change_24h']/100)+1)
    coins['1d_net'] = coins['value'] - coins['1d_value']
    coins['7d_value'] = coins['value']/((coins['percent_change_7d']/100)+1)
    coins['7d_net'] = coins['value'] - coins['7d_value']
    coins['30d_value'] = coins['value']/((coins['percent_change_30d']/100)+1)
    coins['30d_net'] = coins['value'] - coins['30d_value']
    return coins

# View the portfolio
def view_portfolio():
    global raw_df
    conn = get_connection()
    raw_df = pd.read_sql('select portfolio.symbol as coin, portfolio.amount, portfolio.cost, prices.* from portfolio left join prices on portfolio.symbol = prices.symbol', conn)
    conn.close()
    return process_raw_df(raw_df)

# Delete a coin from the portfolio
def delete_coin(symbol):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM portfolio WHERE symbol=?", (symbol,))
    conn.commit()
    conn.close()

# Update a coin's amount and cost
def update_coin(symbol, amount, cost):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE portfolio SET amount=?, cost=? WHERE symbol=?", (amount, cost, symbol))
    conn.commit()
    conn.close()

# Define pages
def data_entry_page():
    st.subheader("Add or Update Coin")
    with st.form("add_coin_form"):
        symbol = st.text_input("Coin Symbol (e.g., BTC, ETH)")
        amount = st.number_input("Amount", min_value=0.0, format="%.8f")
        cost = st.number_input("Cost", min_value=0.0, format="%.2f")
        submitted = st.form_submit_button("Add or Update Coin")
        
        if submitted:
            if symbol.strip() == "":
                st.error("Symbol cannot be blank!")
            else:
                add_coin(symbol, amount, cost)
                st.success("Coin added to or updated in portfolio")

    st.subheader("Delete a Coin")
    delete_symbol = st.text_input("Enter the symbol of the coin to delete")
    if st.button("Delete Coin"):
        if delete_symbol.strip() == "":
            st.error("Symbol cannot be blank!")
        else:
            delete_coin(delete_symbol)
            st.success("Coin deleted from portfolio")

def portfolio_page():
    portfolio = view_portfolio()
    last_update = datetime.strptime(min(raw_df['last_updated']), '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%Y-%m-%d %I:%M %p')
    total_value = sum(portfolio['value'])
    total_cost = sum(portfolio['cost'])
    total_net = sum(portfolio['net'])
    total_percent = total_net / total_cost
    net_1d = sum(portfolio['1d_net'])
    net_1d_percent = net_1d / (total_value + net_1d)
    net_7d = sum(portfolio['7d_net'])
    net_7d_percent = net_7d / (total_value + net_7d)
    net_30d = sum(portfolio['30d_net'])
    net_30d_percent = net_30d / (total_value + net_30d)

    st.subheader("Your Portfolio")
    st.write(f"Last Update: {last_update}", )
    met1, met2, met3, met4, met5 = st.columns(5)
    with met1:
        st.metric(label='Total Value', value='${:,.2f}'.format(total_value))
    with met2:
        st.metric(label='All Time Return', value='${:,.2f}'.format(total_net), delta="{:.1%}".format(total_percent))
    with met3:
        st.metric(label='Last Day', value='${:,.2f}'.format(net_1d), delta="{:.1%}".format(net_1d_percent))
    with met4:
        st.metric(label='Last Week', value='${:,.2f}'.format(net_7d), delta="{:.1%}".format(net_7d_percent))
    with met5:
        st.metric(label='Last Month', value='${:,.2f}'.format(net_30d), delta="{:.1%}".format(net_30d_percent))

    if st.button("Update Prices"):
        update_prices()
    st.table(portfolio)

# Main app layout
st.title("Cryptocurrency Portfolio Tracker")

# Tabs for navigation
tab1, tab2 = st.tabs(["Portfolio", "Data Entry"])

with tab1:
    portfolio_page()
with tab2:
    data_entry_page()