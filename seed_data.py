"""
Development helper: seeds demo users, workouts, follows, likes,
comments, community posts, and workout plans for a realistic demo.

Run from project root:

    python seed_data.py

Demo login:
    username: lebron
    password: Password123

Do NOT commit instance/users.db.
"""

import random
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from app import app, db, User, Workout, WorkoutSet, WorkoutPlan, PersonalRecord

try:
    from app import Follow, FollowRequest, WorkoutLike, WorkoutComment
except ImportError:
    Follow = FollowRequest = WorkoutLike = WorkoutComment = None

try:
    from app import CommunityPost, CommunityPostLike, CommunityPostComment
except ImportError:
    CommunityPost = CommunityPostLike = CommunityPostComment = None


# ─────────────────────────────────────────────────────────────────
#  Users
#  (username, email, bio, profile_public, show_follow_lists)
#
#  Privacy demo showcase:
#    luka    — public profile, hidden follow lists
#               lebron & victor follow them → can view lists
#    damian  — public profile, hidden follow lists
#               steph & shai follow them → can view lists
#    shaq    — public profile, hidden follow lists
#               michael & kd follow them → can view lists
#    kobe    — private profile + hidden follow lists
#               lebron follows them → can view lists despite private profile
#    russell — private profile, follow lists visible to followers
# ─────────────────────────────────────────────────────────────────
DEMO_USERS = [
    # Top NBA stars
    ("lebron",   "lebron@example.com",   "King James in the weight room. Heavy push days and full-body conditioning. GOAT debate settled.",      True,  True),
    ("steph",    "steph@example.com",    "Chef Curry fuelling the grind. Cardio, shooting drills, and high-rep consistency every day.",          True,  True),
    ("michael",  "michael@example.com",  "MJ's training philosophy: no days off. Strength, explosiveness, and the will to be the best.",         True,  True),
    ("shai",     "shai@example.com",     "SGA moving like water. Balanced workouts and elite mobility work. Function over everything.",           True,  True),
    ("victor",   "victor@example.com",   "The Alien dominating leg day. Conditioning and recovery are the secret weapons.",                      True,  True),
    ("kd",       "kd@example.com",       "KD's conditioning is elite. Endless shooting, core work, and pure scorer mentality.",                  True,  True),
    ("giannis",  "giannis@example.com",  "The Greek Freak goes hard every session. Power lifting, sprint drills, and relentless volume.",        True,  True),
    ("luka",     "luka@example.com",     "Luka cooking in the gym. High IQ meets disciplined strength work. Numbers always go up.",              True,  False),  # hidden lists
    ("jayson",   "jayson@example.com",   "Jayson Tatum chasing greatness. Strength and cardio with zero excuses.",                              True,  True),
    ("nikola",   "nikola@example.com",   "Joker's strength is unmatched. Squat, deadlift, clean — the big man lifts heavy.",                    True,  True),
    ("damian",   "damian@example.com",   "Dame Time in the gym too. Game 6 Lillard goes just as hard in training as on the court.",              True,  False),  # hidden lists
    ("kawhi",    "kawhi@example.com",    "The Klaw works in silence. Elite athleticism built through disciplined, methodical sessions.",          True,  True),
    ("kobe",     "kobe@example.com",     "Mamba Mentality. 4am sessions, film study, and zero shortcuts. The standard is the standard.",         False, False),  # private profile + hidden lists
    ("jimmy",    "jimmy@example.com",    "Jimmy Buckets earns everything. Late nights in the gym, cold showers, and max effort always.",          True,  True),
    ("devin",    "devin@example.com",    "Book hitting every session. Elite scorer's mindset applied to every single lift.",                     True,  True),
    ("anthony",  "anthony@example.com",  "Ant-Man with the bounce. Functional fitness, kettlebells, and explosive training every day.",           True,  True),
    ("shaq",     "shaq@example.com",     "Big Diesel in the big-weight room. Old-school bodybuilding, massive volume, protein for days.",         True,  False),  # hidden lists
    ("magic",    "magic@example.com",    "Magic's energy is infectious. Team drills, HIIT, and high energy every single session.",               True,  True),
    ("russell",  "russell@example.com",  "Russ going full throttle. Explosive power, zero rest days, off-season mode permanently activated.",    False, True),   # private profile
    ("larry",    "larry@example.com",    "Larry Legend keeps it old school. Precision training, film study, and a protein shake after every WOD.", True,  True),
]


