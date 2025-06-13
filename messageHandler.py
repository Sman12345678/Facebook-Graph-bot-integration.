import os
import re
from io import BytesIO
from gemini_handler import get_gemini_response
from models import db, MessageLog, ProductImage, BotRequest, Order, CartItem
import joblib
from CMD import view_cart
intent_clf = joblib.load('intent_model.pkl')

BACKEND_INSTRUCTION = """You are a professional business chatbot.
Always help customers, answer queries, recognize products in images, manage cart/checkout, and speak in friendly business English.
The available products in your catalog are:
****
{catalog}
****
If a user asks for a product image, check your catalog. If it exists, reply with just {{"product_image": product name}}, where product name is the matching product.
******
If the user wants to buy/order any product, reply in the format:  
{{order: product name}}

Only reply with this format when the user's message clearly contains the product name.  
If it’s unclear or missing, ask the user to provide the product name first.
******
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

def send_text_fb(recipient_psid, text, page_access_token):
    import requests
    api_url = f"https://graph.facebook.com/v22.0/me/messages"
    params = {'access_token': page_access_token}
    data = {
        'recipient': {'id': recipient_psid},
        'message': {'text': text}
    }
    response = requests.post(api_url, params=params, json=data)
    print("send_text_fb response:", response.status_code, response.text)

def upload_image_to_facebook(image_path, page_access_token):
    import requests
    api_url = f"https://graph.facebook.com/v22.0/me/message_attachments"
    params = {"access_token": page_access_token}
    with open(image_path, "rb") as f:
        files = {'filedata': f}
        data = {
            'message': '{"attachment":{"type":"image", "payload":{}}}'
        }
        response = requests.post(api_url, params=params, data=data, files=files)
    if response.status_code == 200:
        result = response.json()
        return result["attachment_id"]
    else:
        print("Failed to upload image:", response.text)
        return None

def send_image_by_attachment_id(recipient_psid, attachment_id, page_access_token):
    import requests
    api_url = f"https://graph.facebook.com/v22.0/me/messages"
    params = {"access_token": page_access_token}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_psid},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "attachment_id": attachment_id
                }
            }
        }
    }
    response = requests.post(api_url, params=params, headers=headers, json=data)
    print("send_image_by_attachment_id response:", response.status_code, response.text)

def get_user_context(sender_psid):
    from models import UserContext, db
    ctx = UserContext.query.filter_by(sender_psid=sender_psid).first()
    return ctx.context if ctx else {}

def save_user_context(sender_psid, context):
    from models import UserContext, db
    ctx = UserContext.query.filter_by(sender_psid=sender_psid).first()
    if ctx:
        ctx.context = context
    else:
        ctx = UserContext(sender_psid=sender_psid, context=context)
        db.session.add(ctx)
    db.session.commit()

import logging

def handle_message(sender_psid, message, bot_request, image=None, context=None):
    try:
        if context is None:
            context = {}

        history = get_history(bot_request.id)
        product_images = ProductImage.query.filter_by(bot_request_id=bot_request.id).all()
        product_list = [img.product_name for img in product_images]
        catalog = "\n".join(product_list)
        intent = classify_intent(message) if not image else None

        if not image and message.strip().lower() == "/viewcart":
            try:
                return ("text", view_cart.execute(sender_psid, bot_request.id))
            except Exception:
                logging.exception("Error while viewing cart")
                return ("text", "⚠️ We’re having trouble loading your cart right now. Please try again later.")

        if context.get('flow') == 'order':
            step = context.get('step', 1)

            if message.strip().lower() == "cancel":
                context.clear()
                return ("text", "❌ Your order has been cancelled.")

            if step == 1:
                context['product'] = message.strip()

                existing = CartItem.query.filter_by(
                    sender_psid=sender_psid,
                    bot_request_id=bot_request.id,
                    product_name=context['product']
                ).first()

                if existing:
                    existing.quantity += 1
                else:
                    cart_item = CartItem(
                        sender_psid=sender_psid,
                        bot_request_id=bot_request.id,
                        product_name=context['product'],
                        quantity=1
                    )
                    db.session.add(cart_item)

                db.session.commit()

                context['step'] = 2
                return ("text", "📦 How many units would you like to order?")

            elif step == 2:
                context['quantity'] = message.strip()
                context['step'] = 3
                return ("text", "🧑 May I have your name, please?")

            elif step == 3:
                context['customer_name'] = message.strip()
                context['step'] = 4
                return ("text", "📍 Kindly share your delivery address.")

            elif step == 4:
                context['address'] = message.strip()
                context['step'] = 5
                return ("text", "📞 Please provide the best contact info Phone number or email to reach you?")

            elif step == 5:
                context['contact'] = message.strip()
                context['step'] = 6
                summary = (
                    f"🧾 Order summary:\n"
                    f"Product: {context['product']}\n"
                    f"Quantity: {context['quantity']}\n"
                    f"Name: {context['customer_name']}\n"
                    f"Address: {context['address']}\n"
                    f"Contact: {context['contact']}\n"
                    "✉️ Reply 'confirm' to place your order."
                )
                return ("text", summary)

            elif step == 6 and message.strip().lower() == "confirm":
                order = Order(
                    bot_request_id=bot_request.id,
                    customer_psid=sender_psid,
                    product=context['product'],
                    quantity=context['quantity'],
                    customer_name=context['customer_name'],
                    address=context['address'],
                    contact=context['contact'],
                    status="placed"
                )
                db.session.add(order)
                db.session.commit()

                send_order_email_to_owner(bot_request, order)
                context.clear()
                return ("text", f"🎉✅ Your order (ID: {order.id}) has been placed successfully! We’ll contact you soon. 📞")

        if not image and intent == "order":
            context['flow'] = 'order'
            context['step'] = 1
            return ("text", "🛍️ What product would you like to order? (Type 'cancel' to exit)")

        if image:
            catalog_instruction = (
                "You are a product recognition assistant. "
                "You will be shown an image and a list of available products. "
                "Available products:\n" +
                "\n".join(product_list) +
                "\nIf you see a product in the image that matches or is similar to something in the catalog, " +
                "respond with the product name exactly as in the list. " +
                "If none match, say 'No catalog product recognized.'"
            )
            reply = get_gemini_response(
                user_message="Analyze the sent image and check if it contains any product from the catalog.",
                system_instruction=catalog_instruction,
                product_context=catalog,
                backend_instruction=BACKEND_INSTRUCTION.format(catalog=catalog),
                history=history,
                image=image
            )
            log_message(bot_request.id, sender_psid, "[image sent]", "user")
            matched_product = None
            for name in product_list:
                if name.lower() in reply.lower():
                    matched_product = name
                    break
            if matched_product:
                product = next((img for img in product_images if img.product_name == matched_product), None)
                if product:
                    image_path = os.path.join("static/uploads", product.filename)
                    attachment_id = upload_image_to_facebook(image_path, bot_request.page_access_token)
                    if attachment_id:
                        log_message(bot_request.id, sender_psid, f"Sent image: {matched_product}", "bot")
                        return ("image", attachment_id)
                    else:
                        log_message(bot_request.id, sender_psid, f"Failed to upload image: {matched_product}", "bot")
                        return ("text", f"We have '{matched_product}' in our catalog, but couldn't send the image right now.")
            else:
                log_message(bot_request.id, sender_psid, "No catalog product recognized in image.", "bot")
                return ("text", "🤔 We couldn't recognize any product from our catalog in the image. Please try again or send another photo.")

        try:
            reply = get_gemini_response(
                user_message=message,
                system_instruction=bot_request.system_instruction,
                product_context=catalog,
                backend_instruction=BACKEND_INSTRUCTION.format(catalog=catalog),
                history=history,
                image=None
            )
            log_message(bot_request.id, sender_psid, message, "user")

            match = re.search(r'{\s*"product_image"\s*:\s*"([^"]+)"\s*}', reply)
            if match:
                product_name = match.group(1)
                product = next((img for img in product_images if img.product_name == product_name), None)
                if product:
                    image_path = os.path.join("static/uploads", product.filename)
                    attachment_id = upload_image_to_facebook(image_path, bot_request.page_access_token)
                    if attachment_id:
                        log_message(bot_request.id, sender_psid, f"Sent image: {product_name}", "bot")
                        return ("image", attachment_id)
                    else:
                        log_message(bot_request.id, sender_psid, f"Failed to upload image: {product_name}", "bot")
                        return ("text", f"😓 Sorry, there was an error sending the image for {product_name}.")
                else:
                    log_message(bot_request.id, sender_psid, f"Product image not found: {product_name}", "bot")
                    return ("text", f"🔍 Sorry, I couldn't find an image for {product_name}.")

            order_match = re.search(r'{\s*order\s*:\s*([^}]+)\s*}', reply.lower())
            if order_match:
                product = order_match.group(1).strip()
                context['flow'] = 'order'
                context['step'] = 2
                context['product'] = product

                existing = CartItem.query.filter_by(
                    sender_psid=sender_psid,
                    bot_request_id=bot_request.id,
                    product_name=product
                ).first()

                if existing:
                    existing.quantity += 1
                else:
                    cart_item = CartItem(
                        sender_psid=sender_psid,
                        bot_request_id=bot_request.id,
                        product_name=product,
                        quantity=1
                    )
                    db.session.add(cart_item)
                db.session.commit()

                log_message(bot_request.id, sender_psid, f"Auto-detected order for '{product}'", "bot")
                return ("text", f"🛒 How many units of '{product}' would you like to order?")

            log_message(bot_request.id, sender_psid, reply, "bot")
            return ("text", reply)

        except Exception as e:
            logging.exception(f"Exception occurred in inner LLM handler: {e}")
            return ("text", "🙏 Sorry, we're currently unavailable to process your request. Our team will get back to you shortly. Thank you for your patience! 💬")

    except Exception as e:
        logging.exception(f"Exception occurred in handle_message: {e}")
        return ("text", "🙏 Sorry, we're currently unavailable to process your request. Our team will get back to you shortly. Thank you for your patience! 💬")



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
    try:
        with smtplib.SMTP('localhost') as s:
            s.sendmail(msg['From'], [owner_email], msg.as_string())
    except Exception as e:
        print(f"Error sending order email: {e}")
