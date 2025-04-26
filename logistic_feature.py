from flask import Blueprint, redirect, url_for, render_template, request, session, flash
from db import get_connect_db, generate_tracking_code, send_notification

logistic_blueprint = Blueprint("logistic", __name__, template_folder="templates")

@logistic_blueprint.route("/logisticlogin", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        con = get_connect_db()
        cur=con.cursor()
        cur.execute("SELECT * FROM member WHERE email = ? and password = ?", (email, password)) #checking 
        data = cur.fetchone() 
        con.close()

        if data:
            session["member_name"] = data["firstName"]  
            session["member_id"] = data["pid"]   
            return redirect(url_for("logistic.dashboard"))
        else:
            flash("Invalid username or password", "danger")
            return render_template("logisticlogin_page.html")
        
    return render_template("logisticlogin_page.html")

@logistic_blueprint.route("/forgot-password")
def forgot_password():
    flash("Contact T&T Support Team. Check out the contact page.", "info")
    return redirect(url_for("logistic.login"))  # Redirect to the login page



@logistic_blueprint.route("/profile")
def member_profile(): 
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

    con = get_connect_db()
    cur = con.cursor()
    
    member_data = cur.execute("SELECT * FROM member WHERE pid = ?", (member_id,)).fetchone()
    con.close()
    
    if not member_data:
        flash("Member profile not found.", "danger")
        return redirect(url_for("logistic.dashboard"))

    return render_template("logistic_profile.html", member=member_data)


@logistic_blueprint.route("/")
def dashboard():    
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access the admin account.", "danger")
        return redirect(url_for("logistic.login"))
    
    con = get_connect_db()
    cur = con.cursor()

    # Fetch Pickups Today Count
    pickup_count = cur.execute("""
        SELECT COUNT(*)
        FROM pickup_request pr
        JOIN orders o ON pr.order_id = o.id
        WHERE o.delivery_status != 'Delivered' AND o.delivery_status != 'Cancelled'
    """).fetchone()[0]

    # Fetch Deliveries Today Count
    delivery_count = cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status = 'Shipped'").fetchone()[0]

     # Fetch Pending Orders Count
    pending_order_count = cur.execute("""
        SELECT COUNT(*) FROM orders WHERE delivery_status != 'Delivered' AND delivery_status != 'Cancelled'
    """).fetchone()[0]

    con.close()

    return render_template("logistic_page.html", pickup_count=pickup_count, delivery_count=delivery_count, pending_order_count=pending_order_count)
    
@logistic_blueprint.route("/pickup_manage")
def pickup_management():
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    
    pickup_requests = cur.execute("""
        SELECT 
            pr.id,
            pr.order_id,
            pr.courier,
            pr.seller_address,
            pr.buyer_address,
            pr.assigned_status,
            o.delivery_status
        FROM pickup_request pr
        JOIN orders o ON pr.order_id = o.id
        WHERE o.delivery_status != 'Delivered' AND o.delivery_status != 'Cancelled'
    """).fetchall()

    return render_template("pickup_management.html", pickup_requests=pickup_requests)

@logistic_blueprint.route("/delivery_manage")
def delivery_management():
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))
    con = get_connect_db()
    cur = con.cursor()
    
    shipped_orders = cur.execute("""
           SELECT 
                o.id as order_id,
                o.product_id,
                p.name as product_name,
                o.delivery_status,
                ad.condition AS assign_delivery_condition
            FROM orders o
            JOIN products p ON o.product_id = p.id
            LEFT JOIN assign_delivery ad ON o.id = ad.order_id
            WHERE o.delivery_status = 'Shipped'
        """).fetchall()
    
    return render_template("delivery_management.html", shipped_orders=shipped_orders)

@logistic_blueprint.route("/order_manage")
def order_management():
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))
    
    con = get_connect_db()
    cur = con.cursor()

    all_orders = cur.execute("""
        SELECT 
            o.id,
            o.product_id,
            o.buyer_id,
            o.delivery_status,
            ad.courier as courier
        FROM orders o
        LEFT JOIN assign_delivery ad ON o.id = ad.order_id
    """).fetchall()

    return render_template("order_management.html", all_orders=all_orders)

