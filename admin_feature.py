from flask import Blueprint, redirect, url_for, render_template, request, session, flash
from db import get_connect_db, send_notification, seller_database

admin_blueprint = Blueprint("admin", __name__, template_folder="templates")


@admin_blueprint.route("/login", methods=["POST", "GET"])
def login():
    admins = [
        {"Username": "admin1", "Password" : "a1", "Name" : "AdminName1"},
        {"Username": "admin2", "Password" : "a2", "Name" : "AdminName2"},
        {"Username": "admin3", "Password" : "a3", "Name" : "AdminName3"}
    ]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "Login":
            username = request.form["username"]
            password = request.form["password"]
            
            for admin in admins:
                if admin["Username"] == username and admin["Password"] == password:
                    session["admin_id"] = admin["Username"] 
                    session["admin_name"] = admin["Name"] 
                    return redirect(url_for("admin.dashboard"))
                
            flash("Invalid username and password", "danger")
            return render_template("adminlogin_page.html")
        elif action == "Back":
            return redirect(url_for("home"))

    return render_template("adminlogin_page.html")

@admin_blueprint.route("/profile")
def admin_profile():
    if "admin_id" in session:
        admin_id = session["admin_id"]
        admin_name = session["admin_name"] 
        return render_template("admin_profile.html", admin_id=admin_id, admin_name=admin_name)
    else:
        flash("Please log in to access the admin account.", "danger")
        return redirect(url_for("admin.login"))

@admin_blueprint.route("/")
def dashboard():
    if "admin_id" not in session:
        flash("Please log in to access the admin account.", "danger")
        return redirect(url_for("admin.login"))

    try:
        con = get_connect_db()
        cur = con.cursor()

        # Fetch total user count
        cur.execute("SELECT COUNT(*) FROM user")
        total_users = cur.fetchone()[0]

        # Fetch total logistics member count
        cur.execute("SELECT COUNT(*) FROM member")
        total_logistics = cur.fetchone()[0]

        # Fetch total order count
        cur.execute("SELECT COUNT(*) FROM orders")
        total_orders = cur.fetchone()[0]

        # Fetch pending seller approval count
        cur.execute("SELECT COUNT(*) FROM seller_registration WHERE status = 'Pending'")
        pending_approvals = cur.fetchone()[0]

    except Exception as e:
        flash(f"Error fetching dashboard data: {e}", "danger")
        total_users = 0
        total_logistics = 0
        total_orders = 0
        pending_approvals = 0
    finally:
        if con:
            con.close()

    return render_template(
        "admin_page.html",
        admin=session["admin_name"],
        total_users=total_users,
        total_logistics=total_logistics,
        total_orders=total_orders,
        pending_approvals=pending_approvals
    )       

@admin_blueprint.route('/hire_member', methods=["GET", "POST"])
def hire_member():
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

    if request.method == "POST":
        try:
          fname = request.form["first_name"]
          lname = request.form["last_name"]
          email = request.form["email"]
          password = request.form["password"]
        
          con = get_connect_db() # Initialize the connection here
          cur = con.cursor()
          cur.execute("SELECT * FROM member WHERE email = ?", (email,))
          member = cur.fetchone()
        
          if member:  # If a record is found
            flash("Email already exists!", "danger")
            return redirect(url_for("admin.hire_member"))
          cur.execute("INSERT INTO member (firstName, lastName, email, password) VALUES (?, ?, ?, ?)",(fname, lname, email, password),)
          con.commit()
          flash("Account Created Successfully!", "success")
          return redirect(url_for("admin.logistic_management"))
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")
        finally:
            if con:  # Check if con is initialized
                con.close()

    return render_template("hire_member.html")

@admin_blueprint.route("/logistic_management")
def logistic_management():
    if "admin_id" not in session:  # Check if admin is logged in
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    cur.execute("SELECT pid, firstName, lastName, email FROM member")
    members = cur.fetchall()
    con.close()
    members = [{"id": member[0], "first_name": member[1], "last_name": member[2], "email": member[3]} for member in members]

    return render_template("logistic_management.html", members=members,)

@admin_blueprint.route("/inventory") 
def inventory():
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    con.close()

    return render_template('inventory.html', products=products,)
    
    
@admin_blueprint.route('/user_management')
def user_management():
    if "admin_id" not in session:  # Check if admin is logged in
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    users = cur.execute("SELECT pid, firstName, lastName, email FROM user").fetchall()
    sellers = cur.execute("SELECT id, name, email FROM sellers").fetchall()
    con.close()

    # Convert users to dictionaries
    users = [{"id": user[0], "first_name": user[1], "last_name": user[2], "email": user[3]} for user in users]
    sellers = [{"id": seller[0], "name": seller[1], "email": seller[2]} for seller in sellers]
    return render_template(
        'user_management.html', 
        users=users,
        sellers=sellers
    )
 
