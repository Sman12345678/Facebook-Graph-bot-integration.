from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        # Check for existing user
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already in use.', 'danger')
            return render_template('signup.html')
        if not username or not email or not password:
            flash("Please fill out all fields.", "danger")
            return render_template('signup.html')
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for('auth.login'))
    return render_template('signup.html')

def admin_login_required(f):
    from functools import wraps
    def wrap(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Admin access only!", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wraps(f)(wrap)

def login_required(f):
    from functools import wraps
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wraps(f)(wrap)
