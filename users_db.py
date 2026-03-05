'''
Docstring for users_db
This program creates the class for the user dataBase
It will hold tables of a the users user id, their name, their email, their password, their bio, and the image path of their pfp
'''
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from db import db
import sqlite3
import os

class Users(db.Model):
    id = db.Column("id",db.Integer,primary_key = True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    email = db.Column(db.String(100))
    bio = db.Column(db.String(200))
    pfp_file_path = db.Column(db.String(255))
    latitude = db.Column(db.Float())
    longitude = db.Column(db.Float())
    saved = db.Column(db.String())
    def __init__(self,name,password,email,bio='this is a placeholder!',pfp_file_path='transparentnewdefaultpicture.png'):
        self.bio = bio
        self.name = name
        self.email = email
        self.password = password
        self.pfp_file_path = pfp_file_path
    def __repr__(self):
        return f"<User id={self.id}, name={self.name}, email={self.email}, location={self.latitude},{self.latitude}"

    def get_saved_restaurants(self):
        return  f"<User id={self.id}, saved={self.saved}"

if __name__ == "__main__":
    from db import db
    from config import Config

    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    with app.app_context():
        users = Users.query.all()
        print("\n--- DATABASE CONTENTS ---")
        for user in users:
            print(user)
        for user in users:
            print(user.get_saved_restaurants())