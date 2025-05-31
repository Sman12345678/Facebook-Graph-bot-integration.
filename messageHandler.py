from gemini_handler import get_gemini_response
from models import db, MessageLog, ProductImage, BotRequest, Order
import joblib, os

intent_clf = joblib.load('intent_model.pkl')

BACKEND_INSTRUCTION = """You are a professional business chatbot.
Always help customers, answer queries, recognize products in images, manage cart/checkout, and speak in friendly business English.
The available products with images are:
{catalog}
If the customer requests a product image, reply with the file name (no extension) exactly as in the catalog.
"""

def log_message(bot_request_id, sender_psid, message, message_type):
    msg = MessageLog(
        bot_request_id=bot_request_id,
        sender_psid=sender_psid,
        message=message,
        message_type=message_type
    )
    db.session.add(msg)
    db.session.commit()

def get_history(bot_request_id):
    logs = MessageLog.query.filter_by(bot_request_id=bot_request_id).order_by(MessageLog.timestamp).all()
    return [{'role': 'user' if l.message_type == 'user' else 'bot', 'message': l.message} for l in logs]

def get_product_context(bot_request):
    imgs = ProductImage.query.filter_by(bot_request_id=bot_request.id).all()
    return [f"{img.product_name}: {img.url}" for img in imgs]

def classify_intent(text):
    return intent_clf.predict([text])[0]

def handle_message(sender_psid, message, bot_request, image=None, context=None):
    if context is None:
        context = {}
    history = get_history(bot_request.id)
    product_list = get_product_context(bot_request)
    catalog = "\n".join(product_list)
    intent = classify_intent(message)
    # Example command support
    if message.strip().lower() == "/viewcart":
        try:
            from CMD.view_cart import execute
            return execute(sender_psid, bot_request.id)
        except Exception as e:
            return "Error displaying your cart."
    # handle product image request
    if intent == "product_image":
        for prod_img in bot_request.product_images:
            if prod_img.product_name.lower() in message.lower():
                send_image_fb(sender_psid, prod_img.url, bot_request.page_access_token)
                log_message(bot_request.id, sender_psid, f"Sent image: {prod_img.product_name}", "bot")
                return f"Here is the image of {prod_img.product_name}"
        return "Sorry, I couldn't find that product image."
    # order flow (multi-turn)
    if context.get('flow') == 'order':
        if context['step'] == 1:
            context['product'] = message
            context['step'] = 2
            return "How many units do you want to order?"
        elif context['step'] == 2:
            context['quantity'] = message
            context['step'] = 3
            return "Please provide your name."
        elif context['step'] == 3:
            context['customer_name'] = message
            context['step'] = 4
            return "Your address?"
        elif context['step'] == 4:
            context['address'] = message
            context['step'] = 5
            return "Your contact (phone/email)?"
        elif context['step'] == 5:
            context['contact'] = message
            summary = (f"Order summary:\nProduct: {context['product']}\n"
                       f"Quantity: {context['quantity']}\nName: {context['customer_name']}\n"
                       f"Address: {context['address']}\nContact: {context['contact']}\n"
                       "Reply 'confirm' to place your order.")
            context['step'] = 6
            return summary
        elif context['step'] == 6 and message.strip().lower() == "confirm":
            order = Order(
                bot_request_id=bot_request.id,
                customer_psid=sender_psid,
                product=context['product'],
                quantity=int(context['quantity']),
                customer_name=context['customer_name'],
                address=context['address'],
                contact=context['contact'],
                status="placed"
            )
            db.session.add(order)
            db.session.commit()
            send_order_email_to_owner(bot_request, order)
            context.clear()
            return f"✅ Your order (ID: {order.id}) has been placed! We will contact you soon."
    # order detection (start flow)
    if intent == "order":
        context['flow'] = 'order'
        context['step'] = 1
        return "What product would you like to order?"
    # fallback to Gemini
    reply = get_gemini_response(
        user_message=message,
        system_instruction=bot_request.system_instruction,
        product_context=catalog,
        backend_instruction=BACKEND_INSTRUCTION.format(catalog=catalog),
        history=history,
        image=image
    )
    log_message(bot_request.id, sender_psid, message, "user")
    log_message(bot_request.id, sender_psid, reply, "bot")
    return reply

def send_image_fb(recipient_psid, image_url, page_access_token):
    params = {'access_token': page_access_token}
    data = {
        'recipient': {'id': recipient_psid},
        'message': {
            'attachment': {
                'type': 'image',
                'payload': {'url': image_url, 'is_reusable': True}
            }
        }
    }
    import requests
    requests.post('https://graph.facebook.com/v22.0/me/messages', params=params, json=data)

def send_order_email_to_owner(bot_request, order):
    import smtplib
    from email.mime.text import MIMEText
    owner_email = bot_request.user.email
    subject = f"New Order Received (Order ID: {order.id})"
    body = (
        f"New order placed via your bot '{bot_request.fb_page_name}'.\n\n"
        f"Order ID: {order.id}\n"
        f"Product: {order.product}\n"
        f"Quantity: {order.quantity}\n"
        f"Customer Name: {order.customer_name}\n"
        f"Contact: {order.contact}\n"
        f"Address: {order.address}\n"
        f"Placed at: {order.created_at}\n\n"
        f"View in admin panel for more details."
    )
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = "noreply@yourdomain.com"
    msg['To'] = owner_email
    with smtplib.SMTP('localhost') as s:
        s.sendmail(msg['From'], [owner_email], msg.as_string())
