import os
import requests
from robin_stocks import robinhood
from flask import Flask, request, render_template_string
import configparser

app = Flask(__name__)

# -------------------------------------------------------------------
# 1. Load config from config.ini
# -------------------------------------------------------------------
config = configparser.ConfigParser()
config.read("config.ini")  

RH_USERNAME = config.get("default", "ROBINHOOD_USERNAME", fallback="")
RH_PASSWORD = config.get("default", "ROBINHOOD_PASSWORD", fallback="")
MFA_CODE = config.get("default", "MFA_CODE", fallback="")
MASTER_TRADE_SIGNAL_URL = config.get("default", "MASTER_TRADE_SIGNAL_URL", fallback="")
USER_TOKEN = config.get("default", "USER_TOKEN", fallback="")
SYMBOL = config.get("default", "SYMBOL", fallback="")
AUTO_TRADE = config.getboolean("default", "AUTO_TRADE", fallback=False)

# -------------------------------------------------------------------
# 2. Login to Robinhood (helper)
# -------------------------------------------------------------------
def login_to_robinhood():
    """
    Logs into Robinhood. If MFA_CODE is present, we pass it.
    """
    if MFA_CODE:
        robinhood.login(
            username=RH_USERNAME,
            password=RH_PASSWORD,
            mfa_code=MFA_CODE
        )
    else:
        robinhood.login(
            username=RH_USERNAME,
            password=RH_PASSWORD
        )

# -------------------------------------------------------------------
# 3. HTML template
# -------------------------------------------------------------------
HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>Trading Signal Homepage</title>
    <style>
      .message-success { color: green; }
      .message-error { color: red; }
    </style>
</head>
<body>
    <h2>Trading Signal Homepage</h2>

    <p><strong>User Email:</strong> {{ email }}</p>
    <p><strong>Symbol:</strong> {{ symbol }}</p>

    <form action="/trade" method="POST">
        <button type="submit">Start Trade</button>
    </form>

    <form action="/stop-trade" method="POST">
        <button type="submit">Stop Trade</button>
    </form>

    {% if message_success %}
    <p class="message-success">{{ message_success }}</p>
    {% endif %}

    {% if message_error %}
    <p class="message-error">{{ message_error }}</p>
    {% endif %}
</body>
</html>
"""

# -------------------------------------------------------------------
# 4. Core trade logic
# -------------------------------------------------------------------
def do_trade_logic():
    """
    1. Log in to Robinhood
    2. POST to master /trade-signal
    3. Parse the response, place limit order if BUY/SELL
    Returns (success_boolean, message_string)
    """
    # 1. Log in
    try:
        login_to_robinhood()
    except Exception as e:
        return False, f"Robinhood login failed: {str(e)}"

    # 2. Call the master endpoint
    payload = {"token": USER_TOKEN, "symbol": SYMBOL}
    try:
        resp = requests.post(MASTER_TRADE_SIGNAL_URL, json=payload)
    except Exception as e:
        return False, f"Error calling master: {str(e)}"

    if resp.status_code != 200:
        return False, f"Master returned error: {resp.text}"

    signal = resp.json()  # e.g. {"action":"BUY","symbol":"ZSC","quantity":1,"limitPrice":50.0}
    action = signal.get("action")
    limit_price = signal.get("limitPrice")
    quantity = signal.get("quantity", 1)
    symbol = signal.get("symbol")

    # 3. Place the order if recognized
    try:
        if action == "BUY":
            robinhood.order_buy_limit(
                symbol=symbol,
                quantity=quantity,
                limitPrice=limit_price
            )
        elif action == "SELL":
            robinhood.order_sell_limit(
                symbol=symbol,
                quantity=quantity,
                limitPrice=limit_price
            )
        else:
            return False, f"No valid action in signal: {action}"

    except Exception as e:
        return False, f"Order placement failed: {str(e)}"

    return True, "Subscribed successfully to trading strategy"

# -------------------------------------------------------------------
# 5. Flask routes
# -------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return render_template_string(
        HTML_TEMPLATE,
        email=RH_USERNAME,
        symbol=SYMBOL,
        message_success=None,
        message_error=None
    )

@app.route("/trade", methods=["POST"])
def trade():
    success, msg = do_trade_logic()
    if success:
        return render_template_string(
            HTML_TEMPLATE,
            email=RH_USERNAME,
            symbol=SYMBOL,
            message_success=msg,
            message_error=None
        )
    else:
        return render_template_string(
            HTML_TEMPLATE,
            email=RH_USERNAME,
            symbol=SYMBOL,
            message_success=None,
            message_error=msg
        )

@app.route("/stop-trade", methods=["POST"])
def stop_trade():
    """
    Route to show unsubscribed message
    """
    return render_template_string(
        HTML_TEMPLATE,
        email=RH_USERNAME,
        symbol=SYMBOL,
        message_success=None,
        message_error="Unsubscribed from trading strategy"
    )

# -------------------------------------------------------------------
# 6. Main Entry
# -------------------------------------------------------------------
if __name__ == "__main__":
    if AUTO_TRADE:
        print("AUTO_TRADE is true. Invoking trade logic at startup...")
        success, msg = do_trade_logic()
        if success:
            print("AUTO_TRADE success:", msg)
        else:
            print("AUTO_TRADE error:", msg)

    app.run(host="0.0.0.0", port=8000, debug=True)
