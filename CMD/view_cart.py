from models import CartItem

def execute(sender_psid, bot_request_id):
    items = CartItem.query.filter_by(sender_psid=sender_psid, bot_request_id=bot_request_id).all()

    if not items:
        return "🛒 Your cart is empty. Start shopping by typing a product name!"

    response = "🛍️ **Your Shopping Cart:**\n\n"
    for item in items:
        response += f"• 📦 *{item.product_name}* | {item.quantity} units\n"

   
    return response
