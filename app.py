import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from helpers import (
    apology,
    format_money,
    format_time,
    get_time,
    login_required,
    lookup,
    usd,
)
from werkzeug.security import check_password_hash, generate_password_hash

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["format_time"] = format_time
app.jinja_env.filters["format_money"] = format_money

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
print(f'This is my change -> {os.environ.get("API_KEY")}')
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")





@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    totalBalance = balance = db.execute(
        "SELECT cash FROM users WHERE id = ?", session["user_id"]
    )[0]["cash"]
    portfolio = db.execute("SELECT symbol, SUM(quantity) FROM transactions WHERE u_id=? GROUP BY symbol",
        session["user_id"],
    )
    prices = []

    for i, owned in enumerate(portfolio):
        temp = lookup(owned["symbol"])["price"]
        prices.append(temp)
        totalBalance += portfolio[i]["SUM(quantity)"] * prices[i]

    return render_template(
       "index.html",
        port=portfolio,
        prices=prices,
        balance=balance,
        total_bal=totalBalance,
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        # Check if a symbol is provided
        symbol_input = request.form.get("symbol")
        if not symbol_input:
            return apology("Symbol cannot be blank", 400)

        # Validate shares input
        shares_input = request.form.get("shares")
        if not shares_input:
            return apology("Shares cannot be empty", 400)

        try:
            shares = float(shares_input)
            if shares <= 0:
                return apology("Shares must be a positive number", 400)
            if shares != int(shares):
                return apology("Shares must be a whole number", 400)  # Ensure it's an integer
        except ValueError:
            return apology("Shares must be a numeric value", 400)

        # Lookup the stock symbol
        symbol = lookup(symbol_input)
        if not symbol:
            return apology("Symbol not found", 400)

        price = symbol["price"]
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        new_balance = balance - (price * shares)

        # Check if the user has enough funds
        if new_balance < 0:
            return apology("Not enough money", 400)

        # Update user's cash balance
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?",
            new_balance,
            session["user_id"],
        )

        # Record the transaction
        db.execute(
            "INSERT INTO transactions (symbol, quantity, price, u_id) VALUES(?, ?, ?, ?)",
            symbol_input,
            int(shares),  # Store as an integer in the database
            price,
            session["user_id"],
        )

        return redirect("/")

    return render_template("buy.html")






# if request.method == "POST":
@app.route("/history")
@login_required
def history():
    transactions = db.execute(
        "SELECT u_id, symbol, quantity, price, timestamp FROM transactions WHERE u_id=? ORDER BY u_id DESC",
        session["user_id"],
    )

    # Prepare a list of transactions with additional formatting if necessary
    formatted_transactions = []
    for transaction in transactions:
        formatted_transactions.append({
            "id": transaction["u_id"],
            "symbol": transaction["symbol"],
            "quantity": transaction["quantity"],
            "price": f"${transaction['price']:.2f}",  # Format price to two decimal places
            "timestamp": transaction["timestamp"].strftime("%Y-%m-%d %H:%M:%S")  # Format timestamp
        })

    return render_template("history.html", transactions=formatted_transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Get and format user input
        symbol = request.form.get("symbol").strip().upper()

        # Check if symbol is empty
        if not symbol:
            return apology("Symbol cannot be empty", 400)

        # Look up the stock using the provided symbol
        result = lookup(symbol)

        # Handle case where symbol is not found
        if result is None:
            return apology("Symbol not found", 400)

        # Render results in quoted.html
        return render_template("quoted.html", result=result)

    # Render the quote input form on GET request
    return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was submitted again
        elif not request.form.get("confirmation"):
            return apology("must re-enter password", 400)

        # Ensure that the passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match")

        # Check if the username is available
        check = db.execute(
            "SELECT * FROM users WHERE username=?", request.form.get("username")
        )
        if len(check) != 0:
            return apology("username not available")

        db.execute(
            "INSERT INTO users (username, hash, cash) VALUES(?, ?, ?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("confirmation")),
            10000.0,
        )

        # Redirect user to home page
        return redirect("/")
    return render_template("register.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
     # Retrieve the user's portfolio
    portfolio = db.execute(
        "SELECT symbol, SUM(quantity) FROM transactions WHERE u_id=? GROUP BY symbol",
        session["user_id"],
    )

    if request.method == "POST":
        # Check if a symbol is selected
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please select what to sell", 400)

        # Check if shares input is valid
        shares_input = request.form.get("shares")
        if not shares_input or not shares_input.isdigit() or int(shares_input) <= 0:
            return apology("Shares must be a positive number", 400)

        shares_to_sell = int(shares_input)

        # Check if the user owns enough shares
        owned_shares = next((item for item in portfolio if item["symbol"] == symbol), None)
        if not owned_shares or shares_to_sell > owned_shares["SUM(quantity)"]:
            return apology("Not enough shares owned", 400)

        # Proceed with the sale
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        price = lookup(symbol)["price"]
        new_balance = balance + (shares_to_sell * price)

        # Update user's cash balance
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"]
        )

        # Record the transaction
        db.execute(
            "INSERT INTO transactions (symbol, quantity, price, u_id) VALUES(?, ?, ?, ?)",
            symbol,
            -shares_to_sell,
            price,
            session["user_id"],
        )

        return redirect("/")

    return render_template("sell.html", port=portfolio)


@app.route("/delete")
@login_required
def delete():
    i = session["user_id"]
    session.clear()
    db.execute("DELETE FROM users WHERE id=?", i)

    return redirect("/login")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