EXERCISES = [
    ("Bench Press",        40,  130),
    ("Squat",              60,  160),
    ("Deadlift",           70,  180),
    ("Overhead Press",     20,   80),
    ("Barbell Row",        40,  100),
    ("Bicep Curl",         10,   35),
    ("Leg Press",          80,  200),
    ("Incline Press",      30,   90),
    ("Romanian Deadlift",  50,  130),
    ("Leg Curl",           30,   80),
    ("Cable Row",          30,   80),
    ("Tricep Pushdown",    15,   40),
    ("Lateral Raise",       5,   20),
    ("Hip Thrust",         60,  150),
    ("Clean and Jerk",     50,  120),
    ("Snatch",             30,   90),
    ("Kettlebell Swing",   16,   48),
    ("Front Squat",        50,  130),
    ("Chest Press",        30,   90),
    ("Dumbbell Row",       20,   60),
]


# Per-user workout frequency — lower value = more workouts = higher leaderboard volume.
# Targets (at ~10k volume/workout over 61 days):
#   Champion  (>500k): threshold ≤ 0.18  → 50+ workouts
#   Emerald (300-500k): threshold 0.28-0.48 → 32-44 workouts
#   Diamond (180-300k): threshold 0.55-0.68 → 20-27 workouts
#   Platinum(100-180k): threshold 0.75-0.84 → 10-15 workouts
#   Gold     (50-100k): threshold 0.88-0.90 →  6-7  workouts
USER_ACTIVITY = {
    "giannis":  0.10,   # Champion
    "shaq":     0.14,   # Champion
    "lebron":   0.18,   # Champion
    "michael":  0.28,   # Emerald
    "nikola":   0.35,   # Emerald
    "victor":   0.40,   # Emerald
    "kd":       0.44,   # Emerald
    "magic":    0.48,   # Emerald
    "luka":     0.55,   # Diamond
    "russell":  0.58,   # Diamond
    "steph":    0.62,   # Diamond
    "jayson":   0.65,   # Diamond
    "damian":   0.68,   # Diamond
    "kawhi":    0.75,   # Platinum
    "jimmy":    0.78,   # Platinum
    "anthony":  0.80,   # Platinum
    "devin":    0.82,   # Platinum
    "larry":    0.84,   # Platinum
    "shai":     0.88,   # Gold
    "kobe":     0.90,   # Gold
}

# (title_template, description, is_public)
# Descriptions are comma-separated exercise names that match the log_workout picker.
PLAN_TEMPLATES = [
    ("{name}'s Push Day",         "Bench press, Incline bench press, Overhead press, Lateral raises, Tricep pushdown, Cable fly",        True),
    ("{name}'s Pull Day",         "Pull up, Barbell row, Lat pulldown, Bicep curl, Hammer curl, Face pull",                              True),
    ("{name}'s Leg Day",          "Barbell squat, Leg press, Romanian deadlift, Leg curl, Leg extension, Hip thrust, Calf raise",        True),
    ("{name}'s Full Body",        "Barbell squat, Bench press, Deadlift, Pull up, Overhead press, Bicep curl",                           True),
    ("{name}'s Cardio Blast",     "Push up, Plank, Cable crunch, Hanging leg raise, Russian twist, Barbell squat",                       True),
    ("{name}'s Olympic Day",      "Deadlift, Barbell squat, Overhead press, Barbell row, Bench press, Lat pulldown",                     True),
    ("{name}'s Powerlifting Day", "Barbell squat, Bench press, Deadlift, Overhead press, Barbell row",                                   True),
    ("{name}'s HIIT Circuit",     "Barbell squat, Push up, Deadlift, Bicep curl, Tricep pushdown, Plank, Cable crunch",                  True),
    ("{name}'s Upper Body",       "Bench press, Barbell row, Overhead press, Lat pulldown, Bicep curl, Tricep pushdown, Lateral raises", True),
    ("{name}'s Secret Program",   "Bench press, Barbell squat, Deadlift, Overhead press, Barbell row",                                   False),
    ("{name}'s Deload Week",      "Push up, Lat pulldown, Leg curl, Leg extension, Bicep curl, Plank",                                   False),
]


