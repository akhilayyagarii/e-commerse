from flask import Flask, render_template, request, redirect, url_for, session, flash
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from dotenv import load_dotenv
import uuid
import certifi
import os

load_dotenv()
app = Flask(_name_)

app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
db = client["shopping"]
products_col = db["products"]
users_col = db["users"]

# LOGIN
@app.route('/', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']

            if email == "pavani123@gmail.com" and password == "akhil":
                session['username'] = email
                session['is_admin'] = True
                flash('Admin login successful.')
                return redirect(url_for('admin_home'))

            user = users_col.find_one({"email": email})
            if user and check_password_hash(user['password'], password):
                session['username'] = user['email']
                session['user_id'] = str(user['_id'])
                session['is_admin'] = False
                flash('Login successful.')
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password.')
                return redirect(url_for('login'))
        return render_template('login.html')
    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return redirect(url_for('login'))

# SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    try:
        if request.method == 'POST':
            username = request.form.get('username').strip()
            email = request.form.get('email').strip().lower()
            password = request.form.get('password')
            profile_pic_url = request.form.get('profile_pic_url').strip()

            existing_user = users_col.find_one({'email': email})
            if existing_user:
                flash('Email already registered.')
                return redirect(url_for('signup'))

            hashed_password = generate_password_hash(password)
            new_user = {
                'username': username,
                'email': email,
                'password': hashed_password,
                'profile_pic_url': profile_pic_url,
                'cart': []
            }

            users_col.insert_one(new_user)
            flash('Signup successful! Please log in.')
            return redirect(url_for('login'))

        return render_template('signup.html')
    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return redirect(url_for('signup'))

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('login'))

# HOME
@app.route('/home')
def home():
    return render_template('home.html')

# PRODUCT LISTING
@app.route('/products', methods=['GET'])
def products():
    try:
        category = request.args.get('category')
        search_query = request.args.get('q')

        query = {}
        if category:
            query["category"] = category
        if search_query:
            query["name"] = {"$regex": search_query, "$options": "i"}

        products = list(products_col.find(query))

        if len(products) == 1:
            product = products[0]
            return redirect(url_for('product_detail', category=product['category'], product_id=product['id']))

        return render_template('products.html', products=products, category=category, display_category=category.title() if category else "All")
    except Exception as e:
        flash(f"Error loading products: {str(e)}")
        return redirect(url_for('home'))

# PRODUCT DETAIL
@app.route('/product/<category>/<product_id>', methods=['GET'])
def product_detail(category, product_id):
    try:
        product = products_col.find_one({"id": product_id})
        if not product:
            return "Product not found", 404
        return render_template("product_details.html", product=product)
    except Exception as e:
        flash(f"Error retrieving product: {str(e)}")
        return redirect(url_for('products', category=category))

# ADMIN PAGE
@app.route('/add_product_page')
def add_product_page():
    if not session.get('is_admin'):
        flash("Unauthorized access.")
        return redirect(url_for('login'))
    return render_template('add_product.html')

# ADD PRODUCT
@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        if not session.get('is_admin'):
            flash("Unauthorized access.")
            return redirect(url_for('login'))

        data = request.form.to_dict()
        data['id'] = str(uuid.uuid4())
        data['price'] = float(data.get('price', 0))
        data['reviews'] = []

        additional_images = data.get('additional_images', '').split(',')
        data['additional_images'] = [img.strip() for img in additional_images if img.strip()]

        products_col.insert_one(data)
        flash("Product added successfully!")
        return redirect(url_for('add_product_page'))
    except Exception as e:
        flash(f"Error adding product: {str(e)}")
        return redirect(url_for('add_product_page'))


@app.route('/add_to_cart/<product_id>/<category>', methods=['POST'])
def add_to_cart(product_id, category):
    try:
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login'))

        user = users_col.find_one({'_id': ObjectId(session['user_id'])})
        product = products_col.find_one({"id": product_id})

        if not product:
            flash("Product not found.")
            return redirect(url_for('products', category=category))

        cart = user.get("cart", [])
        existing_item = next((item for item in cart if item.get("product_id") == product["id"]), None)

        if existing_item:
            existing_item["quantity"] = existing_item.get("quantity", 1) + 1
        else:
            cart_item = {
                "_id": product["_id"],
                "product_id": product["id"],
                "name": product["name"],
                "price": float(product["price"]),
                "image_url": product.get("image_url", ""),
                "category": product["category"],
                "quantity": 1
            }
            cart.append(cart_item)

        users_col.update_one({'_id': user['_id']}, {'$set': {'cart': cart}})
        flash(f"{product['name']} added to cart!")
        return redirect(url_for('products', category=category))
    except Exception as e:
        flash("An error occurred while adding to cart.")
        return redirect(url_for('products', category=category))

