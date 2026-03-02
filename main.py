from flask import Flask, redirect, url_for, render_template, request,session,flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from blog_db import *
from users_db import *
from config import Config
from db import db
import os
#for the below to work, make sure you make a file called apiKey.py and make a variable called key
try:
    from apiKey import key
    import requests
except:
    print("NO API KEY FOUND, PLEASE LOOK AT LINE 8 OF MAIN.PY")

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")

# Make sure the folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)




@app.route("/index", methods=["POST", "GET"])
@app.route("/", methods=["POST", "GET"])
def home():
    if 'email' in session:
        user = Users.query.filter_by(email=session['email']).first()
    else: redirect(url_for("login"))
    # 1. Capture the data from the HTML 'name' attributes
    raw_lat = request.form.get('latitude')
    raw_lng = request.form.get('longitude')
    if "email" not in session:
        return redirect(url_for("login"))

    user = Users.query.filter_by(email=session["email"]).first()

    # Handle location POST
    if request.method == "POST":
        raw_lat = request.form.get("latitude")
        raw_lng = request.form.get("longitude")

        if raw_lat and raw_lng:
            try:
                user.latitude = float(raw_lat)
                user.longitude = float(raw_lng)
                db.session.commit()
                flash("Location saved successfully!")
            except Exception as e:
                flash("Error saving to database")
                print(e)

            return redirect(url_for("home"))

    filters = session.get("filters", {})

    print("Current filters:", filters)

    return render_template("cards.html", filters=filters)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "email" not in session:
        return redirect(url_for("login"))

    user = Users.query.filter_by(email=session['email']).first()
    if not user:
        return "User not found"

    if request.method == "POST":
        try:
            action = request.form.get("action")  # hidden field in form

            # ----------------- Upload profile picture -----------------
            if action == "upload_pic":
                file = request.files.get("image")  # safe: won't raise KeyError
                if file:
                    extension = os.path.splitext(file.filename)[1]
                    file_name = session['email'] + extension
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file_name)
                    file.save(filepath)
                    user.pfp_file_path = file_name
                    db.session.commit()

            # ----------------- Update bio -----------------
            elif action == "update_bio":
                new_bio = request.form.get("bio")
                if new_bio is not None:
                    user.bio = new_bio
                    db.session.commit()
            elif action == "update_name":
                new_name = request.form.get("name")
                if new_name is not None:
                    user.name = new_name
                    db.session.commit()

        except Exception as e:
            import traceback
            print("Error in POST:", e)
            traceback.print_exc()

    
    return render_template("public.html",u=user,interests=["this is a placeholder!"])


@app.route("/credits")
def credits():
    if "email" not in session:
        return render_template("login.html")
    return render_template("about_us.html")

@app.route("/login",methods=["Post","Get"])
def login():
    if request.method == "POST":
        session.permanent = False
        user = request.form["email"]
        password = request.form["pass"]
        session['email'] = user

        found_user = Users.query.filter_by(email=user).first()
        if found_user:
            session["email"] = found_user.email
            session['id']=found_user.id
        else:
            usr = Users(user,email=user,password=password)
            db.session.add(usr)
            db.session.commit()
        flash("login Succesful")
        return redirect(url_for("home"))
    else:
        if "email" in session:
            flash("Already logged in")
            return redirect(url_for("home"))
        return render_template("login.html")

@app.route('/chat',methods = ["Post","Get"])
def blog():
    #this function will show the last 20 messages sent
    if not 'email' in session and not 'id' in session:
        return redirect(url_for("login"))
    
    
    if request.method == "POST":
            
        message = request.form["message"]
        if message != '':
            new_msg = BlogPosts(message,session.get("id"))
            db.session.add(new_msg)
            db.session.commit()
            print("hello world")
            return redirect(url_for("blog"))
        
    

    return render_template("blog.html")

@app.route("/get_posts")
def get_posts():
    posts = BlogPosts.query.order_by(BlogPosts.id.desc()).limit(10).all()
    
    return {
        "posts": [
            {
                
                "message": p.message,
                "user_id": Users.query.get(p.user_id).name if Users.query.get(p.user_id) else "Unknown"
            } for p in posts
        ]
    }

@app.route('/logout')
def logout():
    if 'email' in session:
        session.clear()
    return redirect(url_for("login"))
        
@app.route('/get_restaurant')
def get_info():
    user= Users.query.filter_by(email=session['email']).first()
    if user.latitude != None and 'email' in session:
        
        url = "https://places.googleapis.com/v1/places:searchText"
        search_headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.photos"
        }
        payload = {
            "textQuery": "restaurant", 
            "locationBias": {
                "circle": {
                    "center": {
                        "latitude": user.latitude,
                        "longitude": user.longitude
                    },
                    "radius": 2000.0 # Floats are safer
                }
            }
        }
        response = requests.post(url, json=payload, headers=search_headers)
        data = response.json()
        results = data.get('places', [])
        print(results)
        return {
        "places": [
            {
                
                "name":r['displayName'],
                "place":r['id'],
                "photo":f"https://places.googleapis.com/v1/{r['photos'][0]['name']}/media?maxHeightPx=500&key={key}"
                
                
            } for r in results
        ]
    }

        return redirect(url_for("login"))

@app.route("/save_filters", methods=["POST"])
def save_filters():
    if "email" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received"}), 400

    session["filters"] = data
    session.modified = True

    return jsonify({"status": "success"})

@app.route("/get_filters")
def get_filters():
    return jsonify(session.get("filters", {}))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
    app.run(debug = True)

