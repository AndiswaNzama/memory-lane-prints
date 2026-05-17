import os
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import cloudinary

from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

from config import config

_sentry_dsn = os.environ.get('SENTRY_DSN', '')
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
mail = Mail()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

_WEAK_KEYS = {"", "dev-secret-not-for-production", "dev-secret-change-in-production"}



def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config["default"]))

    # Security checks for production
    if config_name == "production":
        if app.config.get("SECRET_KEY", "") in _WEAK_KEYS:
            raise RuntimeError("SECRET_KEY is missing or insecure.")
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError("DATABASE_URL is not set.")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # Cloudinary setup
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True,
    )

  
    from routes.main import main_bp
    from routes.orders import orders_bp
    from routes.payments import payments_bp
    from routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(orders_bp, url_prefix="/order")
    app.register_blueprint(payments_bp, url_prefix="/payment")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    
    @app.route("/health")
    def health():
        return jsonify(status="ok"), 200

    
    @app.context_processor
    def inject_site_globals():
        from models import get_setting, Review

        def pending_reviews_count():
            try:
                return Review.query.filter_by(is_approved=False).count()
            except Exception:
                return 0

        return {
            "whatsapp_number": get_setting("whatsapp_number"),
            "instagram_handle": get_setting("instagram_handle"),
            "pending_reviews_count": pending_reviews_count,
        }

   
    import json as _json

    @app.template_filter('fromjson')
    def fromjson_filter(value):
        if not value:
            return []
        try:
            return _json.loads(value)
        except Exception:
            return []

    with app.app_context():
        db.create_all()

        from models import seed_catalog, seed_settings
        seed_catalog()
        seed_settings(app.config)

    return app



app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)