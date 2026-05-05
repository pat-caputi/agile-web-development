"""
Unit tests for the leaderboard and profile features.

Run from the project root with:

    python -m unittest tests.test_leaderboard_profile -v

These tests use Flask's test client + a temporary SQLite database, so they
don't touch the dev users.db.
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta

# IMPORTANT: we have to point the app at a throwaway database file BEFORE we
# import the app module. Otherwise app.py's `with app.app_context(): db.create_all()`
# at import time binds Flask-SQLAlchemy's engine cache to the real users.db,
# and nothing we do in setUp can swap it out afterwards.
_TMPDIR = tempfile.mkdtemp(prefix="liftagile_tests_")
_TMP_DB = os.path.join(_TMPDIR, "test.db")

import app as app_module
from app import (
    app, db, User, Workout, WorkoutSet,
    compute_leaderboard, current_streak, personal_records, initials,
)

# Replace the engine that app.py created on import. Flask-SQLAlchemy caches
# engines in a private dict keyed by Flask app; we replace the cached engine
# in place so it points at our temp DB instead of the real users.db.
from sqlalchemy import create_engine
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_TMP_DB}"
db._app_engines[app][None] = create_engine(f"sqlite:///{_TMP_DB}")


def _make_user(username, **fields):
    u = User(username=username,
             email=f"{username}@test.com",
             password="x",  # not exercising auth here
             **fields)
    db.session.add(u)
    db.session.commit()
    return u


def _add_workout(user, date, sets):
    """sets = list of (exercise, weight, reps) tuples."""
    w = Workout(user_id=user.id, name="Test", date=date)
    db.session.add(w)
    db.session.flush()
    for ex, weight, reps in sets:
        db.session.add(WorkoutSet(workout_id=w.id, exercise=ex, weight=weight, reps=reps))
    db.session.commit()
    return w


class LiftAGILETestBase(unittest.TestCase):
    """Common test setup: temporary SQLite DB, fresh schema per test."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()


# Clean up the temp directory once at the end of the whole test process
# (using atexit instead of tearDownClass, which would fire once per subclass
# and delete the directory before later test classes could use it).
import atexit, shutil
atexit.register(lambda: shutil.rmtree(_TMPDIR, ignore_errors=True))


class WorkoutVolumeTests(LiftAGILETestBase):

    def test_workout_volume_sums_weight_times_reps_across_sets(self):
        u = _make_user("alice")
        w = _add_workout(u, datetime.utcnow(), [
            ("Bench press", 80, 5),
            ("Bench press", 80, 5),
            ("Squat", 100, 3),
        ])
        self.assertEqual(w.volume, 1100)

    def test_user_with_no_workouts_has_no_volume(self):
        u = _make_user("bob")
        self.assertEqual(list(u.workouts), [])
        rows = compute_leaderboard("volume")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["score"], 0)


