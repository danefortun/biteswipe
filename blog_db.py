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
    title = db.Column(db.String(100))
    content = db.Column(db.Text)

    user_id = db.Column(db.Integer)

if __name__ == "__main__":
    pass