import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/sermon_assist"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Groq (free/fast LLM for sermon notes) ---
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    # --- Paystack (Ghana/West Africa billing incl. Mobile Money) ---
    PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")

    # --- Subscription tiers (price in GHS pesewas, i.e. x100) ---
    PLANS = {
        "basic": {"name": "Basic", "price": 0, "features": ["reference_lookup", "single_version"]},
        "standard": {"name": "Standard", "price": 15000, "features": ["autonomous_match", "multi_version", "auto_notes"]},
        "pro": {"name": "Pro", "price": 40000, "features": ["multi_campus", "team_dashboard", "branding", "export_archive"]},
    }

    # ==========================================================
    # BRAND THEME — replace these with DranyTech's real logo hex
    # codes. Everything in templates/static reads from these two
    # variables (see static/css/theme.css), so this is the ONLY
    # place you need to edit to apply the real brand colors.
    # ==========================================================
    BRAND_PRIMARY = os.environ.get("BRAND_PRIMARY", "#1B3A52")     # DranyTech logo navy blue
    BRAND_ACCENT = os.environ.get("BRAND_ACCENT", "#9CA3AA")       # DranyTech logo brushed silver/grey
    BRAND_NAME = "DranyTech Sermon Assist"
