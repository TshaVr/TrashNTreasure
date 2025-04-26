from flask import Flask, redirect, url_for, render_template, request, session, flash
from admin_feature import admin_blueprint
from user_feature import user_blueprint
from logistic_feature import logistic_blueprint
from seller_feature import seller_blueprint
from products import product_blueprint
from db import get_connect_db, get_unread_notification_count

app = Flask(__name__)
app.secret_key = "Strong_Key_Secret_Key"

app.register_blueprint(admin_blueprint, url_prefix="/admin")
app.register_blueprint(user_blueprint, url_prefix="/user")
app.register_blueprint(logistic_blueprint, url_prefix="/logistic")
app.register_blueprint(seller_blueprint, url_prefix="/seller")
app.register_blueprint(product_blueprint, url_prefix="/product")

@app.route("/signup", methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        try: 
            # Get user input from the form
            fname = request.form.get("first_name")
            lname = request.form.get("last_name")
            email = request.form.get("email")
            password = request.form.get("password")
            confirm_password = request.form.get("confirm_password")
            
            if password != confirm_password:
                print(f'{password} != {confirm_password}')
                flash("Password confirmation does not match.", "danger")
                return redirect(url_for("signup"))
            
            # Connect to the database
            with get_connect_db() as con:
                cur = con.cursor()
                
                # Check if the email already exists
                cur.execute("SELECT * FROM user WHERE email = ?", (email,))
                user = cur.fetchone()
                if user:
                    flash("Email already exists. Please log in or use a different email.", "danger")
                    return redirect(url_for("signup"))
                
                # Insert the new user into the database
                cur.execute(
                    "INSERT INTO user (firstName, lastName, email, password) VALUES (?, ?, ?, ?)",
                    (fname, lname, email, password),
                )
                con.commit()
                flash("Account created successfully! You can now log in.", "success")
                return redirect(url_for("login"))
        
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for("signup"))

    # Render the sign-up page
    return render_template("signUp.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        con = get_connect_db()
        cur = con.cursor()
        cur.execute("SELECT * FROM user WHERE email = ? and password = ?", (email, password)) #checking 
        data = cur.fetchone()
        con.close()

        if data: 
            session["user_name"] = data["firstName"] + " " + data["lastName"] 
            session["email"] = data["email"]
            session["buyer_id"] = data["pid"]  
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password", "danger")
        
    return render_template("logIn.html")

@app.route("/")
def home():
    buyer_id = session.get("buyer_id")
    cart_item_count = 0  # Default value

    if buyer_id:
        con = get_connect_db()
        cur = con.cursor()

        # Fetch user details
        user = cur.execute("SELECT * FROM user WHERE pid = ?", (buyer_id,)).fetchone()
        if user:
            session["e-wallet"] = user["wallet"]

        # Fetch cart item count
        cart_item_count = cur.execute("SELECT COUNT(*) FROM cart WHERE buyer_id = ?", (buyer_id,)).fetchone()[0]
        session["cart_item_count"] = cart_item_count  # Update session variable
        con.close()
    
    return render_template("index.html")

@app.route("/aboutus")
def about_page():
    return render_template("about.html")

@app.route("/product")
def product_page():
    con = get_connect_db()
    cur = con.cursor()
    products = cur.execute("SELECT * FROM products WHERE quantity > 0").fetchall()
    
    return render_template("product.html", products=products)

@app.route("/cart")
def cart():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to view your cart.", "error")
        return redirect(url_for("auth.login"))  # Redirect to login if user is not logged in

    con = get_connect_db()
    cur = con.cursor()
    
    # Fetch products added to the cart by the current buyer
    added_products = cur.execute("SELECT * FROM cart WHERE buyer_id = ?", (buyer_id,)).fetchall()
    # Calculate the total price
    total_price = sum(product["price"] * product["quantity"] for product in added_products)

    con.close()

    return render_template("cart.html", added_products=added_products, total_price=total_price)

@app.route('/payment')
def payment_page():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to proceed to checkout.", "danger")
        return redirect(url_for("login"))

    payment_items = session.get("payment_items")

    if not payment_items:
        flash("Your payment information is missing. Please try again.", "warning")
        return redirect(url_for("cart"))
    
    total_price = sum(item["quantity"] * item["price"] for item in payment_items)

    return render_template("payment.html", payment_items=payment_items, total_price=total_price)


@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/e-wallet", methods=['GET', 'POST'])
def eWallet():
    id = session.get("buyer_id")
    if not id:
        flash("You must be logged in to proceed to checkout.", "danger")
        return redirect(url_for("login"))
    
    con = get_connect_db()
    cur = con.cursor()

    user = cur.execute("SELECT * FROM user WHERE pid = ?", (id,)).fetchone()
    date_filter = request.form.get('dateFilter', '')
    
    try:
        if date_filter:
            cur.execute("SELECT * FROM wallet_transaction WHERE buyer_id = ? AND date = ?", (id, date_filter))
        else:
            cur.execute("SELECT * FROM wallet_transaction WHERE buyer_id = ?", (id,))
        transactions = cur.fetchall()
    except Exception as e:
        flash(f"Error while fetching transaction: {e}", "error")
        transactions = []
    finally:
        if con:
            con.close()
    
    return render_template("e-wallet.html", user=user, transactions=transactions, date_filter=date_filter)


@app.route("/my-orders", methods=["GET", "POST"])
def user_orders():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
      flash("You must be logged in to see your orders.", "error")
      return redirect(url_for("login"))
    
    con = get_connect_db()
    cur = con.cursor()
    date_filter = request.form.get('dateFilter', '')
    try:
        if date_filter:
            cur.execute("SELECT * FROM orders WHERE buyer_id = ? AND date = ?", (buyer_id, date_filter,))
        else:
            cur.execute("SELECT * FROM orders WHERE buyer_id = ?", (buyer_id,))
        orders = cur.fetchall()

        processed_orders = []
        for order in orders:
            cur.execute("SELECT * FROM products WHERE id = ?", (order["product_id"],))
            product = cur.fetchone()

            processed_orders.append({
                "id": order["id"],
                "date": order["date"],
                "products":{
                    "product_name": product["name"],
                    "quantity":order["quantity"]
                },
                "total_amount": order["total_amount"],
                "delivery_status": order["delivery_status"]
             })
    except Exception as e:
        flash(f"Error while fetching orders: {e}", "error")
        processed_orders = []
    finally:
        if con:
            con.close()
            
    return render_template("ordersHistory.html", orders=processed_orders, date_filter=date_filter)

    
app.jinja_env.globals.update(get_unread_notification_count=get_unread_notification_count)



@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(debug=True)
 
 
