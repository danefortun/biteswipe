'''
Author: Tech with Tim on YouTube
Date: 10/27/2019
Title: Flask Tutorial #1 - How to Make Websites with Python
Code version: Unspecified
Availability: https://www.youtube.com/watch?v=mqhxxeeTbu0&list=PLzMcBGfZo4-n4vJJybUVV3Un_NFS5EOgX&index=1
'''
# import flask and ability to redirect from a page
from flask import Flask, redirect, url_for

# Create webpage
app = Flask(__name__)

# Tell flask how to get to this page; 
# / will put you at top of page hierarchy
@app.route("/")
# Define pages that will be on website with functions
# This function will return what is to be displayed on page
def home():
    return "Hello lalalala<h1>heading here</h1>"

# Anything in <> after / will be passed into function as a variable
# of the same name, e.g. http://127.0.0.1:5000/user will display text
# "Hello user!"
@app.route("/<name>")
def user(name):
    return f"Hello {name}!"

# Redirect destination is set with function name of page
@app.route("/admin")
def admin():
    return redirect(url_for("home"))

# Run app
if __name__ == "__main__":
    app.run()