from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Church(db.Model):
    __tablename__ = "churches"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default="basic")           # basic / standard / pro
    subscription_status = db.Column(db.String(20), default="trialing")  # trialing/active/past_due/canceled
    paystack_customer_code = db.Column(db.String(100))
    default_bible_version = db.Column(db.String(20), default="KJV")
    autonomous_mode = db.Column(db.Boolean, default=False)      # feature 2's "no operator" toggle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="church", lazy=True)
    sermons = db.relationship("Sermon", backref="church", lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    church_id = db.Column(db.Integer, db.ForeignKey("churches.id"), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="admin")  # admin / operator
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sermon(db.Model):
    __tablename__ = "sermons"
    id = db.Column(db.Integer, primary_key=True)
    church_id = db.Column(db.Integer, db.ForeignKey("churches.id"), nullable=False)
    title = db.Column(db.String(300))
    preached_at = db.Column(db.DateTime, default=datetime.utcnow)
    transcript = db.Column(db.Text)          # full transcript, synced from local client
    notes = db.Column(db.Text)               # Groq-generated notes (JSON string of points)
    synced_at = db.Column(db.DateTime)       # null until local client uploads it

    verses = db.relationship("SermonVerse", backref="sermon", lazy=True)


class SermonVerse(db.Model):
    """Every verse detected/projected during a sermon, for the archive."""
    __tablename__ = "sermon_verses"
    id = db.Column(db.Integer, primary_key=True)
    sermon_id = db.Column(db.Integer, db.ForeignKey("sermons.id"), nullable=False)
    reference = db.Column(db.String(100))       # e.g. "Philippians 4:13"
    version = db.Column(db.String(20))
    text = db.Column(db.Text)
    detected_at_seconds = db.Column(db.Integer)  # offset into sermon
    match_confidence = db.Column(db.Float)       # null if explicit reference, else fuzzy score
    was_auto_projected = db.Column(db.Boolean, default=False)