@admin_blueprint.route("/view_user/<int:id>", methods=["POST", "GET"])
def view_user(id):
  con = get_connect_db()
  cur = con.cursor()
  try:
    cur.execute("SELECT * FROM user WHERE pid = ?", (id,))
    user = cur.fetchone()
    
    if not user:
         flash("User not found.", "warning")
         return redirect(url_for("admin.user_management"))
    
    cur.execute("""
    SELECT 
        o.id,
        o.date,
        o.total_amount,
        o.delivery_status,
        p.name AS product_name
    FROM orders o
    JOIN products p ON o.product_id = p.id
    WHERE o.buyer_id = ?
  """, (id,))
    orders = cur.fetchall()
        
     # Convert the fetched orders into a list of dictionaries
    orders = [{"id": order[0], "date": order[1], "total_amount": order[2], "delivery_status":order[3], "product_name": order[4] } for order in orders]
   
  except Exception as e:
       flash(f"An error occurred: {e}", "danger")
  finally:
    con.close()
      
  return render_template("view_user_details.html", user=user, orders=orders)

@admin_blueprint.route("/remove_user/<id>", methods=["POST", "GET"])
def delete_user(id):
    try:
        con = get_connect_db()
        cur = con.cursor()
        
        cur.execute("SELECT * FROM user WHERE pid = ?", (id,))
        user = cur.fetchone()
        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("admin.user_management"))
        
        # Check if the user is a seller
        is_seller = user["isSeller"]
        if is_seller == 1:
            cur.execute("DELETE FROM sellers WHERE id = ?", (id,))
        
        cur.execute("DELETE FROM user WHERE pid = ?", (id,))
        
        con.commit()
        flash("User deleted successfully!", "success")
        
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        
    finally:
        if con:
            con.close()
            
    return redirect(url_for("admin.user_management"))

@admin_blueprint.route("/seller_approval")
def seller_approval():
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

    con = get_connect_db()
    cur = con.cursor()
    cur.execute("""
        SELECT sr.id, u.firstName, u.lastName, u.email 
        FROM seller_registration sr 
        JOIN user u ON sr.id = u.pid 
        WHERE sr.status = 'Pending'
    """)
    pending_sellers = cur.fetchall()
    con.close()

    return render_template("seller_approval.html", pending_sellers=pending_sellers)

@admin_blueprint.route("/view_seller/<int:seller_id>", methods=["POST", "GET"])
def view_seller(seller_id):
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

    con = get_connect_db()
    cur = con.cursor() 
    cur.execute("""
        SELECT sr.*, u.firstName, u.lastName, u.email 
        FROM seller_registration sr 
        JOIN user u ON sr.id = u.pid 
        WHERE sr.id = ?
    """, (seller_id,))
    seller_details = cur.fetchone()
    
    if not seller_details:
        flash("Seller not found.", "danger") 
        return redirect(url_for("admin.user_management"))
    
    cur.execute("SELECT * FROM products WHERE seller_id = ?", (seller_id,))
    seller_products = cur.fetchall()

    cur.execute("""
        SELECT 
            o.id,
            o.delivery_status
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE p.seller_id = ?
    """, (seller_id,))
    seller_orders = cur.fetchall()

    con.close()
    return render_template("view_seller_details.html", seller_details=seller_details, seller_products = seller_products, seller_orders=seller_orders) 

@admin_blueprint.route("/view_seller_approval/<int:seller_id>", methods=["POST"])
def view_seller_approval(seller_id):
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

    con = get_connect_db()
    cur = con.cursor() 
    cur.execute("""
        SELECT sr.*, u.firstName, u.lastName, u.email 
        FROM seller_registration sr 
        JOIN user u ON sr.id = u.pid 
        WHERE sr.id = ?
    """, (seller_id,))
    seller_details = cur.fetchone()
    
    if not seller_details:
        flash("Seller not found.", "danger") 
        return redirect(url_for("admin.seller_approval"))
    
    cur.execute("SELECT * FROM products WHERE seller_id = ?", (seller_id,))
    seller_products = cur.fetchall()

    cur.execute("""
        SELECT 
            o.id,
            o.delivery_status
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE p.seller_id = ?
    """, (seller_id,))
    seller_orders = cur.fetchall()

    con.close()
    return render_template("view_seller_approval_details.html", seller_details=seller_details, seller_products = seller_products, seller_orders=seller_orders) 

