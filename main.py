from flask import Flask
from chat import chat_bp
from voices import voices_bp
from stripe import stripe_bp

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(voices_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
