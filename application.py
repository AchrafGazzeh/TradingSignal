import os
import requests
from robin_stocks import robinhood
from flask import Flask, request, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# -------------------------------------------------------------------
# Environment variables
# -------------------------------------------------------------------
RH_USERNAME = os.getenv("ROBINHOOD_USERNAME")
RH_PASSWORD = os.getenv("ROBINHOOD_PASSWORD")
MFA_CODE = os.getenv("MFA_CODE")  # optional

MASTER_TRADE_SIGNAL_URL = os.getenv("MASTER_TRADE_SIGNAL_URL")
USER_TOKEN = os.getenv("USER_TOKEN")
SYMBOL = os.getenv("SYMBOL")

AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"

# -------------------------------------------------------------------
# Helper: login to Robinhood, optionally with MFA
# -------------------------------------------------------------------
def login_to_robinhood():
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
# HTML template
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
# Helper: The core trade logic
# -------------------------------------------------------------------
def do_trade_logic():
    """
    1. Log in to Robinhood
    2. Request trade-signal from master
    3. Parse and place order if needed
    Returns (is_success, message) for display
    """
    try:
        login_to_robinhood()
    except Exception as e:
        return False, f"Robinhood login failed: {str(e)}"

    payload = {"token": USER_TOKEN, "symbol": SYMBOL}
    try:
        resp = requests.post(MASTER_TRADE_SIGNAL_URL, json=payload)
    except Exception as e:
        return False, f"Error calling master: {str(e)}"

    if resp.status_code != 200:
        return False, f"Master returned error: {resp.text}"

    signal = resp.json()
    action = signal.get("action")
    limit_price = signal.get("limitPrice")
    quantity = signal.get("quantity", 1)
    symbol = signal.get("symbol")

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
# Flask Routes
# -------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """
    Renders the homepage with user info and two buttons:
    - Start Trade
    - Stop Trade
    """
    return render_template_string(
        HTML_TEMPLATE,
        email=RH_USERNAME,
        symbol=SYMBOL,
        message_success=None,
        message_error=None
    )

@app.route("/trade", methods=["POST"])
def trade():
    """Triggered by the 'Start Trade' button."""
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
    Dummy route. 
    Just show a red message saying we unsubscribed.
    """
    return render_template_string(
        HTML_TEMPLATE,
        email=RH_USERNAME,
        symbol=SYMBOL,
        message_success=None,
        message_error="Unsubscribed from trading strategy"
    )

# -------------------------------------------------------------------
# Main Entry
# -------------------------------------------------------------------
if __name__ == "__main__":
    if AUTO_TRADE:
        print("AUTO_TRADE is true. Invoking trade logic at startup...")
        success, msg = do_trade_logic()
        if success:
            print("AUTO_TRADE success:", msg)
        else:
            print("AUTO_TRADE error:", msg)

    # Start the Flask server
    app.run(host="0.0.0.0", port=8000, debug=True)