@admin_blueprint.route("/approve_seller/<int:seller_id>", methods=["POST"])
def approve_seller(seller_id):
    try:
        con = get_connect_db()
        cur = con.cursor()
        cur.execute("UPDATE seller_registration SET status = 'Approved' WHERE id = ?", (seller_id,))
        con.commit()
        
        cur.execute("UPDATE user SET isSeller = 1 WHERE pid = ?", (seller_id,))
        con.commit()
        
        seller_database(seller_id)
        con.commit()
        
        flash("Seller application approved!", "success")
        send_notification(con, seller_id, "Seller Application Approved", "Congratulations! Your seller application has been approved. You can now start listing your products.")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    finally:
        con.close()

    return redirect(url_for("admin.seller_approval"))

@admin_blueprint.route("/reject_seller/<int:seller_id>", methods=["POST"])
def reject_seller(seller_id):
    try:
        con = get_connect_db()
        cur = con.cursor()
        cur.execute("UPDATE seller_registration SET status = 'Rejected' WHERE id = ?", (seller_id,))
        
        cur.execute("DELETE FROM seller_registration WHERE id = ?", (seller_id,))  # Delete each rejected seller
            
        con.commit()
        
        flash("Seller application rejected.", "info")
        send_notification(con, seller_id, "Seller Application Rejected", "Your seller application has been rejected. You can review the requirements and apply again.")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    finally:
        con.close()

    return redirect(url_for("admin.seller_approval"))

@admin_blueprint.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin.login"))


