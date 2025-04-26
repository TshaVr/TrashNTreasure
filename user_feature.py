from flask import Blueprint, redirect, url_for, render_template, request, session, flash
from db import get_connect_db, send_notification
import re

user_blueprint = Blueprint("user", __name__, template_folder="templates")

@user_blueprint.route("/")
def user_page():
    buyer_id = session.get("buyer_id")
    if buyer_id:
        con = get_connect_db()
        cur = con.cursor()
        user = cur.execute("SELECT * FROM user WHERE pid = ?", (buyer_id,)).fetchone()
        return render_template("user_page.html", user=user)    
    else:
        flash("Please log in to access the user account.", "danger")
        return redirect(url_for("login"))

@user_blueprint.route('/logout')
def logout(): 
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@user_blueprint.route('/proceed_to_payment', methods=["POST"])
def proceed_to_payment():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to proceed to checkout.", "error")
        return redirect(url_for("login"))

    con = get_connect_db()
    cur = con.cursor()
    
    # Fetch latest products added to the cart by the current buyer
    added_products = cur.execute("SELECT * FROM cart WHERE buyer_id = ?", (buyer_id,)).fetchall()
    
    if not added_products:
        flash("Your cart is empty. Add items to proceed to checkout.", "warning")
        return redirect(url_for("product_page"))
    
    # Prepare cart items for payment page
    payment_items = []
    for product in added_products:
        quantity_key = f"quantity_{product['id']}"
        new_quantity = request.form.get(quantity_key, type=int)
        if new_quantity is None:
            new_quantity = product['quantity']
            
        seller_id = cur.execute("SELECT seller_id FROM products WHERE id = ?", (product["product_id"],)).fetchone()
        
        payment_items.append({
                "product_id": product["product_id"],
                "product_name": product["product_name"],
                "quantity": new_quantity,
                "price": product["price"],
                "seller_id": seller_id[0] if seller_id else None,
                "product_image_path": product["product_image_path"]
        })
    con.close()
    session["payment_items"] = payment_items
    return redirect(url_for("payment_page"))

@user_blueprint.route('/withdraw', methods=['POST'])
def withdraw():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to withdraw funds.", "error")
        return redirect(url_for("login"))

    amount = request.form.get("withdrawAmount", type=float)
    if amount is None or amount < 50:
        flash("Invalid withdraw amount. Minimum withdrawal amount is RM50", "danger")
        return redirect(url_for("eWallet"))

    con = get_connect_db()
    cur = con.cursor()
    try:
        cur.execute("SELECT wallet, haveBankCard FROM user WHERE pid = ?", (buyer_id,))
        user_record = cur.fetchone()
        user_balance = user_record["wallet"] if user_record else 0
        have_bank_card = user_record["haveBankCard"] if user_record else False


        if not have_bank_card:
            flash("You must add your bank card to withdraw funds", "warning")
            return redirect(url_for("eWallet"))

        if user_balance < amount:
            flash("Insufficient funds for withdrawal.", "danger")
            return redirect(url_for("eWallet"))
        
        new_balance = user_balance - amount
        cur.execute("UPDATE user SET wallet = ? WHERE pid = ?", (new_balance, buyer_id))

        cur.execute(
          "INSERT INTO wallet_transaction (buyer_id, date, description, amount) VALUES (?, DATE('now'), ?, ?)",
            (buyer_id, f"Withdrawal: RM{amount:.2f}", -amount,)
        )

        con.commit()
        session["e-wallet"] = new_balance # Update e-wallet balance here
        flash(f"Successfully withdrawn RM {amount:.2f}!", "success")
    except Exception as e:
        flash(f"Error while withdrawing funds: {e}", "danger")
    finally:
         if con:
            con.close()
    return redirect(url_for("eWallet"))