@app.route('/cart', methods=['GET'])
def cart():
    try:
        if 'user_id' not in session:
            flash("Please login.")
            return redirect(url_for('login'))

        user = users_col.find_one({'_id': ObjectId(session['user_id'])})
        cart_items = user.get('cart', [])

        for item in cart_items:
            if 'quantity' not in item:
                item['quantity'] = 1

        return render_template('cart.html', cart=cart_items)
    except Exception as e:
        flash("Unable to load cart.")
        return redirect(url_for('home'))

@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    try:
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login'))

        product_id = request.form.get("_id")
        action = request.form.get("action")
        user = users_col.find_one({'_id': ObjectId(session['user_id'])})
        cart = user.get("cart", [])

        for item in cart:
            if str(item.get("_id")) == str(product_id):
                if action == "increase":
                    item["quantity"] += 1
                elif action == "decrease" and item["quantity"] > 1:
                    item["quantity"] -= 1
                break

        users_col.update_one({'_id': user['_id']}, {'$set': {'cart': cart}})
        return redirect(url_for('cart'))
    except Exception as e:
        flash("Unable to update quantity.")
        return redirect(url_for('cart'))

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))

        product_id = request.form.get('_id')
        user = users_col.find_one({'_id': ObjectId(session['user_id'])})
        cart = user.get('cart', [])

        updated_cart = [item for item in cart if str(item.get('_id', item.get('product_id'))) != str(product_id)]
        users_col.update_one({'_id': user['_id']}, {'$set': {'cart': updated_cart}})

        flash("Item removed from cart.")
        return redirect(url_for('cart'))
    except Exception as e:
        flash("Error removing item from cart.")
        return redirect(url_for('cart'))

@app.route('/submit_review/<product_id>', methods=['POST'])
def submit_review(product_id):
    try:
        if 'user_id' not in session:
            flash("Please log in to submit a review.")
            return redirect(url_for('login'))

        user = users_col.find_one({'_id': ObjectId(session['user_id'])})
        rating = int(request.form['rating'])
        comment = request.form['comment']

        review = {
            "user": user['email'],
            "rating": rating,
            "comment": comment
        }

        products_col.update_one({"id": product_id}, {"$push": {"reviews": review}})
        flash("Review submitted!")
        return redirect(url_for('product_detail', category=request.form['category'], product_id=product_id))
    except Exception as e:
        flash("Failed to submit review.")
        return redirect(url_for('home'))

@app.route('/profile')
def profile():
    try:
        if 'user_id' not in session:
            flash("Please log in to view your profile.")
            return redirect(url_for('login'))

        user = users_col.find_one({'_id': ObjectId(session['user_id'])})
        return render_template('profile.html', user=user)
    except Exception as e:
        flash("Unable to load profile.")
        return redirect(url_for('home'))

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    try:
        if 'user_id' not in session:
            flash("Please log in to edit your profile.")
            return redirect(url_for('login'))

        user = users_col.find_one({'_id': ObjectId(session['user_id'])})

        if request.method == 'POST':
            name = request.form.get('name', '')
            bio = request.form.get('bio', '')
            profile_pic_url = request.form.get('profile_pic_url', '')

            users_col.update_one(
                {'_id': user['_id']},
                {'$set': {
                    'name': name,
                    'bio': bio,
                    'profile_pic_url': profile_pic_url
                }}
            )
            flash("Profile updated successfully!")
            return redirect(url_for('profile'))

        return render_template('edit_profile.html', user=user)
    except Exception as e:
        flash("Unable to edit profile.")
        return redirect(url_for('home'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    try:
        if 'user_id' not in session:
            flash("Please log in first.")
            return redirect(url_for('login'))

        user_id = session['user_id']
        users_col.delete_one({'_id': ObjectId(user_id)})

        session.pop('user_id', None)
        flash("Your account has been deleted.")
        return redirect(url_for('signup'))
    except Exception as e:
        flash("Error deleting account.")
        return redirect(url_for('home'))

@app.route('/admin/home')
def admin_home():
    try:
        if not session.get('is_admin'):
            flash("Unauthorized access.")
            return redirect(url_for('login'))

        products = list(products_col.find())
        category_products = {}
        for product in products:
            cat = product.get('category', 'Uncategorized')
            category_products.setdefault(cat, []).append(product)

        return render_template('admin_home.html', category_products=category_products)
    except Exception as e:
        flash("Error loading admin home.")
        return redirect(url_for('home'))

@app.route('/admin/delete_product/<product_id>', methods=['POST'])
def admin_delete_product(product_id):
    try:
        if not session.get('is_admin'):
            flash("Unauthorized access.")
            return redirect(url_for('login'))

        products_col.delete_one({'_id': ObjectId(product_id)})
        flash("Product removed successfully!")
        return redirect(url_for('admin_home'))
    except Exception as e:
        flash("Failed to delete product.")
        return redirect(url_for('admin_home'))

if __name__ == '__main__':
    app.run(debug=True)