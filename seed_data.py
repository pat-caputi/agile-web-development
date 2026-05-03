"""
Optional development helper: seeds a few demo users and workouts so the
leaderboard and profile pages have something to show during local testing.

Run from project root:

    python seed_data.py

Idempotent: re-running won't duplicate users (it only creates ones missing).
"""
import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import app, db, User, Workout, WorkoutSet


DEMO_USERS = [
    ("lebron",  "lebron@example.com",  "Lifting since high school. Push/pull/legs."),
    ("steph",   "steph@example.com",   "Marathon runner getting into strength work."),
    ("michael", "michael@example.com", None),
    ("shai",    "shai@example.com",    "Coffee, then deadlifts."),
    ("victor",  "victor@example.com",  None),
]

# (exercise name, min weight, max weight)
EXERCISES = [
    ("Bench press",    50, 110),
    ("Squat",          70, 150),
    ("Deadlift",       80, 170),
    ("Overhead press", 25,  65),
    ("Barbell row",    40,  90),
    ("Pull up",         0,   0),
    ("Bicep curl",     10,  25),
]

WORKOUT_NAMES = ["Push day", "Pull day", "Leg day", "Upper body", "Full body"]


def seed():
    rng = random.Random(42)  # deterministic so the demo looks the same each run
    with app.app_context():
        # Users
        for username, email, bio in DEMO_USERS:
            if User.query.filter_by(username=username).first():
                continue
            db.session.add(User(
                username=username,
                email=email,
                password=generate_password_hash("Password123"),
                bio=bio,
            ))
        db.session.commit()

        # Workouts: ~14 days of activity for each user, ~55% workout rate
        for username, _, _ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()
            if user.workouts:  # already seeded for this user
                continue

            for days_ago in range(14, 0, -1):
                if rng.random() < 0.55:
                    when = datetime.utcnow() - timedelta(days=days_ago,
                                                         hours=rng.randint(0, 12))
                    workout = Workout(
                        user_id=user.id,
                        name=rng.choice(WORKOUT_NAMES),
                        date=when,
                    )
                    db.session.add(workout)
                    db.session.flush()

                    for ex, lo, hi in rng.sample(EXERCISES, k=rng.randint(2, 4)):
                        if hi == 0:
                            continue   # skip bodyweight-only exercises in seed
                        for _ in range(rng.randint(3, 4)):
                            db.session.add(WorkoutSet(
                                workout_id=workout.id,
                                exercise=ex,
                                weight=rng.randint(lo, hi),
                                reps=rng.randint(5, 12),
                            ))
        db.session.commit()
        print(f"Seeded {len(DEMO_USERS)} demo users with workouts.")
        print("Login with username 'lebron' / password 'Password123' to test.")


if __name__ == "__main__":
    seed()
