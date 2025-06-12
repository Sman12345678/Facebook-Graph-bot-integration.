import google.generativeai as genai
import os

def get_gemini_response(user_message, system_instruction, product_context, backend_instruction, history=None, image=None):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = (backend_instruction or "") + "\n"
    if system_instruction:
        prompt += system_instruction + "\n"
    if product_context:
        prompt += f"Product Catalog:\n{product_context}\n"
    if history:
        prompt += "Conversation history:\n"
        for h in history[-5:]:
            prompt += f"{h['role']}: {h['message']}\n"
    prompt += f"User: {user_message}\n"
    model = genai.GenerativeModel("gemini-1.5-flash")
    if image:
        response = model.generate_content([
            prompt,
            {'mime_type': 'image/jpeg', 'data': image}
        ])
    else:
        response = model.generate_content(prompt)
    return response.text
