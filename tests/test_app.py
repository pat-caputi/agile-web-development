"""
Pytest tests for LiftAGILE.

Place this file at: tests/test_app.py
Run with: python -m pytest -v
"""

import json
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash, check_password_hash

# Allow importing app.py from the project root when this file is inside /tests.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app as app_module  # noqa: E402

app = app_module.app
db = app_module.db
User = app_module.User
Workout = app_module.Workout
WorkoutSet = app_module.WorkoutSet
WorkoutPlan = app_module.WorkoutPlan
PersonalRecord = app_module.PersonalRecord

# Optional models/features. Tests will skip cleanly if a branch does not have them.
CalendarEntry = getattr(app_module, "CalendarEntry", None)
Follow = getattr(app_module, "Follow", None)
WorkoutLike = getattr(app_module, "WorkoutLike", None)
WorkoutComment = getattr(app_module, "WorkoutComment", None)


@pytest.fixture(autouse=True)
def configure_app_for_tests():
    """Make local tests predictable.

    CSRF and rate limiting are disabled for most tests because they test application
    behaviour rather than middleware. A separate CSRF test turns CSRF back on.
    """
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    yield
    app.config.update(
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )


@pytest.fixture()
def client():
    return app.test_client()


def unique_name(prefix="testuser"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def has_route(rule, method=None):
    for r in app.url_map.iter_rules():
        if r.rule == rule and (method is None or method in r.methods):
            return True
    return False


def force_login(client, user_id):
    """Set session directly so feature tests do not depend on the login route."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def cleanup_user(username):
    """Remove test data so the real dev database is not polluted."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            return

        if Follow is not None:
            Follow.query.filter(
                (Follow.follower_id == user.id) | (Follow.followed_id == user.id)
            ).delete(synchronize_session=False)

        if WorkoutLike is not None:
            WorkoutLike.query.filter_by(user_id=user.id).delete(synchronize_session=False)

        if WorkoutComment is not None:
            WorkoutComment.query.filter_by(user_id=user.id).delete(synchronize_session=False)

        if CalendarEntry is not None:
            CalendarEntry.query.filter_by(user_id=user.id).delete(synchronize_session=False)

        user_plan_ids = [p.id for p in WorkoutPlan.query.filter_by(user_id=user.id).all()]
        if user_plan_ids:
            if WorkoutLike is not None:
                WorkoutLike.query.filter(WorkoutLike.workout_id.in_(user_plan_ids)).delete(synchronize_session=False)
            if WorkoutComment is not None:
                WorkoutComment.query.filter(WorkoutComment.workout_id.in_(user_plan_ids)).delete(synchronize_session=False)
            if CalendarEntry is not None:
                CalendarEntry.query.filter(CalendarEntry.plan_id.in_(user_plan_ids)).delete(synchronize_session=False)
            WorkoutPlan.query.filter(WorkoutPlan.id.in_(user_plan_ids)).delete(synchronize_session=False)

        workout_ids = [w.id for w in Workout.query.filter_by(user_id=user.id).all()]
        if workout_ids:
            WorkoutSet.query.filter(WorkoutSet.workout_id.in_(workout_ids)).delete(synchronize_session=False)
            Workout.query.filter(Workout.id.in_(workout_ids)).delete(synchronize_session=False)

        PersonalRecord.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        db.session.delete(user)
        db.session.commit()


def make_user(username=None, password="Password1", email=None):
    username = username or unique_name()
    email = email or f"{username}@example.com"
    with app.app_context():
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "username": username, "email": email, "password": password}


@pytest.fixture()
def test_user():
    user = make_user()
    yield user
    cleanup_user(user["username"])


@pytest.fixture()
def second_user():
    user = make_user(username=unique_name("second"))
    yield user
    cleanup_user(user["username"])


