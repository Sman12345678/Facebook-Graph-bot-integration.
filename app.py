import os
import logging
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from models import db, User, BotRequest, ProductImage, Order
from auth import auth_bp, login_required, admin_login_required
from facebook import get_pages, exchange_code_for_token, subscribe_page
from messageHandler import handle_message, send_text_fb, send_image_by_attachment_id
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

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# =================== Powerful Logging Setup ===================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)
webhook_logger = logging.getLogger("webhook")
webhook_logger.propagate = False

class EmojiStreamHandler(logging.StreamHandler):
    LEVEL_EMOJIS = {
        logging.DEBUG: "🐛",
        logging.INFO: "ℹ️",
        logging.WARNING: "⚠️",
        logging.ERROR: "❌",
        logging.CRITICAL: "🔥",
    }
    def emit(self, record):
        emoji = self.LEVEL_EMOJIS.get(record.levelno, "")
        record.msg = f"{emoji} {record.msg}"
        super().emit(record)

for h in webhook_logger.handlers[:]:
    webhook_logger.removeHandler(h)
webhook_logger.addHandler(EmojiStreamHandler())

def mask_token(token):
    if not token or len(token) < 10:
        return token
    return token[:4] + "*" * (len(token) - 8) + token[-4:]

with app.app_context():
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
    fb_oauth_url = (
        f"https://www.facebook.com/v22.0/dialog/oauth"
        f"?client_id={os.environ.get('FB_APP_ID')}"
        f"&redirect_uri={os.environ.get('FB_REDIRECT_URI')}"
        f"&scope=pages_show_list,pages_messaging,pages_read_engagement,pages_manage_metadata"
    )
    webhook_logger.info(f"Facebook OAuth URL generated: {fb_oauth_url}")
    return redirect(fb_oauth_url)
    
@app.route('/facebook/callback')
@login_required
def facebook_callback():
    code = request.args.get('code')
    webhook_logger.info(f"Received Facebook code: {code}")
    access_token = exchange_code_for_token(code)
    webhook_logger.info(f"Exchanged code for access token: {mask_token(access_token)}")
    session['fb_access_token'] = access_token
    pages = get_pages(access_token)
    webhook_logger.info(f"Fetched pages: {pages}")
    session['fb_pages'] = pages
    return redirect(url_for('select_page'))

@app.route('/pages', methods=['GET', 'POST'])
@login_required
def select_page():
    pages = session.get('fb_pages', [])
    webhook_logger.info(f"Pages in session for selection: {pages}")
    if request.method == 'POST':
        selected_page_id = request.form['page_id']
        selected_page = next((p for p in pages if p['id'] == selected_page_id), None)
        webhook_logger.info(f"User selected page: {selected_page}")
        if not selected_page:
            flash("Page not found.", "danger")
            return redirect(url_for('select_page'))
        session['selected_page_id'] = selected_page['id']
        session['selected_page_name'] = selected_page['name']
        session['selected_page_access_token'] = selected_page['access_token']
        webhook_logger.info(f"Session updated with page ID: {selected_page['id']}, name: {selected_page['name']}, access_token: {mask_token(selected_page['access_token'])}")
        try:
            result = subscribe_page(selected_page['id'], selected_page['access_token'])
            webhook_logger.info(f"Subscribed page {selected_page['id']} to webhook: {result}")
        except Exception as e:
            webhook_logger.error(f"Failed to subscribe page to webhook: {e}")
            flash("Failed to subscribe page to webhook. Please contact support.", "danger")
            return redirect(url_for('select_page'))
        return redirect(url_for('system_instruction'))
    return render_template('pages.html', pages=pages)

@app.route('/system-instruction', methods=['GET', 'POST'])
@login_required
def system_instruction():
    if request.method == 'POST':
        webhook_logger.info(f"System instruction form: {request.form}\nFiles: {request.files}")
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
                webhook_logger.info(f"Product image saved: {filename}, name: {name}, url: {img.url}")
        db.session.commit()
        webhook_logger.info(f"BotRequest created: {bot_request}")
        flash("Bot request submitted. You will be notified after approval.", "info")
        return redirect(url_for('dashboard'))
    page_id = session.get('selected_page_id')
    page_name = session.get('selected_page_name')
    return render_template('system_instruction.html', page_id=page_id, page_name=page_name)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    webhook_logger.info(f"Serving uploaded file: {filename}")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/my-bots')
@login_required
def my_bots():
    bot_requests = BotRequest.query.filter_by(user_id=session['user_id']).all()
    webhook_logger.info(f"User {session['user_id']} bots: {bot_requests}")
    return render_template('my_bots.html', bot_requests=bot_requests)