@user_blueprint.route('/top_up', methods=['POST'])
def top_up():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to top up your e-wallet.", "danger")
        return redirect(url_for("login"))

    amount = request.form.get("topUpAmount", type=float)
    if amount is None or amount < 20:
        flash("Invalid top-up amount. Minimum amount of top up is RM20", "danger")
        return redirect(url_for("eWallet"))

    con = get_connect_db()
    cur = con.cursor()
    try:
        cur.execute("SELECT * FROM user WHERE pid = ?", (buyer_id,))
        user_record = cur.fetchone()
        user_balance = user_record["wallet"] if user_record else 0.00
            
        new_balance = user_balance + amount
        cur.execute("UPDATE user SET wallet = ? WHERE pid = ?", (new_balance, buyer_id))

        cur.execute(
            "INSERT INTO wallet_transaction (buyer_id, date, description, amount) VALUES (?, DATE('now'), ?, ?)",
               (buyer_id, f"Top-up: RM{amount:.2f}", amount,) 
        )
            
        con.commit()
        flash(f"Successfully topped up RM {amount:.2f}!", "success")
    except Exception as e:
        flash(f"Error while topping up: {e}", "danger")
    finally:
        if con:
            con.close()

    return redirect(url_for("eWallet")) 


@user_blueprint.route('/update_user_info', methods=['POST'])
def update_user_info():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to update your information.", "danger")
        return redirect(url_for("login"))

    phone_number = request.form.get("phone_number")
    address = request.form.get("address")
    
    con = get_connect_db()
    cur = con.cursor()
    try:
        cur.execute("UPDATE user SET phone_number = ?, address = ? WHERE pid = ?", (phone_number, address, buyer_id))
        con.commit()
        flash("User information updated successfully!", "success")
    except Exception as e:
         flash(f"An error occurred: {e}", "danger")
    finally:
        if con:
          con.close()
    
    return redirect(url_for("user.user_page"))