COMMUNITY_POSTS = [
    "Just hit a new PR on deadlift today. Hard work is paying off.",
    "Morning session done. 5am club is no joke but the gains are real.",
    "Pushed through a tough session. Legs are wrecked but the mind is clear.",
    "Rest day today — foam rolling, stretching, and a solid meal. Recovery is training too.",
    "Shared a new workout plan. Give it a try and let me know what you think!",
    "Six weeks into the program and I can already see the difference. Trust the process.",
    "Deload week is humbling but necessary. Next week we go again.",
    "Tried paused squats for the first time. Absolutely brutal. Will do again.",
    "Nutrition is 80% of the game. Meal prepped for the whole week. Feeling prepared.",
    "Nothing beats training with a good partner. Accountability is everything.",
    "New PB on the bench today! Consistency over perfection, always.",
    "Olympic lifting session this morning. The snatch is finally coming together.",
    "Hybrid training week — long run Monday, heavy lifts Wednesday and Friday.",
    "Competed this weekend and finished top 5. So proud of where this journey has taken me.",
    "Full body workout complete. Every muscle group hit and zero regrets.",
    "The mental side of training is just as important as the physical. Stay focused.",
    "Progress check at the 3-month mark. The dedication is visible. Keep going.",
    "New powerlifting plan posted. For those who want to go heavy and heavy only.",
    "Love seeing everyone's progress on the community feed. Keep posting.",
    "Five-rep max on squat today. Getting stronger every single week.",
    "Just wrapped up a 10-week strength block. Volume was insane. PRs across the board.",
    "Mobility work before every session is non-negotiable. Your joints will thank you.",
    "Hit every rep today. Some days you just feel locked in.",
    "Warm-up properly, people. Skipping it is how you get hurt.",
]


WORKOUT_COMMENTS = [
    "Solid session!",
    "This plan looks tough — I'll give it a try.",
    "Nice volume on this workout.",
    "Strong work — the progression is impressive.",
    "That's some serious weight. Goals!",
    "Great structure. Love the push/pull split.",
    "I tried this last week — brutal but effective.",
    "Clean program. Bookmarking this.",
    "The consistency shows. Respect.",
    "Love the focus on compound movements here.",
    "Perfect rep scheme for hypertrophy.",
    "Going to run this next cycle for sure.",
]


POST_COMMENTS = [
    "Keep it up!",
    "That's awesome progress!",
    "Solid work, well done.",
    "Inspiring as always!",
    "Goals! Love seeing this.",
    "This is what consistency looks like.",
    "So proud of you!",
    "Training really is the best therapy.",
    "Respect the grind.",
    "Can't wait to try that plan!",
    "You're an inspiration to the community.",
    "Exactly the mindset we need more of.",
]


