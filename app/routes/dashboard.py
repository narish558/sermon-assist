from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Sermon

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def home():
    sermons = (
        Sermon.query.filter_by(church_id=current_user.church_id)
        .order_by(Sermon.preached_at.desc())
        .limit(20)
        .all()
    )
    return render_template("dashboard.html", sermons=sermons, church=current_user.church)


@dashboard_bp.route("/sermon/<int:sermon_id>")
@login_required
def sermon_detail(sermon_id):
    sermon = Sermon.query.filter_by(
        id=sermon_id, church_id=current_user.church_id
    ).first_or_404()
    return render_template("sermon_detail.html", sermon=sermon)
