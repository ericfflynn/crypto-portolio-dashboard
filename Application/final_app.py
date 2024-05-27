import streamlit as st
import sqlite3
import pandas as pd
import os
api_key = os.environ.get('CMC_API_KEY')

def get_connection():
    conn = sqlite3.connect('crypto_portfolio.db')
    return conn

def get_response_multiple(symbols):
    from requests import Session
    import json
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

def clean_response_multiple(symbols):
    data = get_response_multiple(symbols)
    df = pd.DataFrame(
        [{'symbol': symbol, **data['data'][symbol][0]['quote']['USD']} for symbol in symbols]
    )
    return df

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

# Function to add a new coin to the portfolio
def add_coin(symbol, amount, cost):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO portfolio (symbol, amount, cost) VALUES (?, ?, ?)", (symbol, amount, cost))
    conn.commit()
    conn.close()

# Function to view the portfolio
def view_portfolio():
    conn = get_connection()
    dfjoin = pd.read_sql('select portfolio.amount, portfolio.cost, prices.* from portfolio left join prices on portfolio.symbol = prices.symbol', conn)
    conn.close()
    return dfjoin

# Function to delete a coin from the portfolio
def delete_coin(symbol):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM portfolio WHERE symbol=?", (symbol,))
    conn.commit()
    conn.close()

# Function to update a coin's amount and cost
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
    st.subheader("Your Portfolio")
    if st.button("Update Prices"):
        update_prices()
    df = view_portfolio()
    st.table(df)


# Main app layout
st.title("Cryptocurrency Portfolio Tracker")

# Tabs for navigation
tab1, tab2 = st.tabs(["Portfolio", "Data Entry"])

with tab1:
    portfolio_page()
with tab2:
    data_entry_page()