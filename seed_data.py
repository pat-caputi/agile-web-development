"""
Optional development helper: seeds demo users and workouts so the
dashboard, leaderboard and profile pages have data locally.

Run from project root:

    python seed_data.py

Demo login:
    username: lebron
    password: Password123

Do NOT commit instance/users.db.
"""

import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import app, db, User, Workout, WorkoutSet


DEMO_USERS = [
    ("lebron", "lebron@example.com"),
    ("steph", "steph@example.com"),
    ("michael", "michael@example.com"),
    ("shai", "shai@example.com"),
    ("victor", "victor@example.com"),
]


EXERCISES = [
    ("Bench press", 50, 110),
    ("Squat", 70, 150),
    ("Deadlift", 80, 170),
    ("Overhead press", 25, 65),
    ("Barbell row", 40, 90),
    ("Bicep curl", 10, 25),
    ("Leg press", 80, 180),
    ("Incline press", 35, 85),
]


def seed():
    rng = random.Random(42)

    with app.app_context():
        db.create_all()

        # Create demo users.
        for username, email in DEMO_USERS:
            existing_user = User.query.filter_by(username=username).first()

            if existing_user:
                continue

            user = User(
                username=username,
                email=email,
                password=generate_password_hash("Password123"),
            )

            db.session.add(user)

        db.session.commit()

        # Create demo workouts and workout sets.
        for username, _ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()

            if not user:
                continue

            existing_workout = Workout.query.filter_by(user_id=user.id).first()

            if existing_workout:
                continue

            for days_ago in range(14, 0, -1):
                if rng.random() >= 0.65:
                    continue

                workout_date = datetime.utcnow() - timedelta(
                    days=days_ago,
                    hours=rng.randint(0, 12),
                )

                # Your Workout model only accepts user_id and date.
                workout = Workout(
                    user_id=user.id,
                    date=workout_date,
                )

                db.session.add(workout)
                db.session.flush()

                selected_exercises = rng.sample(
                    EXERCISES,
                    k=rng.randint(3, 5),
                )

                for exercise_name, min_weight, max_weight in selected_exercises:
                    for _ in range(rng.randint(3, 4)):
                        workout_set = WorkoutSet(
                            workout_id=workout.id,
                            exercise=exercise_name,
                            weight=rng.randint(min_weight, max_weight),
                            reps=rng.randint(5, 12),
                        )

                        db.session.add(workout_set)

        db.session.commit()

        print(f"Seeded {len(DEMO_USERS)} demo users with workouts.")
        print("Login with username 'lebron' / password 'Password123' to test.")


if __name__ == "__main__":
    seed()
