from flask import Flask, redirect, url_for, render_template, request,session,flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

class users(db.Model):
    id = db.Column("id",db.Integer,primary_key = True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    email = db.Column(db.String(100))
    bio = db.Column(db.String(200))
    pfp_file_path = db.Column(db.String(255))
    def __init__(self,name,password,email,bio='this is a placeholder!',pfp_file_path='transparentnewdefaultpicture.png'):
        self.bio = bio
        self.name = name
        self.email = email
        self.password = password
        self.pfp_file_path = pfp_file_path

@app.route("/index")
@app.route("/")
def home():
    if "user" not in session:
        return render_template("login.html")
    return render_template("cards.html")

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user" not in session:
        return redirect(url_for("login"))

    user = users.query.filter_by(email=session['user']).first()
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
                    file_name = session['user'] + extension
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
    if "user" not in session:
        return render_template("login.html")
    return render_template("about_us.html")

@app.route("/login",methods=["Post","Get"])
def login():
    if request.method == "POST":
        session.permanent = False
        user = request.form["email"]
        password = request.form["pass"]
        session['email'] = user.email

        found_user = users.query.filter_by(email=user).first()
        if found_user:
            session["email"] = found_user.email
        else:
            usr = users(user,email=user,password=password)
            db.session.add(usr)
            db.session.commit()
        flash("login Succesful")
        return redirect(url_for("home"))
    else:
        if "user" in session:
            flash("Already logged in")
            return redirect(url_for("home"))
        return render_template("login.html")

@app.route('/logout')
def logout():
    if 'user' in session:
        session.clear()
        return redirect(url_for("login"))
        

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
    app.run(debug = True)