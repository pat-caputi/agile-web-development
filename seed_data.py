"""
Optional development helper: seeds demo users, workouts, follows, likes,
and comments so dashboard, leaderboard, profile, community feed, and
public profile pages have data locally.

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

from app import app, db, User, Workout, WorkoutSet, WorkoutPlan

# Import social models only if they exist.
try:
    from app import Follow, WorkoutLike, WorkoutComment
except ImportError:
    Follow = None
    WorkoutLike = None
    WorkoutComment = None


DEMO_USERS = [
    ("lebron", "lebron@example.com", "I like hooping and heavy push days."),
    ("steph", "steph@example.com", "Cardio, shooting, and consistency."),
    ("michael", "michael@example.com", "Strength training and competition."),
    ("shai", "shai@example.com", "Balanced workouts and mobility."),
    ("victor", "victor@example.com", "Leg day, conditioning, and recovery."),
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


COMMENTS = [
    "Solid session 🔥",
    "This plan looks tough.",
    "I might try this one.",
    "Good volume on this workout.",
    "Strong work — nice progression.",
]


def set_if_exists(model_obj, field_name, value):
    """Safely set a field only if the SQLAlchemy model has it."""
    if hasattr(model_obj, field_name):
        setattr(model_obj, field_name, value)


def seed():
    rng = random.Random(42)

    with app.app_context():
        db.create_all()

        # Create demo users.
        for username, email, bio in DEMO_USERS:
            user = User.query.filter_by(username=username).first()

            if not user:
                user = User(
                    username=username,
                    email=email,
                    password=generate_password_hash("Password123"),
                )
                db.session.add(user)
                db.session.flush()

            set_if_exists(user, "bio", bio)
            set_if_exists(user, "profile_public", True)

        db.session.commit()

        # Create demo workouts and workout sets.
        # Range covers the last 30 days (history) plus the current week (days 0-6)
        # so the leaderboard, which filters by Workout.date >= start_of_week, always has data.
        for username, _, _ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()

            if not user:
                continue

            for days_ago in range(30, -1, -1):
                # Higher hit rate for current week so leaderboard is well-populated.
                threshold = 0.50 if days_ago <= 6 else 0.65
                if rng.random() >= threshold:
                    continue

                workout_date = datetime.utcnow() - timedelta(
                    days=days_ago,
                    hours=rng.randint(0, 12),
                )

                # Skip if a workout already exists for this user on this date.
                date_start = workout_date.replace(hour=0, minute=0, second=0, microsecond=0)
                date_end = date_start + timedelta(days=1)
                existing = Workout.query.filter(
                    Workout.user_id == user.id,
                    Workout.date >= date_start,
                    Workout.date < date_end,
                ).first()
                if existing:
                    continue

                workout = Workout(
                    user_id=user.id,
                    date=workout_date,
                )

                set_if_exists(workout, "is_public", True)
                set_if_exists(workout, "title", f"{username.title()}'s Training Session")
                set_if_exists(workout, "name", f"{username.title()}'s Training Session")
                set_if_exists(workout, "description", "A public demo workout for the community feed.")
                set_if_exists(workout, "notes", "A public demo workout for the community feed.")
                set_if_exists(workout, "category", rng.choice(["Strength", "Cardio", "Upper Body", "Legs"]))
                set_if_exists(workout, "difficulty", rng.choice(["Beginner", "Intermediate", "Advanced"]))

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

        # Create public WorkoutPlans so demo users appear in the community feed.
        PLAN_TEMPLATES = [
            ("{name}'s Push Day", "Chest, shoulders, and triceps focused session."),
            ("{name}'s Pull Day", "Back and biceps with heavy compound lifts."),
            ("{name}'s Leg Day", "Quad-dominant with accessory hamstring work."),
            ("{name}'s Full Body", "Total body conditioning circuit."),
            ("{name}'s Cardio Blast", "High-intensity cardio and core work."),
        ]

        for username, _, _ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()
            if not user:
                continue

            existing_plans = WorkoutPlan.query.filter_by(user_id=user.id, is_public=True).count()
            if existing_plans >= 3:
                continue

            for title_tpl, desc in rng.sample(PLAN_TEMPLATES, k=3):
                title = title_tpl.format(name=username.title())
                exists = WorkoutPlan.query.filter_by(user_id=user.id, title=title).first()
                if exists:
                    continue
                plan = WorkoutPlan(
                    title=title,
                    description=desc,
                    user_id=user.id,
                    is_public=True,
                )
                db.session.add(plan)

        db.session.commit()

        users = User.query.all()
        workouts = Workout.query.all()
        plans = WorkoutPlan.query.filter_by(is_public=True).all()

        # Create follows.
        if Follow:
            for follower in users:
                for followed in users:
                    if follower.id == followed.id:
                        continue

                    # Keep it light/random, not everyone follows everyone.
                    if rng.random() >= 0.35:
                        continue

                    existing_follow = Follow.query.filter_by(
                        follower_id=follower.id,
                        followed_id=followed.id,
                    ).first()

                    if not existing_follow:
                        db.session.add(
                            Follow(
                                follower_id=follower.id,
                                followed_id=followed.id,
                            )
                        )

            db.session.commit()

        # Create likes on public WorkoutPlans (what the feed displays).
        # Skip "lebron" so the main demo account doesn't auto-like everything.
        if WorkoutLike:
            for plan in plans:
                for user in users:
                    if user.username == "lebron":
                        continue
                    if rng.random() >= 0.45:
                        continue

                    existing_like = WorkoutLike.query.filter_by(
                        user_id=user.id,
                        workout_id=plan.id,
                    ).first()

                    if not existing_like:
                        db.session.add(
                            WorkoutLike(
                                user_id=user.id,
                                workout_id=plan.id,
                            )
                        )

            db.session.commit()

        # Create comments on public WorkoutPlans.
        if WorkoutComment:
            for plan in plans:
                commenters = rng.sample(users, k=min(len(users), rng.randint(1, 3)))

                for user in commenters:
                    existing_comment = WorkoutComment.query.filter_by(
                        user_id=user.id,
                        workout_id=plan.id,
                    ).first()

                    if existing_comment:
                        continue

                    db.session.add(
                        WorkoutComment(
                            user_id=user.id,
                            workout_id=plan.id,
                            body=rng.choice(COMMENTS),
                        )
                    )

            db.session.commit()

        print(f"Seeded {len(DEMO_USERS)} demo users with workouts (current week + 30-day history).")
        print("Created public WorkoutPlans for the community feed.")
        print("Added follows, likes, and comments on public plans.")
        print("Login with username 'lebron' / password 'Password123' to test.")


if __name__ == "__main__":
    seed()