@user_blueprint.route('/add_bank_card', methods=['POST'])
def add_bank_card():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to add a bank card.", "danger")
        return redirect(url_for("login"))

    card_number = request.form.get("card_number")
    card_holder = request.form.get("card_holder")
    expiry_date = request.form.get("expiry_date")
    cvv = request.form.get("cvv")
    
    if not all([card_number, card_holder, expiry_date, cvv]):
        flash("Please fill all bank card details", "danger")
        return redirect(url_for("user.user_page")+"/#bank-card")
    
    # Basic CVV validation, allow only 3 or 4 digit numbers
    if not re.match(r'^\d{3,4}$', cvv):
      flash("Invalid CVV format. Use 3 or 4 digit numbers", "danger")
      return redirect(url_for("user.user_page")+"/#bank-card")


    con = get_connect_db()
    cur = con.cursor()

    try:
        cur.execute("UPDATE user SET haveBankCard = 1 WHERE pid = ?", (buyer_id,))
        con.commit()
        flash("Bank card added successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    finally:
         if con:
            con.close()
    
    return redirect(url_for("user.user_page")+"/#bank-card")

@user_blueprint.route('/remove_bank_card', methods=['POST'])
def remove_bank_card():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to remove your bank card.", "error")
        return redirect(url_for("login"))

    con = get_connect_db()
    cur = con.cursor()

    try:
      cur.execute("UPDATE user SET haveBankCard = 0 WHERE pid = ?", (buyer_id,))
      con.commit()
      flash("Bank card removed successfully!", "success")
    except Exception as e:
         flash(f"An error occurred: {e}", "danger")
    finally:
        if con:
            con.close()

    return redirect(url_for("user.user_page")+"/#bank-card")


@user_blueprint.route('/change_password', methods=['POST'])
def change_password():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to change your password.", "error")
        return redirect(url_for("login"))

    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    if not all([current_password, new_password, confirm_password]):
      flash("Please fill all password fields", "danger")
      return redirect(url_for("user.user_page")+"/#change-password")
    
    if new_password != confirm_password:
        flash("New password and confirm password do not match.", "danger")
        return redirect(url_for("user.user_page")+"/#change-password")

    con = get_connect_db()
    cur = con.cursor()
    try:
        cur.execute("SELECT password FROM user WHERE pid = ?", (buyer_id,))
        user_record = cur.fetchone()
        
        if not user_record or user_record["password"] != current_password:
          flash("Incorrect current password.", "danger")
          return redirect(url_for("user.user_page")+"/#change-password")


        cur.execute("UPDATE user SET password = ? WHERE pid = ?", (new_password, buyer_id))
        con.commit()
        flash("Password changed successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    finally:
        if con:
            con.close()

    return redirect(url_for("user.user_page")+"/#change-password")

@user_blueprint.route('/confirm_payment', methods=['POST'])
def confirm_payment():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to proceed to checkout.", "error")
        return redirect(url_for("login"))
    
    payment_method = request.form.get("payment_method")
    payment_items = session.get("payment_items")
        
    if not payment_items:
        flash("Your payment information is missing. Please try again.", "warning")
        return redirect(url_for("cart"))
    if not payment_method:
        flash("Please choose one of the payment options.", "warning")
        return redirect(url_for('payment_page'))
    
    con = get_connect_db()
    cur = con.cursor()
    
    # Fetch user address for validation
    cur.execute("SELECT address, phone_number, firstName, lastName FROM user WHERE pid = ?", (buyer_id,))
    user = cur.fetchone()
    user_address = user['address'] if user else None
    user_phone_number = user['phone_number'] if user else None
    buyer_name = f"{user['firstName']} {user['lastName']}"
    
    if not user_address or not user_phone_number:
       flash("You must set your address and phone number before processing payment.", "warning")
       con.close()
       return redirect(url_for('user.user_page') + '#personal-details')
    
    total_price = sum(item["quantity"] * item["price"] for item in payment_items)

    if payment_method == "e-wallet":
       
        cur.execute("SELECT * FROM user WHERE pid = ?", (buyer_id,))
        user_balance_record = cur.fetchone()
        user_balance = user_balance_record["wallet"] if user_balance_record else 0
        
        if user_balance < total_price:
            flash("Insufficient balance in your e-wallet. Please top up.", "warning")
            con.close()
            return redirect(url_for("eWallet"))
        else:
            new_balance = user_balance - total_price
            cur.execute("UPDATE user SET wallet = ? WHERE pid = ?", (new_balance, buyer_id))
             
            cur.execute(
                "INSERT INTO wallet_transaction (buyer_id, date, description, amount) VALUES (?, DATE('now'), ?, ?)",
                    (buyer_id, f"Purchase with E-Wallet: RM{total_price:.2f}", -total_price,)
            )
            
            for item in payment_items:
                try:
                    seller_id = int(item["seller_id"])
                except (KeyError, ValueError) as e:
                    seller_id = None
                
                # Fetch product name
                cur.execute("SELECT name FROM products WHERE id = ?", (item["product_id"],))
                product = cur.fetchone()
                product_name = product['name'] if product else "Unknown Product"
                
                if seller_id == None:
                     # Insert order
                    cur.execute("INSERT INTO orders (buyer_id, product_id, quantity, date, total_amount, seller_status, delivery_status, payment_method) VALUES (?, ?, ?, DATE('now'), ?, ?, ?, ?)",(buyer_id, item["product_id"], item["quantity"], (item["quantity"]*item["price"]), "Confirmed", "Shipped", "E-Wallet"))
                else:
                     # Insert order
                    cur.execute("INSERT INTO orders (buyer_id, product_id, quantity, date, total_amount, payment_method) VALUES (?, ?, ?, DATE('now'), ?, ?)",(buyer_id, item["product_id"], item["quantity"], (item["quantity"]*item["price"]), "E-Wallet"))
                
                order_id = cur.lastrowid
                
                cur.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (item["quantity"], item["product_id"]))
               
                # Construct notification messages
                seller_message = f"New order received! Order ID: {order_id}, Buyer: {buyer_name}, Product: {product_name}."
                buyer_message = f"Your purchase is confirmed! Order ID: {order_id}, Product: {product_name}, Total Amount: RM{total_price:.2f}, Payment Method: {payment_method}."

                # Send notifications
                if seller_id:
                   send_notification(con, seller_id, "New Order", seller_message)
                
                send_notification(con, buyer_id, "Purchase Confirmation", buyer_message)

            
            con.execute("DELETE FROM cart WHERE buyer_id = ?", (buyer_id,))
            
            con.commit()
            con.close()
            
            flash("Payment processed successfully with e-wallet!", "success")
            session.pop('payment_items', None) # remove the items in session
            return redirect(url_for('cart'))

    elif payment_method == "bank-card":
      
        cur.execute("SELECT * FROM user WHERE pid = ?", (buyer_id,))
        user_record = cur.fetchone()
        have_bank_card = user_record["haveBankCard"] if user_record else 0
        
        if not have_bank_card:
           con.close()
           flash("You must add a bank card before processing payment.", "warning")
           return redirect(url_for("user.user_page"))
       
        for item in payment_items:
             try:
                seller_id = int(item["seller_id"])
             except (KeyError, ValueError) as e:
                seller_id = None
             
            # Fetch product name
             cur.execute("SELECT name FROM products WHERE id = ?", (item["product_id"],))
             product = cur.fetchone()
             product_name = product['name'] if product else "Unknown Product"
             
             if seller_id == None:
                cur.execute("INSERT INTO orders (buyer_id, product_id, quantity, date, total_amount, seller_status, delivery_status, payment_method) VALUES (?, ?, ?, DATE('now'), ?, ?, ?, ?)",(buyer_id, item["product_id"], item["quantity"], (item["quantity"]*item["price"]), "Confirmed", "Shipped", "Bank Card"))
             else:
                cur.execute("INSERT INTO orders (buyer_id, product_id, quantity, date, total_amount, payment_method) VALUES (?, ?, ?, DATE('now'), ?, ?)",(buyer_id, item["product_id"], item["quantity"], (item["quantity"]*item["price"]), "Bank Card"))
             
             order_id = cur.lastrowid
             cur.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (item["quantity"], item["product_id"]))
            
              # Construct notification messages
             seller_message = f"New order received! Order ID: {order_id}, Buyer: {buyer_name}, Product: {product_name}."
             buyer_message = f"Your purchase is confirmed! Order ID: {order_id}, Product: {product_name}, Total Amount: RM{total_price:.2f}, Payment Method: {payment_method}."
              # Send notifications
             if seller_id:
                send_notification(con, seller_id, "New Order", seller_message)
             
             send_notification(con, buyer_id, "Purchase Confirmation", buyer_message)
        
        cur.execute("DELETE FROM cart WHERE buyer_id = ?", (buyer_id,))
        con.commit()
        con.close()
        
        flash("Payment processed successfully with bank card!", "success")
        session.pop('payment_items', None) # remove the items in session
        return redirect(url_for('cart'))
    
    
    return redirect(url_for('cart'))