@admin_blueprint.route("/view_order_details/<int:order_id>", methods=["GET"])
def view_order_details(order_id):
    admin_id = session["admin_id"]
    if not admin_id:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

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
                s.phone_number as seller_phone,
                u.firstName as buyer_name,
                u.email as buyer_email,
                 u.address as buyer_address
            FROM orders o
            JOIN products p ON o.product_id = p.id
            LEFT JOIN sellers s ON p.seller_id = s.id
            LEFT JOIN user u ON o.buyer_id = u.pid
            WHERE o.id = ?
        """, (order_id,)).fetchone()
    
    if not order:
         flash("Order not found in our database.", "warning")
         return redirect(url_for("admin.dashboard"))

    try:
        int(order['seller_id'])
    except (ValueError, TypeError):
         order = dict(order) # Convert to dictionary so that we can assign new key:value
         order['seller_name'] = "Admin's Choice"
         order['seller_email'] = "support@trashandtreasure.com" # Added dummy admin email
         order['seller_phone'] = "+1 (800) 123-4567" # Added dummy admin phone
    
    con.close()

    return render_template("view_order_details.html", order=order)


@admin_blueprint.route("/view_member_details/<int:member_id>", methods=["GET"])
def view_member_details(member_id):
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

    con = get_connect_db()
    cur = con.cursor()

    cur.execute("SELECT * FROM member WHERE pid = ?", (member_id,))
    member = cur.fetchone()

    if not member:
        flash("Member not found.", "warning")
        return redirect(url_for("admin.logistic_management"))

    # Fetch delivery assignments
    delivery_assignments = cur.execute("""
        SELECT 
            ad.order_id,
            o.delivery_status,
            CASE
                 WHEN ad.assigned_member_id = ? THEN 'Assigned Courier'
                 WHEN ad.status_updated_member_id = ? THEN 'Updated Status'
            END AS worked_type
         FROM assign_delivery ad
        JOIN orders o ON ad.order_id = o.id
        WHERE ad.assigned_member_id = ? OR ad.status_updated_member_id = ?
    """, (member_id, member_id, member_id, member_id, )).fetchall()
    
      # Fetch pickup assignments
    pickup_assignments = cur.execute("""
         SELECT 
            pr.order_id,
            o.delivery_status,
            CASE
                WHEN pr.assigned_member_id = ? THEN 'Assigned Courier'
                WHEN pr.status_updated_member_id = ? THEN 'Updated Status'
            END AS worked_type
        FROM pickup_request pr
        JOIN orders o ON pr.order_id = o.id
        WHERE pr.assigned_member_id = ? OR pr.status_updated_member_id = ?
    """, (member_id, member_id, member_id, member_id,)).fetchall()

    con.close()

    return render_template("view_member_details.html", member=member, delivery_assignments = delivery_assignments, pickup_assignments = pickup_assignments)


@admin_blueprint.route("/delete_member/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))

    con = get_connect_db()
    cur = con.cursor()

    try:
        # Check if the member exists
        cur.execute("SELECT * FROM member WHERE pid = ?", (member_id,))
        member = cur.fetchone()
        if not member:
            flash("Member not found.", "warning")
            return redirect(url_for("admin.logistic_management"))

        # Delete the member
        cur.execute("DELETE FROM member WHERE pid = ?", (member_id,))
        con.commit()
        flash("Member removed successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        con.rollback()
    finally:
        con.close()
    return redirect(url_for("admin.logistic_management"))

@admin_blueprint.route("/notify_product/<int:product_id>", methods=["GET"])
def notify_product_form(product_id):
    if "admin_id" not in session:
         flash("Please log in to access this page.", "danger")
         return redirect(url_for("admin.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    product = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    con.close()
    if not product:
         flash("Product not found.", "warning")
         return redirect(url_for("admin.inventory"))
     
    return render_template("notify_modal.html", product=product)

@admin_blueprint.route("/send_notification/<int:product_id>", methods=["POST"])
def send_notification_to_seller(product_id):
   if "admin_id" not in session:
        flash("Please log in to access this page.", "danger")
        return redirect(url_for("admin.login"))
    
   message = request.form.get("message")
   if not message:
        flash("Please add a message", "danger")
        return redirect(url_for("admin.notify_product_form", product_id=product_id))
    
   con = get_connect_db()
   cur = con.cursor()
   try:
        # Get the seller ID from the product.
        cur.execute("SELECT seller_id, name FROM products WHERE id = ?", (product_id,))
        product = cur.fetchone()
        if not product:
            flash("Product not found.", "warning")
            return redirect(url_for("admin.inventory"))
        
        seller_id = product["seller_id"]
        product_name = product["name"]
        
        send_notification(con, seller_id, f"Notification from Admin for product {product_name}", message)
        
        flash("Notification sent successfully", "success")
   except Exception as e:
       flash(f"An error occurred: {e}", "danger")
   finally:
        con.close()
    
   return redirect(url_for("admin.inventory"))

@admin_blueprint.route("/add_product_page", methods=["GET", "POST"])
def add_product_page():
    if "admin_id" not in session:
      flash("Please log in to access this page.", "danger")
      return redirect(url_for("admin.login"))
    
    return render_template('admin_add_product.html')


@admin_blueprint.route("/view_product_details/<int:product_id>", methods=["GET"])
def view_product_details(product_id):
    if "admin_id" not in session:
         flash("Please log in to access this page.", "danger")
         return redirect(url_for("admin.login"))
    
    con = get_connect_db()
    cur = con.cursor()
    
    # Fetch the product
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cur.fetchone()
    
    if not product:
         flash("Product not found.", "warning")
         return redirect(url_for("admin.inventory"))
    try:
           cur.execute("SELECT id, name, email, phone_number FROM sellers WHERE id = ?", (product['seller_id'],))
           seller = cur.fetchone()

    except Exception as e:
          seller = None #If Seller ID is not present it is the Admin choice so seller value becomes None and set accordingly at jinja.

    
     # Fetch product order details
    product_orders = cur.execute("""
        SELECT
        o.id,
        o.date,
        o.quantity,
        o.delivery_status
        FROM orders o
        WHERE o.product_id = ?
    """, (product_id,)).fetchall()

    con.close()
      
    return render_template("view_product_details.html", product=product, seller=seller, product_orders = product_orders)



@admin_blueprint.route("/view_logistic_reports/<int:member_id>", methods=["GET"])
def view_logistic_reports(member_id):
   if "admin_id" not in session:
      flash("Please log in to access this page.", "danger")
      return redirect(url_for("admin.login"))
    
   con = get_connect_db()
   cur = con.cursor()
   
   cur.execute("SELECT * FROM member WHERE pid = ?", (member_id,))
   member = cur.fetchone()
    
   if not member:
        flash("Member not found.", "danger")
        return redirect(url_for("admin.logistic_management"))
      
  
   reports = cur.execute("SELECT * FROM logistic_report WHERE member_id = ?", (member_id,)).fetchall()

   con.close()
   
   return render_template("view_logistic_reports.html", member=member, reports=reports)


@admin_blueprint.route("/view_report_details/<int:report_id>", methods=["GET"])
def view_report(report_id):
    if "admin_id" not in session:
         flash("Please log in to access this page.", "danger")
         return redirect(url_for("admin.login"))

    con = get_connect_db()
    cur = con.cursor()
    report = cur.execute("SELECT * FROM logistic_report WHERE id = ?", (report_id,)).fetchone()
    
    if not report:
      flash("Report not found.", "danger")
      return redirect(url_for("admin.view_logistic_reports"))
    
    member_data = cur.execute("SELECT firstName,lastName from member where pid = ?", (report["member_id"],)).fetchone()
    con.close()
    return render_template("view_report_details.html", report=report, member_name= f"{member_data['firstName']} {member_data['lastName']}")