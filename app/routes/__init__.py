from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate

from app.config import Config
from app.models import db, User

login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = "auth.login"

    # Make brand colors available to every template without passing manually
    @app.context_processor
    def inject_brand():
        return {
            "brand_primary": app.config["BRAND_PRIMARY"],
            "brand_accent": app.config["BRAND_ACCENT"],
            "brand_name": app.config["BRAND_NAME"],
        }

    from app.routes.auth import auth_bp
    from app.routes.billing import billing_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.sync import sync_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sync_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app