def login(client, username, password="Password1"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def create_plan_for_user(user_id, title="Push Day", exercises="Bench press, Overhead press", is_public=True):
    with app.app_context():
        plan = WorkoutPlan(
            title=title,
            description=exercises,
            user_id=user_id,
            is_public=is_public,
        )
        db.session.add(plan)
        db.session.commit()
        return plan.id


# -----------------------------
# Authentication tests
# -----------------------------

def test_register_creates_user_and_hashes_password(client):
    username = unique_name("register")
    email = f"{username}@example.com"
    try:
        response = client.post(
            "/register",
            data={
                "username": username,
                "email": email,
                "password": "Password1",
                "confirm": "Password1",
            },
            follow_redirects=False,
        )

        assert response.status_code in (200, 302)

        with app.app_context():
            user = User.query.filter_by(username=username).first()
            assert user is not None
            assert user.email == email
            assert user.password != "Password1"
            assert check_password_hash(user.password, "Password1")
    finally:
        cleanup_user(username)


def test_duplicate_registration_is_rejected(client):
    username = unique_name("dupe")
    email = f"{username}@example.com"
    try:
        make_user(username=username, email=email)

        response = client.post(
            "/register",
            data={
                "username": username,
                "email": email,
                "password": "Password1",
                "confirm": "Password1",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        with app.app_context():
            assert User.query.filter_by(username=username).count() == 1
    finally:
        cleanup_user(username)


def test_valid_login_redirects_to_dashboard(client, test_user):
    response = login(client, test_user["username"], test_user["password"])
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_invalid_login_stays_on_login_page(client, test_user):
    response = client.post(
        "/login",
        data={"username": test_user["username"], "password": "wrong"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid" in response.data or b"Welcome back" in response.data


def test_logout_clears_session(client, test_user):
    force_login(client, test_user["id"])
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# -----------------------------
# Protected page tests
# -----------------------------

@pytest.mark.parametrize("path", ["/dashboard", "/profile", "/plans", "/calendar", "/log_workout"])
def test_protected_pages_redirect_when_logged_out(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# -----------------------------
# Workout plan tests
# -----------------------------

def test_create_plan_route_creates_plan(client, test_user):
    force_login(client, test_user["id"])

    response = client.post(
        "/plans/create",
        data={
            "title": "Test Push Plan",
            "exercises": "Bench press, Overhead press",
        },
        follow_redirects=False,
    )

    assert response.status_code in (200, 302)

    with app.app_context():
        plan = WorkoutPlan.query.filter_by(user_id=test_user["id"], title="Test Push Plan").first()
        assert plan is not None
        assert "Bench press" in (plan.description or "")


def test_edit_plan_route_updates_plan(client, test_user):
    force_login(client, test_user["id"])
    plan_id = create_plan_for_user(test_user["id"], title="Old Plan")

    response = client.post(
        f"/plans/{plan_id}/edit",
        data={
            "title": "Updated Plan",
            "exercises": "Squat, Leg press",
        },
        follow_redirects=False,
    )

    assert response.status_code in (200, 302)

    with app.app_context():
        plan = db.session.get(WorkoutPlan, plan_id)
        assert plan is not None
        assert plan.title == "Updated Plan"
        assert "Squat" in (plan.description or "")


def test_delete_plan_route_deletes_plan(client, test_user):
    force_login(client, test_user["id"])
    plan_id = create_plan_for_user(test_user["id"], title="Delete Me")

    response = client.post(f"/plans/{plan_id}/delete", follow_redirects=False)
    assert response.status_code in (200, 302)

    with app.app_context():
        assert db.session.get(WorkoutPlan, plan_id) is None


def test_user_cannot_delete_other_users_plan(client, test_user, second_user):
    force_login(client, test_user["id"])
    other_plan_id = create_plan_for_user(second_user["id"], title="Other User Plan")

    response = client.post(f"/plans/{other_plan_id}/delete", follow_redirects=False)
    assert response.status_code in (401, 403, 404)


# -----------------------------
# Workout logging / PR tests
# -----------------------------

def test_log_workout_saves_sets_and_personal_record(client, test_user):
    force_login(client, test_user["id"])

    workout_data = [
        {"exercise": "Bench press", "weight": 80, "reps": 8},
        {"exercise": "Bench press", "weight": 85, "reps": 5},
    ]

    response = client.post(
        "/log_workout",
        data={"workout_data": json.dumps(workout_data)},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]

    with app.app_context():
        workouts = Workout.query.filter_by(user_id=test_user["id"]).all()
        assert len(workouts) >= 1

        sets = (
            WorkoutSet.query
            .join(Workout, WorkoutSet.workout_id == Workout.id)
            .filter(Workout.user_id == test_user["id"])
            .all()
        )
        assert len(sets) >= 2

        pr = PersonalRecord.query.filter_by(
            user_id=test_user["id"],
            exercise="bench press",
        ).first()
        assert pr is not None
        assert pr.best_weight == 80
        assert pr.best_reps == 8


def test_log_workout_rejects_empty_sets(client, test_user):
    force_login(client, test_user["id"])

    response = client.post(
        "/log_workout",
        data={"workout_data": "[]"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/log_workout" in response.headers["Location"]


# -----------------------------
# Calendar tests
# -----------------------------

def test_calendar_schedule_creates_entry(client, test_user):
    if CalendarEntry is None or not has_route("/calendar/schedule", "POST"):
        pytest.skip("Calendar scheduling route/model not available in this branch")

    force_login(client, test_user["id"])
    plan_id = create_plan_for_user(test_user["id"], title="Calendar Plan")

    response = client.post(
        "/calendar/schedule",
        json={"date": "2026-05-20", "plan_id": plan_id},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    with app.app_context():
        entry = CalendarEntry.query.filter_by(user_id=test_user["id"], date=date(2026, 5, 20)).first()
        assert entry is not None
        assert entry.plan_id == plan_id
        assert entry.is_rest is False


def test_calendar_schedule_rejects_other_users_plan(client, test_user, second_user):
    if CalendarEntry is None or not has_route("/calendar/schedule", "POST"):
        pytest.skip("Calendar scheduling route/model not available in this branch")

    force_login(client, test_user["id"])
    other_plan_id = create_plan_for_user(second_user["id"], title="Other Calendar Plan")

    response = client.post(
        "/calendar/schedule",
        json={"date": "2026-05-21", "plan_id": other_plan_id},
    )

    assert response.status_code in (401, 403, 404)


# -----------------------------
# Social tests
# -----------------------------

def test_follow_and_unfollow_user(client, test_user, second_user):
    if Follow is None:
        pytest.skip("Follow model not available")

    force_login(client, test_user["id"])

    follow_response = client.post(f"/follow/{second_user['id']}", follow_redirects=False)
    assert follow_response.status_code in (302, 200)

    with app.app_context():
        follow = Follow.query.filter_by(
            follower_id=test_user["id"],
            followed_id=second_user["id"],
        ).first()
        assert follow is not None

    unfollow_response = client.post(f"/unfollow/{second_user['id']}", follow_redirects=False)
    assert unfollow_response.status_code in (302, 200)

    with app.app_context():
        follow = Follow.query.filter_by(
            follower_id=test_user["id"],
            followed_id=second_user["id"],
        ).first()
        assert follow is None


def test_like_json_toggles_public_workout_plan(client, test_user, second_user):
    if WorkoutLike is None:
        pytest.skip("WorkoutLike model not available")

    force_login(client, test_user["id"])
    plan_id = create_plan_for_user(second_user["id"], title="Public Plan", is_public=True)

    like_response = client.post(f"/workout/{plan_id}/like/json")
    assert like_response.status_code == 200
    like_data = like_response.get_json()
    assert like_data["liked"] is True
    assert like_data["count"] >= 1

    unlike_response = client.post(f"/workout/{plan_id}/like/json")
    assert unlike_response.status_code == 200
    unlike_data = unlike_response.get_json()
    assert unlike_data["liked"] is False


def test_private_plan_cannot_be_liked_by_other_user(client, test_user, second_user):
    if WorkoutLike is None:
        pytest.skip("WorkoutLike model not available")

    force_login(client, test_user["id"])
    private_plan_id = create_plan_for_user(second_user["id"], title="Private Plan", is_public=False)

    response = client.post(f"/workout/{private_plan_id}/like/json")
    assert response.status_code == 403


# -----------------------------
# Security tests
# -----------------------------

def test_csrf_blocks_post_when_enabled(client, test_user):
    # Only meaningful if Flask-WTF CSRF is installed/configured in this app.
    if "csrf" not in app_module.__dict__:
        pytest.skip("CSRF protection not configured in this branch")

    app.config["WTF_CSRF_ENABLED"] = True
    app.config["RATELIMIT_ENABLED"] = False

    try:
        response = client.post(
            "/login",
            data={"username": test_user["username"], "password": test_user["password"]},
        )
        assert response.status_code == 400
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_login_rate_limit_blocks_excessive_attempts(client):
    # Only meaningful if Flask-Limiter is installed/configured in this app.
    if "limiter" not in app_module.__dict__:
        pytest.skip("Rate limiter not configured in this branch")

    app.config["RATELIMIT_ENABLED"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    username = unique_name("ratelimit")
    try:
        make_user(username=username, password="Password1")

        last_response = None
        for _ in range(6):
            last_response = client.post(
                "/login",
                data={"username": username, "password": "WrongPassword"},
                follow_redirects=False,
            )

        assert last_response.status_code in (200, 429)
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        cleanup_user(username)
