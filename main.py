from flask import Flask, redirect, url_for, render_template, request,session,flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class users(db.Model):
    _id = db.Column("id",db.Integer,primary_key = True)
    name = db.Column(db.String(100))
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
        user = request.form["email"]
        session["user"] = user

        found_user = users.query.filter_by(name=user).first()
        if found_user:
            session["email"] = found_user.email
        else:
            usr = users(user,email="",password='')
            db.session.add(usr)
            db.session.commit()
        flash("login Succesful")
        return redirect(url_for("home"))
    else:
        if "user" in session:
            flash("Already logged in")
            return redirect(url_for("home"))
        return render_template("login.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
    app.run(debug = True)