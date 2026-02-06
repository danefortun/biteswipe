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
    pfp_file_path = db.Column(db.String(255))
    def __init__(self,name,password,email,pfp_file_path=None):
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
    if request.method == "POST":
        file = request.files["image"]
    user = users.query.filter_by(name=session['user']).first()
    try:
        # Extract extension
        extension = ''
        for i in range(len(file.filename)):
            if file.filename[i] == '.':
                extension += file.filename[i:]
                break
        
        # Build filename and path
        file_name = session['user'] + extension
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file_name)

        # Save file to disk
        file.save(filepath)

        # Update user in database
        
        if user:
            user.pfp_file_path = file_name   
            db.session.commit()

    except Exception as e:
        import traceback
        print("Error uploading file:", e)
        traceback.print_exc()

        
        

    
    return render_template("public.html",pfp=user.pfp_file_path,name=user.name)

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
        session["user"] = user

        found_user = users.query.filter_by(name=user).first()
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