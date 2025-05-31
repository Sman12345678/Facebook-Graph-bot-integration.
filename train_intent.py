from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import joblib

X = [
    "hello", "hi", "hey", "good morning",
    "show me products", "product list", "catalog", "what do you sell",
    "i want to buy", "order", "purchase", "i want product",
    "track my order", "order status", "where is my order",
    "help", "support", "how can i use", "assist me",
    "i have a problem", "complaint", "feedback",
    "show me image of product a", "picture of product b", "can i see product c"
]
y = [
    "greeting", "greeting", "greeting", "greeting",
    "catalog", "catalog", "catalog", "catalog",
    "order", "order", "order", "order",
    "track", "track", "track",
    "help", "help", "help", "help",
    "complaint", "complaint", "complaint",
    "product_image", "product_image", "product_image"
]

pipeline = Pipeline([
    ('vect', CountVectorizer()),
    ('clf', MultinomialNB())
])

pipeline.fit(X, y)
joblib.dump(pipeline, 'intent_model.pkl')
print("Intent model trained and saved.")
