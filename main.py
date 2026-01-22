from flask import Flask, redirect, url_for, render_template, request,session,flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class users(db.Model):
    _id = db.Column("id",db.Integer,primary_key = True)
    userName = db.Column(db.String(100))
    password = db.Column(db.String(100))
    email = db.Column(db.String(100))
    def __init__(self,name,password,email):
        self.__name = name
        self.__email = email
        self.__password = password

@app.route("/index")
@app.route("/")
def home():
    if "user" not in session:
        return render_template("login.html")
    return render_template("cards.html")

@app.route("/profile")
def profile():
    return render_template("public.html")

@app.route("/credits")
def credits():
    return render_template("about_us.html")

@app.route("/login",methods=["Post","Get"])
def login():
    if request.method == "POST":
        session.permanent = True
        address = request.form["email"]
        session["email"] = address

        found_user = users.query.filter_by(email=address).first()
    if "email" not in session:
        return render_template("login.html")
    else:
        return render_template

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
    app.run(debug = True)