@user_blueprint.route('/remove_from_cart/<int:cart_item_id>', methods=['POST'])
def remove_from_cart(cart_item_id):
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to modify your cart.", "danger")
        return redirect(url_for("login"))

    con = get_connect_db() 
    cur = con.cursor()
    try:
        # Check if the cart item exists and belongs to the user
        cur.execute("SELECT * FROM cart WHERE id = ? AND buyer_id = ?", (cart_item_id, buyer_id))
        cart_item = cur.fetchone()
        if not cart_item:
            flash("Cart item not found or does not belong to this user.", "warning")
            return redirect(url_for("cart"))

        # Delete the item from the cart
        cur.execute("DELETE FROM cart WHERE id = ?", (cart_item_id,))
        con.commit()

        # Update cart_item_count in the session
        if "cart_item_count" in session and session["cart_item_count"] > 0:
            session["cart_item_count"] -= 1

        flash("Item removed from cart successfully!", "success")
    except Exception as e:
        flash(f"An error occurred while removing the item from the cart: {e}", "danger")
        con.rollback() # Rollback in case of error
    finally:
         if con:
            con.close()
    
    return redirect(url_for("cart"))

@user_blueprint.route('/order_details/<int:order_id>', methods=['GET'])
def order_details(order_id):
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to view order details.", "error")
        return redirect(url_for("login"))

    con = get_connect_db()
    cur = con.cursor()

    order = cur.execute("""
            SELECT 
                o.id as order_id,
                o.buyer_id,
                o.product_id,
                o.quantity as order_quantity,
                o.date,
                o.total_amount,
                o.delivery_status,
                o.seller_status,
                o.payment_method,
                p.name as product_name,
                p.image_path as product_image_path,
                p.seller_id,
                s.name as seller_name,
                s.email as seller_email,
                s.phone_number as seller_phone
            FROM orders o
            JOIN products p ON o.product_id = p.id
            LEFT JOIN sellers s ON p.seller_id = s.id
            WHERE o.id = ? AND o.buyer_id = ?
        """, (order_id, buyer_id)).fetchone()

    if not order:
        # Check if order exists with different buyer id
        cur.execute("SELECT buyer_id FROM orders WHERE id = ?",(order_id,))
        existing_order = cur.fetchone()

        if existing_order:
             flash(f"This order does not belong to your account, buyer ID {existing_order['buyer_id']}.", "warning")
        else:
            flash("Order not found in our database.", "warning")
            
        return redirect(url_for("user_orders"))
    try:
        int(order['seller_id'])
    except (ValueError, TypeError):
        order = dict(order) # Convert to dictionary so that we can assign new key:value
        order['seller_name'] = "Admin's Choice"
        order['seller_email'] = "support@trashandtreasure.com" # Added dummy admin email
        order['seller_phone'] = "+1 (800) 123-4567" # Added dummy admin phone
        
    return render_template("order_details.html", order=order)