@logistic_blueprint.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("logistic.login"))

@logistic_blueprint.route("/pickup_details/<int:pickup_id>", methods=['GET', 'POST'])
def pickup_details(pickup_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

    con = get_connect_db()
    cur = con.cursor()
    
    pickup_details = cur.execute("SELECT * FROM pickup_request WHERE id = ?", (pickup_id,)).fetchone()
    if not pickup_details:
        flash("Pickup request not found.", "danger")
        return redirect(url_for("logistic.pickup_management"))
    
    order_details = cur.execute("SELECT * FROM orders WHERE id = ?", (pickup_details['order_id'],)).fetchone()
    if not order_details:
        flash("Order details not found for this pickup request.", "danger")
        return redirect(url_for("logistic.pickup_management"))
    
    # Fetch delivery status
    delivery_status = cur.execute("SELECT delivery_status FROM orders WHERE id = ?", (pickup_details['order_id'],)).fetchone()

    if delivery_status:
      pickup_details = dict(pickup_details)
      pickup_details['delivery_status'] = delivery_status['delivery_status']

    seller_details = cur.execute("""
        SELECT s.*
        FROM sellers s
        JOIN products p ON s.id = p.seller_id
        JOIN orders o ON p.id = o.product_id
        WHERE o.id = ?
    """, (pickup_details['order_id'],)).fetchone()
    if not seller_details:
        flash("Seller details not found for this pickup request.", "danger")
        return redirect(url_for("logistic.pickup_management"))
    
    buyer_details = cur.execute("SELECT * FROM user WHERE pid = ?", (order_details['buyer_id'],)).fetchone()
    if not buyer_details:
        flash("Buyer details not found for this pickup request.", "danger")
        return redirect(url_for("logistic.pickup_management"))

    return render_template(
        "pickup_details.html",
        pickup_details=pickup_details,
        order_details=order_details,
        seller_details=seller_details,
        buyer_details=buyer_details
    )

@logistic_blueprint.route("/assign_courier/<int:pickup_id>", methods=['POST'])
def assign_courier(pickup_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

    if request.method == 'POST':
        courier = request.form['courier']
        
        con = get_connect_db()
        cur = con.cursor()
        
        try:
            # Fetch pickup request details
            cur.execute("SELECT order_id, seller_id FROM pickup_request WHERE id = ?", (pickup_id,))
            pickup_data = cur.fetchone()

            if not pickup_data:
                flash("Pickup request not found.", "danger")
                return redirect(url_for('logistic.pickup_management'))

            order_id = pickup_data['order_id']
            seller_id = pickup_data['seller_id']

            # Fetch buyer_id from the orders table
            cur.execute("SELECT buyer_id FROM orders WHERE id = ?", (order_id,))
            order_data = cur.fetchone()

            if not order_data:
                flash("Order not found.", "danger")
                return redirect(url_for('logistic.pickup_management'))

            buyer_id = order_data['buyer_id']

            # Update pickup request with courier and assigned status
            cur.execute("UPDATE pickup_request SET courier = ?, assigned_status = 'Assigned', assigned_member_id = ? WHERE id = ?", (courier, member_id, pickup_id))
            con.commit()

             # Generate tracking code
            tracking_code = generate_tracking_code(order_id)

            # Construct notification messages
            seller_message = f"Your Order with ID {order_id} has been assigned to {courier} courier for pickup. Your tracking code is: {tracking_code}."
            buyer_message = f"Your Order with ID {order_id} has been assigned to {courier} courier for delivery. Your tracking code is: {tracking_code}."


            # Send notifications to seller and buyer
            send_notification(con, seller_id, f"Courier Assigned - {courier}", seller_message)
            send_notification(con, buyer_id, f"Courier Assigned - {courier}", buyer_message)


            flash("Courier assigned successfully.", "success")
            return redirect(url_for('logistic.pickup_management'))
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")
            con.rollback()
        finally:
            if con:
                con.close()

    flash("Invalid request method", 'danger')
    return redirect(url_for('logistic.pickup_management'))



@logistic_blueprint.route("/delivery_details/<int:order_id>", methods=['GET', 'POST'])
def delivery_details(order_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

    con = get_connect_db()
    cur = con.cursor()

    # Fetch order details
    order_details = cur.execute("""
        SELECT 
            o.id as order_id,
            o.product_id,
            p.name as product_name,
            o.quantity,
            o.total_amount,
            o.buyer_id,
            o.delivery_status
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.id = ?
    """, (order_id,)).fetchone()

    if not order_details:
        flash("Order not found.", "danger")
        return redirect(url_for("logistic.delivery_management"))

     # Fetch buyer details
    buyer_details = cur.execute("SELECT * FROM user WHERE pid = ?", (order_details['buyer_id'],)).fetchone()
    if not buyer_details:
        flash("Buyer details not found for this order.", "danger")
        return redirect(url_for("logistic.delivery_management"))

    # Fetch seller details
    seller_details = cur.execute("""
        SELECT s.*
        FROM sellers s
        JOIN products p ON s.id = p.seller_id
        JOIN orders o ON p.id = o.product_id
        WHERE o.id = ?
    """, (order_id,)).fetchone()
    
    if not seller_details:
         # If seller_details is None, consider it as admin's product
        seller_details = {
            'id': 'Admin',
            'name': "Admin's Choice",
            'email': "support@trashandtreasure.com",
            'phone_number': "+1 (800) 123-4567"
        }
    else:
        try:
            int(seller_details['id'])
        except (ValueError, TypeError):
            seller_details = {
                'id': 'Admin',
                'name': "Admin's Choice",
                'email': "support@trashandtreasure.com",
                'phone_number': "+1 (800) 123-4567"
            }
    
    # Fetch assign delivery info if exists
    assign_delivery_info = cur.execute("SELECT * FROM assign_delivery WHERE order_id = ?", (order_id,)).fetchone()


    con.close()

    return render_template(
        "delivery_details.html",
        order_details=order_details,
        buyer_details=buyer_details,
        seller_details=seller_details,
        assign_delivery_info = assign_delivery_info
    )


@logistic_blueprint.route("/assign_delivery/<int:order_id>", methods=['POST'])
def assign_delivery(order_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

    if request.method == 'POST':
        pickup_date = request.form['pickup_date']
        arrival_date = request.form['arrival_date']
        condition = request.form['condition']
        description = request.form['description']
        courier = request.form['courier']
        
        con = get_connect_db()
        cur = con.cursor()

        # Fetch seller id from order table
        order_details = cur.execute("SELECT product_id, buyer_id FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order_details:
            flash("Order not found to get the seller and buyer ID.", "danger")
            con.close()
            return redirect(url_for("logistic.delivery_details", order_id=order_id))
        
        product_details = cur.execute("SELECT seller_id FROM products WHERE id = ?", (order_details['product_id'],)).fetchone()
        if not product_details:
            flash("Product not found to get the seller ID.", "danger")
            con.close()
            return redirect(url_for("logistic.delivery_details", order_id=order_id))
        seller_id = product_details['seller_id']
        buyer_id = order_details['buyer_id']

        try:
            cur.execute("""
                INSERT INTO assign_delivery (order_id, seller_id, condition, courier, arrival_date, pickup_date, description, assigned_member_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_id, seller_id, condition, courier, arrival_date, pickup_date, description, member_id))
            con.commit()

            # Generate tracking code
            tracking_code = generate_tracking_code(order_id)


            # Construct notification messages
            seller_message = f"Your Order with ID {order_id} has been assigned to {courier} courier for delivery. Pickup date: {pickup_date}, Arrival date: {arrival_date}. Tracking code: {tracking_code}."
            buyer_message = f"Your Order with ID {order_id} has been assigned to {courier} courier for delivery. Pickup date: {pickup_date}, Arrival date: {arrival_date}. Tracking code: {tracking_code}."

            # Send notifications to seller and buyer
            send_notification(con, seller_id, f"Delivery Assigned - {courier}", seller_message)
            send_notification(con, buyer_id, f"Delivery Assigned - {courier}", buyer_message)


            flash("Delivery assigned successfully.", "success")
        except Exception as e:
            flash(f"Error assigning delivery: {e}", "danger")
            con.rollback()
        finally:
           con.close()

    return redirect(url_for("logistic.delivery_details", order_id=order_id))


@logistic_blueprint.route("/update_delivery_status/<int:order_id>", methods=['POST'])
def update_delivery_status(order_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    
    try:
        # Fetch order details including seller id and total amount
        cur.execute("""
            SELECT 
                o.total_amount,
                p.seller_id,
                p.name AS product_name,
                o.buyer_id
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.id = ?
        """, (order_id,))
        order = cur.fetchone()

        if not order:
            flash(f"Order with ID {order_id} not found.", "danger")
            return redirect(url_for("logistic.order_management"))
        
        total_amount = order['total_amount']
        seller_id = order['seller_id']
        product_name = order['product_name']
        buyer_id = order['buyer_id']


        # Check if seller_id is a valid integer before crediting
        try:
            int(seller_id)
            # Credit the amount to the seller's wallet
            cur.execute(
                "UPDATE user SET wallet = wallet + ? WHERE pid = ?",
                (total_amount, seller_id)
            )
            
            # Add a record in the transaction history
            cur.execute("""
                INSERT INTO wallet_transaction (buyer_id, date, description, amount) 
                VALUES (?, DATE('now'), ?, ?)
            """, (seller_id, f"Credit for delivered order of {product_name} (ID: {order_id})", total_amount))
            
            flash("Seller has been credited", 'success')
        except (ValueError, TypeError):
            # If seller_id is not an integer, it's considered admin's product so skip money transfer
            flash(f"Skipping credit transfer for admin's product (Order ID: {order_id}).", "info")
    
        # Update the delivery status to 'Delivered'
        cur.execute("UPDATE orders SET delivery_status = 'Delivered' WHERE id = ?", (order_id,))

        # Fetch the assign_delivery record id
        assign_delivery_data = cur.execute("SELECT id FROM assign_delivery WHERE order_id = ?", (order_id,)).fetchone()
        if assign_delivery_data:
            assign_delivery_id = assign_delivery_data['id']
            cur.execute("UPDATE assign_delivery SET delivered_date = DATE('now'), status_updated_member_id = ? WHERE id = ?", (member_id, assign_delivery_id,))

        con.commit()

        # Construct notification messages
        seller_message = f"Your product {product_name} with ID {order_id} has been successfully delivered."
        seller_credit_message = f"The amount of RM {total_amount} for the order of {product_name} with ID {order_id} has been credited to your account."
        buyer_message = f"Your order of {product_name} with ID {order_id} has been successfully delivered."


        # Send notifications to seller and buyer
        send_notification(con, seller_id, "Delivery Completed", seller_message)
        send_notification(con, seller_id, "Payment Credited", seller_credit_message)
        send_notification(con, buyer_id, "Delivery Completed", buyer_message)


        flash("Delivery status updated to 'Delivered'.", "success")

    except Exception as e:
        flash(f"Error updating delivery status: {e}", "danger")
        con.rollback()
    finally:
        con.close()
    
    return redirect(url_for("logistic.delivery_details", order_id=order_id))


@logistic_blueprint.route("/update_pickup_status/<int:pickup_id>", methods=['POST'])
def update_pickup_status(pickup_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))
    
    con = get_connect_db()
    cur = con.cursor()

    try:
        # Fetch order ID from pickup_request table
        pickup_details = cur.execute("SELECT order_id, seller_id FROM pickup_request WHERE id = ?", (pickup_id,)).fetchone()
        if not pickup_details:
            flash("Pickup request not found.", "danger")
            con.close()
            return redirect(url_for("logistic.pickup_details", pickup_id=pickup_id))
        order_id = pickup_details['order_id']
        seller_id = pickup_details['seller_id']

        # Fetch buyer_id from order table
        order_data = cur.execute("SELECT buyer_id FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order_data:
            flash("Order not found.", "danger")
            con.close()
            return redirect(url_for("logistic.pickup_details", pickup_id=pickup_id))
        buyer_id = order_data['buyer_id']


        # Update delivery status in orders table
        cur.execute("UPDATE orders SET delivery_status = 'Shipped' WHERE id = ?", (order_id,))
        
        # Update pickup_request table
        cur.execute("UPDATE pickup_request SET status_updated_member_id = ? WHERE id = ?", (member_id, pickup_id,))
        
        con.commit()

        # Construct notification messages
        seller_message = f"Your order with ID {order_id} has been shipped."
        buyer_message = f"Your order with ID {order_id} has been shipped."

         # Send notifications to seller and buyer
        send_notification(con, seller_id, "Product Shipped", seller_message)
        send_notification(con, buyer_id, "Product Shipped", buyer_message)

        flash("Delivery status updated to 'Shipped'.", "success")

    except Exception as e:
        flash(f"Error updating delivery status: {e}", "danger")
    finally:
        con.close()
    
    return redirect(url_for("logistic.pickup_details", pickup_id=pickup_id))


@logistic_blueprint.route("/order_details_logistics/<int:order_id>", methods=['GET'])
def order_details_logistics(order_id):
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

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
            p.name as product_name,
            p.image_path as product_image_path,
            p.price as product_price,
            s.id as seller_id,
            s.name as seller_name,
            s.email as seller_email,
            s.phone_number as seller_phone,
            u.firstName as buyer_name,
            u.email as buyer_email,
            u.address as buyer_address,
            ad.pickup_date,
            ad.arrival_date,
            ad.delivered_date,
            m1.firstName as delivery_assigned_member_name,
            m1.pid as delivery_assigned_member_id,
            m2.firstName as delivery_status_updated_member_name,
            m2.pid as delivery_status_updated_member_id,
            pr.courier,
            m3.firstName as pickup_assigned_member_name,
            m3.pid as pickup_assigned_member_id,
            m4.firstName as pickup_status_updated_member_name,
            m4.pid as pickup_status_updated_member_id
        FROM orders o
        JOIN products p ON o.product_id = p.id
        LEFT JOIN sellers s ON p.seller_id = s.id
        LEFT JOIN user u ON o.buyer_id = u.pid
        LEFT JOIN assign_delivery ad ON o.id = ad.order_id
        LEFT JOIN pickup_request pr ON o.id = pr.order_id
        LEFT JOIN member m1 ON ad.assigned_member_id = m1.pid
        LEFT JOIN member m2 ON ad.status_updated_member_id = m2.pid
        LEFT JOIN member m3 ON pr.assigned_member_id = m3.pid
        LEFT JOIN member m4 ON pr.status_updated_member_id = m4.pid
        WHERE o.id = ?
        """, (order_id,)).fetchone()
    if not order:
        flash("Order not found in our database.", "warning")
        return redirect(url_for("logistic.order_management"))
    try:
        int(order['seller_id'])
    except (ValueError, TypeError):
        order = dict(order) # Convert to dictionary so that we can assign new key:value
        order['seller_name'] = "Admin's Choice"
        order['seller_email'] = "support@trashandtreasure.com" # Added dummy admin email
        order['seller_phone'] = "+1 (800) 123-4567" # Added dummy admin phone
    con.close()

    return render_template("order_details_logistics.html", order=order)


@logistic_blueprint.route("/cancel_order/<int:order_id>", methods=['POST'])
def cancel_order(order_id):
    if "member_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    
    try:
        member_id = session.get("member_id")

        # Fetch order details
        cur.execute("""
            SELECT 
                o.buyer_id,
                o.quantity,
                o.total_amount,
                p.name AS product_name,
                p.seller_id,
                p.id AS product_id,
                o.seller_status
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.id = ?
        """, (order_id,))
        order = cur.fetchone()

        if not order:
            flash(f"Order with ID {order_id} not found.", "danger")
            return redirect(url_for("logistic.order_management"))

        buyer_id = order['buyer_id']
        total_amount = order['total_amount']
        product_name = order['product_name']
        seller_id = order['seller_id']
        seller_status = order['seller_status']
        quantity = order['quantity']
        product_id = order['product_id'] 
        
        # Credit the amount back to the buyer's e-wallet
        cur.execute(
          "UPDATE user SET wallet = wallet + ? WHERE pid = ?",
            (total_amount, buyer_id)
        )
        
        cur.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))


         # Add a record in the transaction history
        cur.execute("""
            INSERT INTO wallet_transaction (buyer_id, date, description, amount) 
            VALUES (?, DATE('now'), ?, ?)
        """, (buyer_id, f"Refund for cancelled order of {product_name} (ID: {order_id})", total_amount))


       # Update the order status
        cur.execute("UPDATE orders SET delivery_status = 'Cancelled' WHERE id = ?", (order_id,))

        # Update status_updated_member_id in assign_delivery
        cur.execute("""
            UPDATE assign_delivery
            SET status_updated_member_id = ?, delivered_date = DATE('now')
            WHERE order_id = ?
        """, (member_id, order_id))
        
        con.commit()

        # Construct notification message for buyer
        cancellation_reason = "due to not enough information or undeliverable items"
        buyer_message = f"Your order of {product_name} with ID {order_id} has been cancelled {cancellation_reason}. Your refund of RM {total_amount} has been credited back to your wallet."
        
        # Send notification to buyer
        send_notification(con, buyer_id, "Order Cancelled", buyer_message)

        # Construct notification message for seller if seller status is confirmed
        if seller_status == 'Confirmed':
            seller_message = f"Your order of {product_name} with ID {order_id} has been cancelled {cancellation_reason}."
        
             # Send notification to seller
            send_notification(con, seller_id, "Order Cancelled", seller_message)


        flash("Order Cancelled Successfully, buyer has been refunded.", "success")

    except Exception as e:
        flash(f"Error canceling the order: {e}", "danger")
        con.rollback()
    finally:
        con.close()
    
    return redirect(url_for('logistic.order_details_logistics',order_id = order_id ))


@logistic_blueprint.route("/report_page", methods=['GET', 'POST'])
def logistics_reports():
    member_id = session.get("member_id")
    if not member_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("logistic.login"))

    con = get_connect_db()
    cur = con.cursor()
    reports = cur.execute("SELECT * FROM logistic_report WHERE member_id = ?", (member_id,)).fetchall()
    con.close()

    if request.method == 'POST':
        report_type = request.form['report-type']
        start_date = request.form.get('start-date')
        end_date = request.form.get('end-date')
        total_orders = request.form.get('total-orders',0) #Default to 0 if not set
        successful_deliveries = request.form.get('successful',0) #Default to 0 if not set
        delayed_deliveries = request.form.get('delayed',0) #Default to 0 if not set
        issues_reported = request.form.get('issues',0) #Default to 0 if not set

        con = get_connect_db()
        cur = con.cursor()

        cur.execute("""
            INSERT INTO logistic_report (member_id, report_type, start_date, end_date, total_orders, successful_deliveries, delayed_deliveries, issues_reported, report_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, DATE('now'))
        """, (member_id, report_type, start_date, end_date, total_orders, successful_deliveries, delayed_deliveries, issues_reported))
        con.commit()
        con.close()
        flash("Report generated and saved successfully.", "success")
        return redirect(url_for("logistic.logistics_reports"))

    return render_template("logistics_reports.html", reports=reports)

@logistic_blueprint.route("/view_report/<int:report_id>")
def view_report(report_id):
    member_id = session.get("member_id")
    if not member_id:
         flash("Please log in to access this page.", "danger")
         return redirect(url_for("logistic.login"))

    con = get_connect_db()
    cur = con.cursor()
    report = cur.execute("SELECT * FROM logistic_report WHERE id = ? AND member_id = ?", (report_id, member_id)).fetchone()
    con.close()
    
    if not report:
        flash("Report not found.", "danger")
        return redirect(url_for("logistic.logistics_reports"))
    return render_template("view_report.html", report=report)

