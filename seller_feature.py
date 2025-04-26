from flask import Blueprint, redirect, url_for, render_template, request, session, flash
from db import get_connect_db, send_notification
import os

seller_blueprint = Blueprint("seller", __name__, template_folder="templates")
UPLOAD_FOLDER = 'TrashNTreasure/static/uploads/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
 
@seller_blueprint.route('/seller_verification', methods=["POST", "GET"])
def seller_verification():
    if "user_name" not in session: 
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("login"))
    
    id = session.get('buyer_id')
    if not id:
        flash("You need to log in to proceed.", "danger")
        return redirect(url_for('login')) 

    con = get_connect_db()  
    cur = con.cursor() 
    
    # Check for existing rejected request
    rejected_request = cur.execute('SELECT * FROM seller_registration WHERE id = ? AND status = "Rejected"', (id,)).fetchone()
    if rejected_request:
        session['isExist'] = False
    else:
        user_exist = cur.execute('SELECT * FROM seller_registration WHERE id = ?', (id,)).fetchone()
        if user_exist:
            session['isExist'] = True
        else:
            session['isExist'] = False
    
    cur.execute('SELECT isSeller FROM user WHERE pid = ?', (id,))
    result = cur.fetchone()
    session["seller_status"] = result['isSeller'] if result else None
    
    con.close()
    if request.method == "POST":
        if session['isExist']:
            return render_template("seller_registration.html")
        
        name = request.form.get("name")
        email = request.form.get("email")
        phone_number = request.form.get("phone-number")
        description = request.form.get("description")
        
        if 'ic_picture' not in request.files or 'profile_picture' not in request.files:
            flash("Both IC and profile pictures are required.", "danger")
            return redirect(url_for('seller.seller_verification'))

        ic_picture = request.files['ic_picture']
        profile_picture = request.files['profile_picture']

        if ic_picture.filename == '' or profile_picture.filename == '':
            flash("Both IC and profile pictures must have valid filenames.", "danger")
            return redirect(url_for('seller.seller_verification'))
        
        # Create a folder for the seller based on their id
        seller_folder = os.path.join(UPLOAD_FOLDER, f'seller_{id}')
        os.makedirs(seller_folder, exist_ok=True)
        
        ic_filename = os.path.join(seller_folder, ic_picture.filename)
        profile_filename = os.path.join(seller_folder, profile_picture.filename)
        ic_filename_db = f'/static/uploads/seller_{id}/{ic_picture.filename}'
        profile_filename_db = f'/static/uploads/seller_{id}/{profile_picture.filename}'
            
        try:
            ic_picture.save(ic_filename)
            profile_picture.save(profile_filename)
        except Exception as e:
            flash(f"Error saving files: {e}", "danger")
            return redirect(url_for('seller.seller_verification'))
            
        if os.path.exists(ic_filename) and os.path.exists(profile_filename):
            con = get_connect_db()
            cur = con.cursor()
            cur.execute("""
                INSERT INTO seller_registration (id, name, email, phone_number, ic_picture, profile_picture, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id, name, email, phone_number, ic_filename_db, profile_filename_db, description))
            con.commit()
            
            # Send notification to the user
            message = "Your seller verification request has been submitted successfully! We will notify you once it has been processed."
            send_notification(con, id, "Seller Verification Request", message)
            con.close()
                        
            flash("Seller verification submitted successfully!", "success")
            return redirect(url_for('seller.seller_verification'))
        else:
            flash("File paths are invalid. Please try again.", "danger")
            return redirect(url_for('seller.seller_verification'))
    
    return render_template('seller_verification.html')

    
@seller_blueprint.route("/seller?")
def wanna_be_seller():
    return redirect(url_for("seller.seller_verification"))

@seller_blueprint.route("/your_products", methods=["GET"])
def your_products():
    seller_id = session.get("buyer_id")
    if not seller_id:
        flash("You must be logged in as a seller to access your products.", "danger")
        return redirect(url_for("login"))
    con = get_connect_db()
    cur = con.cursor()
    
    products = cur.execute("SELECT * FROM products WHERE seller_id = ?", (seller_id,)).fetchall()
    
    seller = cur.execute("SELECT address FROM user WHERE pid = ?", (seller_id,)).fetchone()
    
    if seller:
        session["seller_address"] = seller["address"]
    return render_template("seller_verification.html", products=products)

@seller_blueprint.route("/your-product-orders", methods=["GET"])
def your_product_orders():
    # Get the seller_id from the session
    seller_id = session.get('buyer_id')
    if not seller_id:
        return redirect(url_for('login'))  # Redirect to login if seller_id is not in session

    # Connect to the database
    con = get_connect_db()
    cur = con.cursor()

    # Fetch orders that include products sold by the seller
    requested_orders = cur.execute("""
        SELECT 
            orders.id AS order_id,
            orders.buyer_id,
            orders.product_id,
            orders.quantity AS order_quantity,
            orders.date,
            orders.total_amount,
            products.name AS product_name,
            products.price AS product_price,
            orders.seller_status
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE products.seller_id = ? AND orders.seller_status = "Pending"
    """, (seller_id,)).fetchall()
    
    confirmed_orders = cur.execute("""
        SELECT 
            orders.id AS order_id,
            orders.buyer_id,
            orders.product_id,
            orders.quantity AS order_quantity,
            orders.date,
            orders.total_amount,
            products.name AS product_name,
            products.price AS product_price,
            orders.seller_status
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE products.seller_id = ? AND orders.seller_status = "Confirmed"
    """, (seller_id,)).fetchall()

    
    # Close the database connection
    con.close()

    # Render the template with the fetched orders
    return render_template("seller_verification.html", requested_orders=requested_orders,  confirmed_orders=confirmed_orders)


@seller_blueprint.route("/seller_product_detail/<id>", methods=["GET"])
def product_details(id):
    con = get_connect_db()
    cur = con.cursor()
    seller_product = cur.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
    
    return render_template("seller_verification.html", seller_product=seller_product)


@seller_blueprint.route("/edit_product/<id>", methods=["POST"])
def edit_product(id):
    con = get_connect_db()
    cur = con.cursor()
    try:
        # Get the new price and quantity from the form
        new_price = request.form.get("price", type=float)
        new_quantity = request.form.get("quantity", type=int)

        # Check if the new price and quantity are valid
        if new_price is None or new_quantity is None:
            flash("Invalid price or quantity.", "danger")
            return redirect(url_for("seller.your_products", id=id)+"#Product")

        # Fetch product from database
        cur.execute("SELECT * FROM products WHERE id = ?", (id,))
        product = cur.fetchone()

        if not product:
            flash("Product not found.", "danger")
            return redirect(url_for("seller.your_products"))

        # Update the product in the database
        cur.execute(
            "UPDATE products SET price = ?, quantity = ? WHERE id = ?",
            (new_price, new_quantity, id)
        )
        con.commit()
        flash("Product updated successfully!", "success")
    except Exception as e:
        con.rollback()
        flash(f"An error occurred: {e}", "danger")
    finally:
        con.close()

    return redirect(url_for("seller.your_products", id=id)+"#Product")

@seller_blueprint.route("/accept_order/<int:order_id>", methods=["POST"])
def accept_order(order_id):
    seller_id = session.get("buyer_id")
    if not seller_id:
        flash("You must be logged in as a seller to accept an order.", "danger")
        return redirect(url_for("login"))
    con = get_connect_db()
    cur = con.cursor()
    try:
        cur.execute("UPDATE orders SET seller_status = 'Confirmed' WHERE id = ?",(order_id,))
        con.commit()
        flash(f"Order with ID {order_id} has been accepted and seller status is set to 'Confirmed'.", "success")

        # Fetch the order details to pass it to the courier section
        order = cur.execute("""
            SELECT 
                o.id as order_id,
                o.buyer_id,
                p.name as product_name,
                o.quantity as order_quantity,
                 u.address as buyer_address
            FROM orders o
            JOIN products p ON o.product_id = p.id
             JOIN user u ON o.buyer_id = u.pid
            WHERE o.id = ? AND p.seller_id = ?
        """, (order_id, seller_id)).fetchone()
        
        if order:
           buyer_id = order["buyer_id"]
           product_name = order["product_name"]
           # Construct notification message
           message = f"Your order with ID {order_id} for product {product_name} has been accepted by the seller."

           # Send notification to buyer
           send_notification(con, buyer_id, "Order Accepted", message)

        session["courier_order"] = dict(order)  # Store order data in session
    
    except Exception as e:
        flash(f"An error occurred while accepting order: {e}", "danger")
        con.rollback()
    finally:
        if con:
            con.close()

    return redirect(url_for("seller.your_product_orders") + "#Courier")

@seller_blueprint.route('/reject_order/<int:order_id>', methods=['POST'])
def reject_order(order_id):
    con = get_connect_db()
    cur = con.cursor()

    try:
        # Fetch order details
        cur.execute("""
            SELECT 
                orders.buyer_id,
                orders.total_amount,
                products.name AS product_name,
                orders.product_id,
                orders.quantity
            FROM orders
            JOIN products ON orders.product_id = products.id
            WHERE orders.id = ?
        """, (order_id,))
        order = cur.fetchone()

        if not order:
            flash(f"Order with ID {order_id} not found.", "danger")
            return redirect(url_for('seller.your_product_orders'))
            
        buyer_id = order['buyer_id']
        total_amount = order['total_amount']
        product_name = order['product_name']
        product_id = order['product_id']
        quantity = order['quantity']
        
        # Credit the amount back to the buyer's e-wallet
        cur.execute(
          "UPDATE user SET wallet = wallet + ? WHERE pid = ?",
            (total_amount, buyer_id)
        )

        # Add a record in the transaction history
        cur.execute("""
            INSERT INTO wallet_transaction (buyer_id, date, description, amount) 
            VALUES (?, DATE('now'), ?, ?)
        """, (buyer_id, f"Refund for rejected order of {product_name} (ID: {order_id})", total_amount))
      
         # Update the quantity of the product
        cur.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))
        
        # Update seller_status to 'Rejected' and delivery status to cancelled
        cur.execute("UPDATE orders SET seller_status = 'Rejected' WHERE id = ?",(order_id,))
        cur.execute("UPDATE orders SET delivery_status = 'Cancelled' WHERE id = ?",(order_id,))
        con.commit()
        
        # Construct notification message
        message = f"Your order with ID {order_id} for product {product_name} has been rejected by the seller. A refund of RM {total_amount:.2f} has been credited back to your e-wallet."
        
        # Send notification to buyer
        send_notification(con, buyer_id, "Order Rejected", message)

        flash(f"Order with ID {order_id} has been rejected.", "success")
    
    except Exception as e:
        flash(f"An error occurred while rejecting order: {e}", "danger")
        con.rollback()
    finally:
        con.close()
    
    return redirect(url_for('seller.your_product_orders'))

@seller_blueprint.route("/order_details/<order_id>", methods=["GET"])
def order_details(order_id):
    seller_id = session.get("buyer_id")
    if not seller_id:
        flash("You must be logged in as a seller to view order details.", "danger")
        return redirect(url_for("login"))
    con = get_connect_db()
    cur = con.cursor()
    # Fetch order details and user information
    order = cur.execute("""
            SELECT 
                o.id as order_id,
                o.buyer_id,
                o.product_id,
                o.quantity as order_quantity,
                o.date,
                o.total_amount,
                o.delivery_status,
                p.name as product_name,
                p.image_path as product_image_path,
                u.firstName || ' ' || u.lastName as buyer_name,
                u.email as buyer_email,
                u.phone_number as buyer_phone,
                u.address as buyer_address
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN user u ON o.buyer_id = u.pid
            WHERE o.id = ? AND p.seller_id = ?
        """, (order_id, seller_id)).fetchone()

    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("seller.your_product_orders") + "#confirmed")
    
    session["selected_order"] = dict(order)  # Convert to dictionary before storing
    return redirect(url_for("seller.your_product_orders") + "#order-details")




@seller_blueprint.route("/request_courier", methods=["POST"])
def request_courier():
   seller_id = session.get("buyer_id")
   if not seller_id:
        flash("You must be logged in as a seller to request a courier.", "danger")
        return redirect(url_for("login"))

   order_id = request.form.get("order-id")
   courier = request.form.get("courier")
   seller_address = request.form.get("seller-address")
   buyer_address = request.form.get("buyer-address")
    
   if not all([order_id, courier, seller_address, buyer_address]):
       flash("Please fill all courier details", "danger")
       return redirect(url_for("seller.your_product_orders") + "#Courier")


   con = get_connect_db()
   cur = con.cursor()
   try:
        cur.execute(
            "INSERT INTO pickup_request (order_id, seller_id, courier, seller_address, buyer_address) VALUES (?, ?, ?, ?, ?)",
            (order_id, seller_id, courier, seller_address, buyer_address)
        )
        con.commit()
        
        # Construct notification message
        message = f"Your courier request for Order ID: {order_id} has been submitted successfully! We will notify you once it has been processed."
        
        # Send notification to seller
        send_notification(con, seller_id, "Courier Request Submitted", message)
        
        flash("Courier request submitted successfully!", "success")
   except Exception as e:
        flash(f"An error occurred while requesting courier: {e}", "danger")
        con.rollback() # Rollback in case of error
   finally:
        if con:
            con.close()

   session.pop('courier_order', None) # remove the order info in session
   session.pop('seller_address', None)  #remove the seller address in session

   return redirect(url_for("seller.your_product_orders") + "#Product")