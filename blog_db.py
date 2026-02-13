'''
Docstring for blog_dp
This program creates the class for the posting dataBase
It will hold tables of a string attached to a users name
'''
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from db import db
from datetime import datetime
from users_db import Users
from db import db
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

class BlogPosts(db.Model):
    __bind_key__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text)
    user_id = db.Column(db.Integer)
    time = db.Column(db.Text)

    def __init__(self,message,user_id=0):
        self.message = message
        self.user_id = user_id
        self.time = datetime.now()

    def __repr__(self):
        return f"message_id = {self.id}, user_id = {self.user_id}, message content = {self.message}, time sent = {self.time}"
    
    def message_content(self):
        user = Users.query.filter_by(id=self.user_id).first()
        return f"{user.name}: {self.message}"
if __name__ == "__main__":
    
    with app.app_context():
        posts = BlogPosts.query.all()
        print("\n--- DATABASE CONTENTS ---")
        for post in posts:
            print(post.message_content())