"""
Subscription billing via Paystack — supports card + Mobile Money,
which matters for the Ghana/West Africa church market.
"""
from flask import Blueprint, current_app, jsonify, request, redirect
from flask_login import login_required, current_user
from paystackapi.transaction import Transaction

from app.models import db

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


@billing_bp.route("/subscribe/<plan_code>", methods=["POST"])
@login_required
def subscribe(plan_code):
    plans = current_app.config["PLANS"]
    if plan_code not in plans:
        return jsonify({"error": "Unknown plan"}), 400

    plan = plans[plan_code]
    if plan["price"] == 0:
        # Free tier — no payment needed, activate directly
        current_user.church.plan = plan_code
        current_user.church.subscription_status = "active"
        db.session.commit()
        return redirect("/dashboard")

    response = Transaction.initialize(
        reference=f"church-{current_user.church_id}-{plan_code}",
        amount=plan["price"],  # in pesewas
        email=current_user.email,
        callback_url=request.url_root.rstrip("/") + "/billing/verify",
        metadata={"church_id": current_user.church_id, "plan": plan_code},
    )
    return redirect(response["data"]["authorization_url"])


@billing_bp.route("/verify")
@login_required
def verify():
    ref = request.args.get("reference")
    response = Transaction.verify(reference=ref)

    if response["data"]["status"] == "success":
        plan_code = response["data"]["metadata"]["plan"]
        current_user.church.plan = plan_code
        current_user.church.subscription_status = "active"
        db.session.commit()

    return redirect("/dashboard")


@billing_bp.route("/webhook", methods=["POST"])
def webhook():
    """Paystack calls this on subscription renewals/failures — verify
    the signature header in production before trusting the payload."""
    event = request.json
    event_type = event.get("event")

    if event_type == "charge.success":
        pass  # extend/renew subscription
    elif event_type == "subscription.disable":
        pass  # mark church as past_due

    return jsonify({"status": "received"}), 200