@user_blueprint.route("/forgot-password-user")
def forgot_password():
    flash("Future Development since we didn't state in the report.", "info")
    return redirect(url_for("login"))  # Redirect to the login page

@user_blueprint.route('/deactivate_account')
def deactivate_account():
    buyer_id = session.get("buyer_id")
    if not buyer_id:
        flash("You must be logged in to deactivate your account.", "error")
        return redirect(url_for("login"))

    con = get_connect_db()
    cur = con.cursor()
    try:
        cur.execute("DELETE FROM user WHERE pid = ?", (buyer_id,))
        con.commit()
        session.clear()  # Clear user session
        flash("Your account has been successfully deactivated.", "success")
    except Exception as e:
         flash(f"An error occurred: {e}", "danger")
         con.rollback() # Rollback in case of error
    finally:
        if con:
            con.close()

    return redirect(url_for("login"))


@user_blueprint.route("/notifications")
def notifications():
  user_id = session.get("buyer_id") or session.get("user_id")
  if not user_id:
    flash("Please log in to access this page.", "danger")
    return redirect(url_for("login"))
  
  con = get_connect_db()
  cur = con.cursor()
  notifications = cur.execute("SELECT * FROM notification WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,)).fetchall()
    # Mark notifications as read when viewed
  cur.execute("UPDATE notification SET is_read = 1 WHERE user_id = ?", (user_id,))
  con.commit()
  con.close()

  return render_template("notifications.html", notifications = notifications)


@user_blueprint.route("/cancel_order/<int:order_id>", methods=['POST'])
def cancel_order(order_id):
    if "buyer_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("login"))
    
    con = get_connect_db()
    cur = con.cursor()
    
    try:
        buyer_id = session.get("buyer_id")

        # Fetch order details
        cur.execute("""
            SELECT 
                o.buyer_id,
                o.total_amount,
                p.name AS product_name,
                p.seller_id,
                p.id AS product_id,
                o.seller_status,
                o.quantity
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.id = ? AND o.buyer_id = ?
        """, (order_id, buyer_id))
        order = cur.fetchone()

        if not order:
            flash(f"Order with ID {order_id} not found or does not belong to you.", "danger")
            return redirect(url_for("user_orders"))

        total_amount = order['total_amount']
        product_name = order['product_name']
        seller_id = order['seller_id']
        seller_status = order['seller_status']
        quantity = order['quantity']
        product_id = order["product_id"]
        
        # Credit the amount back to the buyer's e-wallet
        cur.execute(
          "UPDATE user SET wallet = wallet + ? WHERE pid = ?",
            (total_amount, buyer_id)
        )
        
        # Add a record in the transaction history
        cur.execute("""
            INSERT INTO wallet_transaction (buyer_id, date, description, amount) 
            VALUES (?, DATE('now'), ?, ?)
        """, (buyer_id, f"Refund for cancelled order of {product_name} (ID: {order_id})", total_amount))

        # Update the order status
        cur.execute("UPDATE orders SET delivery_status = 'Cancelled' WHERE id = ?", (order_id,))
        
        cur.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))
        
        con.commit()

        # Construct notification message for buyer
        cancellation_reason = "by buyer request"
        buyer_message = f"Your order of {product_name} with ID {order_id} has been cancelled {cancellation_reason}. Your refund of RM {total_amount} has been credited back to your wallet."
        
        # Send notification to buyer
        send_notification(con, buyer_id, "Order Cancelled", buyer_message)

        # Construct notification message for seller if seller status is confirmed
        if seller_status == 'Confirmed':
            seller_message = f"Your order of {product_name} with ID {order_id} has been cancelled {cancellation_reason}."
        
            # Send notification to seller
            send_notification(con, seller_id, "Order Cancelled", seller_message)

        flash("Order Cancelled Successfully, refund has been credited to your e-wallet.", "success")

    except Exception as e:
        flash(f"Error canceling the order: {e}", "danger")
        con.rollback()
    finally:
        con.close()
    
    return redirect(url_for('user_orders'))