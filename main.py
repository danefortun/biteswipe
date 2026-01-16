from flask import Flask, redirect, url_for, render_template, request,session,flash

app = Flask(__name__)

@app.route("/index")
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/profile")
def profile():
    return render_template("public.html")

@app.route("/credits")
def credits():
    return render_template("about_us.html")

@app.route("/login")
def login():
    return render_template("login.html")

if __name__ == "__main__":
    
        
    app.run(debug = True)