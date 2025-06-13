from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    requests = db.relationship('BotRequest', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class BotRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    fb_page_id = db.Column(db.String(128))
    fb_page_name = db.Column(db.String(255))
    system_instruction = db.Column(db.Text)
    page_access_token = db.Column(db.String(255))
    approved = db.Column(db.Boolean, default=False)
    rejected = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product_images = db.relationship('ProductImage', backref='bot_request', lazy=True)
    orders = db.relationship('Order', backref='bot_request', lazy=True)

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_request_id = db.Column(db.Integer, db.ForeignKey('bot_request.id'))
    filename = db.Column(db.String(255))
    url = db.Column(db.String(255))
    product_name = db.Column(db.String(255))

class MessageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_request_id = db.Column(db.Integer, db.ForeignKey('bot_request.id'))
    sender_psid = db.Column(db.String(128))
    message = db.Column(db.Text)
    message_type = db.Column(db.String(32))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_request_id = db.Column(db.Integer, db.ForeignKey('bot_request.id'))
    customer_psid = db.Column(db.String(128))
    product = db.Column(db.String(255))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    customer_name = db.Column(db.String(255))
    address = db.Column(db.String(255))
    contact = db.Column(db.String(100))
    status = db.Column(db.String(32), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserContext(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_psid = db.Column(db.String, unique=True, nullable=False)
    context = db.Column(db.PickleType, nullable=False)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_psid = db.Column(db.String(128))
    bot_request_id = db.Column(db.Integer, db.ForeignKey('bot_request.id'))
    product_name = db.Column(db.String(255))
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

