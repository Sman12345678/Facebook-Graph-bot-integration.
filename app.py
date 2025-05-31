import os
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from models import db, User, BotRequest, ProductImage, Order
from auth import auth_bp, login_required, admin_login_required
from facebook import get_pages, exchange_code_for_token
from messageHandler import handle_message
from werkzeug.utils import secure_filename
from autopost import start_autopost

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///site.db")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "supersecret")
db.init_app(app)
app.register_blueprint(auth_bp)

@app.before_first_request
def ensure_admin():
    db.create_all()
    admin = User.query.filter_by(username="SULEIMAN").first()
    if not admin:
        admin = User(username="SULEIMAN", email="admin@site.com", is_admin=True)
        admin.set_password("ALPHAMETHANE")
        db.session.add(admin)
        db.session.commit()

@app.route('/')
@login_required
def dashboard():
    return render_template('index.html', user=session['username'], is_admin=session.get('is_admin'))

@app.route('/facebook/login')
@login_required
def facebook_login():
    fb_oauth_url = f"https://www.facebook.com/v22.0/dialog/oauth?client_id={os.environ.get('FB_APP_ID')}&redirect_uri={os.environ.get('FB_REDIRECT_URI')}&scope=pages_show_list,pages_messaging"
    return redirect(fb_oauth_url)

@app.route('/facebook/callback')
@login_required
def facebook_callback():
    code = request.args.get('code')
    access_token = exchange_code_for_token(code)
    session['fb_access_token'] = access_token
    pages = get_pages(access_token)
    session['fb_pages'] = pages
    return redirect(url_for('select_page'))

@app.route('/pages', methods=['GET', 'POST'])
@login_required
def select_page():
    pages = session.get('fb_pages', [])
    if request.method == 'POST':
        selected_page_id = request.form['page_id']
        selected_page = next((p for p in pages if p['id'] == selected_page_id), None)
        if not selected_page:
            flash("Page not found.", "danger")
            return redirect(url_for('select_page'))
        session['selected_page_id'] = selected_page['id']
        session['selected_page_name'] = selected_page['name']
        session['selected_page_access_token'] = selected_page['access_token']
        return redirect(url_for('system_instruction'))
    return render_template('pages.html', pages=pages)

@app.route('/system-instruction', methods=['GET', 'POST'])
@login_required
def system_instruction():
    if request.method == 'POST':
        bot_request = BotRequest(
            user_id=session['user_id'],
            fb_page_id=session['selected_page_id'],
            fb_page_name=session['selected_page_name'],
            system_instruction=request.form['instruction'],
            page_access_token=session['selected_page_access_token'],
        )
        db.session.add(bot_request)
        db.session.commit()
        files = request.files.getlist("product_images")
        names = request.form.getlist("product_names")
        for file, name in zip(files, names):
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                img = ProductImage(
                    bot_request_id=bot_request.id,
                    filename=filename,
                    url=url_for('uploaded_file', filename=filename, _external=True),
                    product_name=name
                )
                db.session.add(img)
        db.session.commit()
        flash("Bot request submitted. You will be notified after approval.", "info")
        return redirect(url_for('dashboard'))
    page_id = session.get('selected_page_id')
    page_name = session.get('selected_page_name')
    return render_template('system_instruction.html', page_id=page_id, page_name=page_name)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/my-bots')
@login_required
def my_bots():
    bot_requests = BotRequest.query.filter_by(user_id=session['user_id']).all()
    return render_template('my_bots.html', bot_requests=bot_requests)

@app.route('/admin')
@admin_login_required
def admin_panel():
    pending = BotRequest.query.filter_by(approved=False, rejected=False).all()
    approved = BotRequest.query.filter_by(approved=True).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin.html', pending=pending, approved=approved, orders=orders)

@app.route('/admin/approve/<int:bot_request_id>')
@admin_login_required
def approve_bot(bot_request_id):
    bot = BotRequest.query.get(bot_request_id)
    bot.approved = True
    db.session.commit()
    start_autopost(bot.fb_page_id, bot.page_access_token)
    flash("Bot approved!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/reject/<int:bot_request_id>')
@admin_login_required
def reject_bot(bot_request_id):
    bot = BotRequest.query.get(bot_request_id)
    bot.rejected = True
    db.session.commit()
    flash("Bot rejected!", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if token == os.environ.get('FB_VERIFY_TOKEN'):
            return challenge
        return "Verification failed", 403
    data = request.get_json()
    for entry in data.get('entry', []):
        for event in entry.get('messaging', []):
            sender_psid = event['sender']['id']
            page_id = entry.get('id')
            bot_request = BotRequest.query.filter_by(fb_page_id=page_id, approved=True).first()
            if not bot_request:
                continue
            context = {}
            if 'postback' in event and event['postback'].get('payload') == 'GET_STARTED_PAYLOAD':
                reply = "Welcome! How can I help you? (Type /help)"
                messageHandler.send_image_fb(sender_psid, reply, bot_request.page_access_token)
            elif 'message' in event:
                text = event['message'].get('text')
                if 'attachments' in event['message']:
                    for att in event['message']['attachments']:
                        if att['type'] == 'image':
                            img_url = att['payload']['url']
                            import requests
                            img_data = requests.get(img_url).content
                            reply = handle_message(sender_psid, "image", bot_request, image=img_data, context=context)
                            messageHandler.send_image_fb(sender_psid, reply, bot_request.page_access_token)
                elif text:
                    reply = handle_message(sender_psid, text, bot_request, context=context)
                    messageHandler.send_image_fb(sender_psid, reply, bot_request.page_access_token)
    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