@app.route('/admin')
@admin_login_required
def admin_panel():
    pending = BotRequest.query.filter_by(approved=False, rejected=False).all()
    approved = BotRequest.query.filter_by(approved=True).all()
    rejected = BotRequest.query.filter_by(rejected=True).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    webhook_logger.info(f"Admin panel loaded. Pending: {len(pending)}, Approved: {len(approved)}, Rejected: {len(rejected)}, Orders: {len(orders)}")
    return render_template('admin.html', pending=pending, approved=approved, rejected=rejected, orders=orders)

@app.route('/admin/approve/<int:bot_request_id>')
@admin_login_required
def approve_bot(bot_request_id):
    bot = db.session.get(BotRequest, bot_request_id)
    bot.approved = True
    db.session.commit()
    webhook_logger.info(f"BotRequest approved: {bot_request_id} for page {bot.fb_page_id} with token {mask_token(bot.page_access_token)}")
    start_autopost(bot.fb_page_id, bot.page_access_token)
    flash("Bot approved!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/reject/<int:bot_request_id>')
@admin_login_required
def reject_bot(bot_request_id):
    bot = BotRequest.query.get(bot_request_id)
    bot.rejected = True
    db.session.commit()
    webhook_logger.info(f"BotRequest rejected: {bot_request_id}")
    flash("Bot rejected!", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        webhook_logger.info(f"Webhook GET called with token: {token} and challenge: {challenge}")
        if token == os.environ.get('FB_VERIFY_TOKEN'):
            webhook_logger.info("Webhook verification passed! 🚦")
            return challenge
        webhook_logger.warning("Webhook verification failed! 🚫")
        return "Verification failed", 403
    data = request.get_json()
    webhook_logger.info(f"Received webhook event! 📩\nFull Data: {data}")
    for entry in data.get('entry', []):
        webhook_logger.info(f"Processing entry: {entry}")
        for event in entry.get('messaging', []):
            sender_psid = event['sender']['id']
            page_id = entry.get('id')
            webhook_logger.info(f"New message event from sender_psid: {sender_psid} on page_id: {page_id}")
            bot_request = BotRequest.query.filter_by(fb_page_id=page_id, approved=True).first()
            if not bot_request:
                webhook_logger.warning(f"No approved bot for page_id: {page_id} 🚷")
                continue
            webhook_logger.info(f"BotRequest found: id={bot_request.id}, user_id={bot_request.user_id}, page_access_token={mask_token(bot_request.page_access_token)}")
            context = {}
            if 'postback' in event and event['postback'].get('payload') == 'GET_STARTED_PAYLOAD':
                webhook_logger.info(f"GET_STARTED_PAYLOAD received from {sender_psid} 🚀")
                send_text_fb(sender_psid, "Welcome! How can I help you? (Type /help)", bot_request.page_access_token)
            elif 'message' in event:
                text = event['message'].get('text')
                if 'attachments' in event['message']:
                    for att in event['message']['attachments']:
                        webhook_logger.info(f"Received attachment from {sender_psid}: {att}")
                        if att['type'] == 'image':
                            img_url = att['payload']['url']
                            import requests
                            img_data = requests.get(img_url).content
                            webhook_logger.info(f"Downloading image from URL: {img_url} 🖼️")
                            reply_type, reply_content = handle_message(sender_psid, "image", bot_request, image=img_data, context=context)
                            if reply_type == "image":
                                webhook_logger.info(f"Sending image with attachment_id: {reply_content} to {sender_psid} 📷 using page_access_token={mask_token(bot_request.page_access_token)}")
                                send_image_by_attachment_id(sender_psid, reply_content, bot_request.page_access_token)
                            else:
                                webhook_logger.info(f"Sending text to {sender_psid}: {reply_content} 💬 using page_access_token={mask_token(bot_request.page_access_token)}")
                                send_text_fb(sender_psid, reply_content, bot_request.page_access_token)
                elif text:
                    webhook_logger.info(f"Received text from {sender_psid}: {text} 📝")
                    reply_type, reply_content = handle_message(sender_psid, text, bot_request, context=context)
                    if reply_type == "image":
                        webhook_logger.info(f"Sending image with attachment_id: {reply_content} to {sender_psid} 📷 using page_access_token={mask_token(bot_request.page_access_token)}")
                        send_image_by_attachment_id(sender_psid, reply_content, bot_request.page_access_token)
                    else:
                        webhook_logger.info(f"Sending text to {sender_psid}: {reply_content} 💬 using page_access_token={mask_token(bot_request.page_access_token)}")
                        send_text_fb(sender_psid, reply_content, bot_request.page_access_token)
    webhook_logger.info("Webhook event processing complete! ✅")
    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