# Specific follows wired for the privacy demo.
# These ensure follower-only list access is demonstrable at presentation time.
SPECIFIC_FOLLOWS = [
    # Followers of luka (hidden lists) — can view lists
    ("lebron",  "luka"),
    ("victor",  "luka"),
    # Followers of damian (hidden lists) — can view lists
    ("steph",   "damian"),
    ("shai",    "damian"),
    # Followers of shaq (hidden lists) — can view lists
    ("michael", "shaq"),
    ("kd",      "shaq"),
    # Follower of kobe (private profile + hidden lists) — can view lists despite private profile
    ("lebron",  "kobe"),
    # Mutual follows between pairs for a realistic social graph
    ("kd",      "giannis"),
    ("giannis", "kd"),
    ("nikola",  "kawhi"),
    ("kawhi",   "nikola"),
    ("jimmy",   "magic"),
    ("magic",   "jimmy"),
    ("devin",   "jayson"),
    ("jayson",  "devin"),
    ("anthony", "larry"),
    ("larry",   "anthony"),
    ("lebron",  "steph"),
    ("steph",   "lebron"),
    ("michael", "lebron"),
    ("lebron",  "michael"),
    ("victor",  "shai"),
    ("shai",    "victor"),
]


# Pending follow requests for private users to demo the request flow.
# Format: (requester_username, target_username)
# target must be a private user (profile_public=False)
SPECIFIC_REQUESTS = [
    # Requests to kobe (private profile + hidden lists)
    ("steph",   "kobe"),
    ("kd",      "kobe"),
    ("giannis", "kobe"),
    # Requests to russell (private profile)
    ("victor",  "russell"),
    ("nikola",  "russell"),
]


def set_if_exists(model_obj, field_name, value):
    if hasattr(model_obj, field_name):
        setattr(model_obj, field_name, value)