class LeaderboardTests(LiftAGILETestBase):

    def test_leaderboard_orders_users_by_weekly_volume_desc(self):
        a = _make_user("alice")
        b = _make_user("bob")
        c = _make_user("carol")
        today = datetime.utcnow()
        _add_workout(a, today, [("Bench press", 60, 10)])
        _add_workout(b, today, [("Squat", 100, 10)])
        _add_workout(c, today, [("Deadlift", 50, 5)])
        rows = compute_leaderboard("volume")
        usernames = [r["user"].username for r in rows]
        self.assertEqual(usernames, ["bob", "alice", "carol"])
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["score"], 1000)

    def test_leaderboard_frequency_metric_counts_workouts_in_week(self):
        a = _make_user("alice")
        b = _make_user("bob")
        # Anchor the test to a stable mid-week reference point so the 3 consecutive
        # workouts always fall within the same Monday-Sunday week regardless of when
        # the test runs. We pick the latest weekday (Wed-Sun) within the current week
        # so today, today-1, today-2 all sit safely inside it.
        today = datetime.utcnow()
        # Days from this week's Monday: 0=Mon, 1=Tue, ... 6=Sun
        days_into_week = today.weekday()
        # If we're early in the week (Mon/Tue), use this week's Wednesday.
        # Otherwise, use today (which gives plenty of headroom).
        if days_into_week < 2:
            anchor = today + timedelta(days=(2 - days_into_week))
        else:
            anchor = today
        for i in range(3):
            _add_workout(a, anchor - timedelta(days=i), [("Bench press", 50, 5)])
        _add_workout(b, anchor, [("Bench press", 50, 5)])
        rows = compute_leaderboard("frequency")
        self.assertEqual(rows[0]["user"].username, "alice")
        self.assertEqual(rows[0]["score"], 3)
        self.assertEqual(rows[1]["score"], 1)

    def test_leaderboard_excludes_workouts_from_previous_weeks(self):
        a = _make_user("alice")
        _add_workout(a, datetime.utcnow() - timedelta(days=30),
                     [("Bench press", 200, 10)])
        rows = compute_leaderboard("volume")
        self.assertEqual(rows[0]["score"], 0)

    def test_leaderboard_prs_metric_counts_sets_matching_alltime_max(self):
        a = _make_user("alice")
        _add_workout(a, datetime.utcnow() - timedelta(days=10),
                     [("Bench press", 100, 1)])
        _add_workout(a, datetime.utcnow(), [
            ("Bench press", 100, 1),
            ("Bench press", 90, 5),
            ("Squat", 150, 1),
        ])
        rows = compute_leaderboard("prs")
        self.assertEqual(rows[0]["score"], 2)


class StreakTests(LiftAGILETestBase):

    def test_streak_zero_when_no_workouts(self):
        u = _make_user("alice")
        self.assertEqual(current_streak(u), 0)

    def test_streak_counts_consecutive_days_ending_today(self):
        u = _make_user("alice")
        today = datetime.utcnow()
        for i in range(4):
            _add_workout(u, today - timedelta(days=i), [("Bench press", 50, 5)])
        self.assertEqual(current_streak(u), 4)

    def test_streak_breaks_with_a_gap(self):
        u = _make_user("alice")
        today = datetime.utcnow()
        for i in [0, 1]:
            _add_workout(u, today - timedelta(days=i), [("Bench press", 50, 5)])
        _add_workout(u, today - timedelta(days=4), [("Bench press", 50, 5)])
        self.assertEqual(current_streak(u), 2)


class PersonalRecordTests(LiftAGILETestBase):

    def test_personal_records_returns_max_weight_per_exercise(self):
        u = _make_user("alice")
        _add_workout(u, datetime.utcnow(), [
            ("Bench press", 80, 5),
            ("Bench press", 90, 3),
            ("Squat", 120, 5),
            ("Squat", 100, 5),
        ])
        records = personal_records(u)
        bench = next(r for r in records if r["exercise"].lower() == "bench press")
        squat = next(r for r in records if r["exercise"].lower() == "squat")
        self.assertEqual(bench["weight"], 90)
        self.assertEqual(squat["weight"], 120)


class HelperTests(LiftAGILETestBase):

    def test_initials_handles_single_and_multi_word_names(self):
        self.assertEqual(initials("kawhi"), "KA")
        self.assertEqual(initials("Pat Caputi"), "PC")
        self.assertEqual(initials(""), "?")
        self.assertEqual(initials(None), "?")

    def test_login_required_redirects_anonymous_user_to_login(self):
        resp = self.client.get("/profile", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_leaderboard_route_returns_200_when_logged_in(self):
        u = _make_user("alice")
        with self.client.session_transaction() as sess:
            sess['user_id'] = u.id
        resp = self.client.get("/leaderboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Leaderboard", resp.data)

    def test_api_leaderboard_returns_json(self):
        u = _make_user("alice")
        _add_workout(u, datetime.utcnow(), [("Bench press", 80, 5)])
        with self.client.session_transaction() as sess:
            sess['user_id'] = u.id
        resp = self.client.get("/api/leaderboard?metric=volume")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["metric"], "volume")
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["username"], "alice")
        self.assertEqual(data["rows"][0]["score"], 400)


if __name__ == "__main__":
    unittest.main()