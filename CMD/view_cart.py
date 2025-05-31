from models import MessageLog

def execute(sender_psid, bot_request_id):
    logs = MessageLog.query.filter_by(bot_request_id=bot_request_id, sender_psid=sender_psid).order_by(MessageLog.timestamp.desc()).limit(20)
    items = [l.message for l in logs if "product" in l.message.lower()]
    if not items:
        return "Your cart is empty."
    return "Items in your cart:\n" + "\n".join(items)