def seed():
    rng = random.Random(42)

    with app.app_context():
        db.create_all()

        # ── Users ──────────────────────────────────────────────────────
        for username, email, bio, profile_public, show_follow_lists in DEMO_USERS:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(
                    username=username,
                    email=email,
                    password=generate_password_hash("Password123"),
                )
                db.session.add(user)
                db.session.flush()

            set_if_exists(user, "bio",               bio)
            set_if_exists(user, "profile_public",    profile_public)
            set_if_exists(user, "show_follow_lists", show_follow_lists)

        db.session.commit()

        # ── Workouts and sets ──────────────────────────────────────────
        categories   = ["Strength", "Cardio", "Upper Body", "Lower Body", "Full Body", "Olympic", "HIIT"]
        difficulties = ["Beginner", "Intermediate", "Advanced"]

        for username, *_ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()
            if not user:
                continue

            threshold = USER_ACTIVITY.get(username, 0.55)
            for days_ago in range(60, -1, -1):
                if rng.random() >= threshold:
                    continue

                workout_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                    days=days_ago,
                    hours=rng.randint(0, 16),
                )

                date_start = workout_date.replace(hour=0, minute=0, second=0, microsecond=0)
                date_end   = date_start + timedelta(days=1)
                if Workout.query.filter(
                    Workout.user_id == user.id,
                    Workout.date    >= date_start,
                    Workout.date    <  date_end,
                ).first():
                    continue

                workout = Workout(user_id=user.id, date=workout_date)
                set_if_exists(workout, "is_public",   rng.random() < 0.75)
                set_if_exists(workout, "title",       f"{username.title()}'s Training Session")
                set_if_exists(workout, "name",        f"{username.title()}'s Training Session")
                set_if_exists(workout, "description", "Demo workout for the community feed.")
                set_if_exists(workout, "notes",       "Demo workout for the community feed.")
                set_if_exists(workout, "category",    rng.choice(categories))
                set_if_exists(workout, "difficulty",  rng.choice(difficulties))
                db.session.add(workout)
                db.session.flush()

                for ex_name, min_w, max_w in rng.sample(EXERCISES, k=rng.randint(3, 6)):
                    for _ in range(rng.randint(3, 5)):
                        db.session.add(WorkoutSet(
                            workout_id=workout.id,
                            exercise=ex_name,
                            weight=rng.randint(min_w, max_w),
                            reps=rng.randint(4, 12),
                        ))

        db.session.commit()

        # ── Workout plans (public and private) ────────────────────────
        # Build a suffix→desc map so we can fix every plan in the DB by title,
        # regardless of which user owns it (covers user-saved copies too).
        desc_by_suffix = {
            title_tpl.split('}', 1)[1]: desc
            for title_tpl, desc, _ in PLAN_TEMPLATES
        }
        for plan in WorkoutPlan.query.all():
            for suffix, desc in desc_by_suffix.items():
                if plan.title.endswith(suffix):
                    plan.description = desc
                    break

        for username, *_ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()
            if not user:
                continue

            # Create any plans this user is still missing (random sample for variety).
            for title_tpl, desc, is_public in rng.sample(PLAN_TEMPLATES, k=min(6, len(PLAN_TEMPLATES))):
                title = title_tpl.format(name=username.title())
                if WorkoutPlan.query.filter_by(user_id=user.id, title=title).first():
                    continue
                db.session.add(WorkoutPlan(
                    title=title,
                    description=desc,
                    user_id=user.id,
                    is_public=is_public,
                ))

        db.session.commit()

        users = User.query.all()
        plans = WorkoutPlan.query.filter_by(is_public=True).all()

        # ── Personal records derived from workout sets ─────────────────
        for username, *_ in DEMO_USERS:
            user = User.query.filter_by(username=username).first()
            if not user:
                continue

            all_sets = (
                db.session.query(WorkoutSet, Workout.date)
                .join(Workout, Workout.id == WorkoutSet.workout_id)
                .filter(Workout.user_id == user.id)
                .all()
            )

            best = {}
            for ws, date in all_sets:
                key = ws.exercise.strip().lower()
                pts = ws.weight * ws.reps
                if key not in best or pts > best[key]["pts"]:
                    best[key] = {"weight": ws.weight, "reps": ws.reps, "pts": pts, "date": date}

            for key, data in best.items():
                pr = PersonalRecord.query.filter_by(user_id=user.id, exercise=key).first()
                if pr is None:
                    db.session.add(PersonalRecord(
                        user_id=user.id,
                        exercise=key,
                        best_weight=data["weight"],
                        best_reps=data["reps"],
                        date_set=data["date"],
                    ))
                elif data["pts"] > pr.best_weight * pr.best_reps:
                    pr.best_weight = data["weight"]
                    pr.best_reps   = data["reps"]
                    pr.date_set    = data["date"]

        db.session.commit()

        # ── Follows ────────────────────────────────────────────────────
        if Follow:
            # Specific follows for the privacy demo
            for follower_name, followed_name in SPECIFIC_FOLLOWS:
                follower = User.query.filter_by(username=follower_name).first()
                followed = User.query.filter_by(username=followed_name).first()
                if not follower or not followed:
                    continue
                if not Follow.query.filter_by(follower_id=follower.id, followed_id=followed.id).first():
                    db.session.add(Follow(follower_id=follower.id, followed_id=followed.id))

            # Random follows (~28% probability) for a richer social graph
            for follower in users:
                for followed in users:
                    if follower.id == followed.id:
                        continue
                    if rng.random() >= 0.28:
                        continue
                    if not Follow.query.filter_by(follower_id=follower.id, followed_id=followed.id).first():
                        db.session.add(Follow(follower_id=follower.id, followed_id=followed.id))

            db.session.commit()

        # ── Follow requests for private users ─────────────────────────
        if FollowRequest:
            for requester_name, target_name in SPECIFIC_REQUESTS:
                requester = User.query.filter_by(username=requester_name).first()
                target = User.query.filter_by(username=target_name).first()
                if not requester or not target:
                    continue
                # Skip if requester already follows target (would have been seeded above)
                already_follows = Follow.query.filter_by(
                    follower_id=requester.id, followed_id=target.id
                ).first() if Follow else None
                if already_follows:
                    continue
                if not FollowRequest.query.filter_by(
                    requester_id=requester.id, target_id=target.id
                ).first():
                    db.session.add(FollowRequest(
                        requester_id=requester.id,
                        target_id=target.id,
                    ))
            db.session.commit()

        # ── Likes on public workout plans ──────────────────────────────
        if WorkoutLike:
            for plan in plans:
                for u in users:
                    if rng.random() >= 0.40:
                        continue
                    if not WorkoutLike.query.filter_by(user_id=u.id, workout_id=plan.id).first():
                        db.session.add(WorkoutLike(user_id=u.id, workout_id=plan.id))

            db.session.commit()

        # ── Comments on public workout plans ───────────────────────────
        if WorkoutComment:
            for plan in plans:
                for u in rng.sample(users, k=min(len(users), rng.randint(2, 6))):
                    if WorkoutComment.query.filter_by(user_id=u.id, workout_id=plan.id).first():
                        continue
                    db.session.add(WorkoutComment(
                        user_id=u.id,
                        workout_id=plan.id,
                        body=rng.choice(WORKOUT_COMMENTS),
                    ))

            db.session.commit()

        # ── Community posts ────────────────────────────────────────────
        if CommunityPost:
            post_pool = list(COMMUNITY_POSTS)
            rng.shuffle(post_pool)
            pool_idx = 0

            for username, *_ in DEMO_USERS:
                user = User.query.filter_by(username=username).first()
                if not user:
                    continue
                if CommunityPost.query.filter_by(user_id=user.id).count() >= 3:
                    continue

                user_plans = WorkoutPlan.query.filter_by(user_id=user.id, is_public=True).all()
                n_posts = rng.randint(2, 4)

                for _ in range(n_posts):
                    body = post_pool[pool_idx % len(post_pool)]
                    pool_idx += 1
                    linked_plan = rng.choice(user_plans) if user_plans and rng.random() < 0.4 else None
                    created_offset = rng.randint(0, 30)
                    db.session.add(CommunityPost(
                        user_id=user.id,
                        body=body,
                        plan_id=linked_plan.id if linked_plan else None,
                        is_public=True,
                        created_at=datetime.now(timezone.utc) - timedelta(days=created_offset),
                    ))

            db.session.commit()

            posts = CommunityPost.query.filter_by(is_public=True).all()

            # Community post likes
            if CommunityPostLike:
                for post in posts:
                    for u in users:
                        if rng.random() >= 0.38:
                            continue
                        if not CommunityPostLike.query.filter_by(user_id=u.id, post_id=post.id).first():
                            db.session.add(CommunityPostLike(user_id=u.id, post_id=post.id))
                db.session.commit()

            # Community post comments
            if CommunityPostComment:
                for post in posts:
                    for u in rng.sample(users, k=min(len(users), rng.randint(1, 4))):
                        if CommunityPostComment.query.filter_by(user_id=u.id, post_id=post.id).first():
                            continue
                        db.session.add(CommunityPostComment(
                            user_id=u.id,
                            post_id=post.id,
                            body=rng.choice(POST_COMMENTS),
                        ))
                db.session.commit()

        print(f"\nSeeded {len(DEMO_USERS)} NBA players with workouts, plans, follows, follow requests, likes, and posts.")
        print("\nNBA roster:")
        for username, *_ in DEMO_USERS:
            print(f"  {username}")
        print("\nPrivacy demo users:")
        print("  luka    — public profile, hidden follow lists")
        print("            lebron and victor follow them → can view their lists")
        print("  damian  — public profile, hidden follow lists")
        print("            steph and shai follow them → can view their lists")
        print("  shaq    — public profile, hidden follow lists")
        print("            michael and kd follow them → can view their lists")
        print("  kobe    — private profile + hidden follow lists")
        print("            lebron follows them (accepted); steph/kd/giannis have pending requests")
        print("  russell — private profile, follow lists visible to followers")
        print("            victor/nikola have pending follow requests")
        print("\nFollow request demo:")
        print("  Login as kobe    / Password123 → visit Profile to see 3 pending requests")
        print("  Login as russell / Password123 → visit Profile to see 2 pending requests")
        print("\nLogin: username 'lebron' / password 'Password123'")


if __name__ == "__main__":
    seed()
