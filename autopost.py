import threading, time, random
from messageHandler import send_text_fb

AUTOPOST_MESSAGES = [
    "Welcome to our store! 🎉",
    "Check out our latest products! 🛍️",
    "Contact us for special deals! 📞",
    "We value your feedback! 💬",
    "Today's special offer awaits you!",
    "Looking for something? Ask away!",
    "Don’t miss our top-selling items!",
    "New arrivals just landed! 🚚",
    "Order now and get fast delivery!",
    "Customer satisfaction is our priority.",
    "Leave us a review – we love feedback!",
    "Track your order in real-time!",
    "Got questions? We’ve got answers.",
    "Upgrade your experience with us!",
    "Our team is here for you 24/7.",
    "Exclusive deals inside. Ask for catalog!",
    "Refer a friend for rewards!",
    "Thank you for shopping with us!",
    "Your favorite products are just a message away!",
    "Visit our website for more info.",
    "Enjoy exclusive discounts today!"
]

def start_autopost(page_id, page_access_token):
    def autopost_loop():
        while True:
            msg = random.choice(AUTOPOST_MESSAGES)
            send_text_fb(page_id, msg, page_access_token)
            time.sleep(86400)  # 24 hours
    t = threading.Thread(target=autopost_loop, daemon=True)
    t.start()
    return t
