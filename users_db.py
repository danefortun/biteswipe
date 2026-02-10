'''
Docstring for users_db
This program creates the class for the user dataBase
It will hold tables of a the users user id, their name, their email, their password, their bio, and the image path of their pfp
'''
from flask_sqlalchemy import SQLAlchemy
from db import db

class Users(db.Model):
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


if __name__ == "__main__":
    pass