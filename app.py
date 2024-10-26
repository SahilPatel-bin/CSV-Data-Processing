from flask import Flask
from config import Config
from controllers.auth_controller import auth_bp
from controllers.purchase_controller import purchase_bp

app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(purchase_bp, url_prefix='')
app.register_blueprint(auth_bp, url_prefix='')


if __name__ == "__main__":
    app.run(debug=True)