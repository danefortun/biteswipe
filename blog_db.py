'''
Docstring for blog_dp
This program creates the class for the posting dataBase
It will hold tables of a string attached to a users name
'''
from flask_sqlalchemy import SQLAlchemy
from db import db
class BlogPosts(db.Model):
    __bind_key__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text)
    user_id = db.Column(db.Integer)

    def __init__(self,message,user_id):
        self.message = message
        self.user_id = user_id

if __name__ == "__main__":
    pass