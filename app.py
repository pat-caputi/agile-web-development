from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, or_
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import os
import re
import json

# ── App setup ──
app = Flask(__name__)
app.secret_key = "your_secret_key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

PROFILE_UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads", "profile_pictures")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app.config["PROFILE_UPLOAD_FOLDER"] = PROFILE_UPLOAD_FOLDER
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)


def allowed_image_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


# ── Database models ──
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(280), default="")
    profile_photo = db.Column(db.String(255), default="")
    profile_public = db.Column(db.Boolean, default=True)


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class WorkoutSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    exercise = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    reps = db.Column(db.Integer, nullable=False)


class PersonalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercise = db.Column(db.String(100), nullable=False)
    best_weight = db.Column(db.Float, nullable=False)
    best_reps = db.Column(db.Integer, nullable=False)
    date_set = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'exercise', name='uq_user_exercise'),
    )


class WorkoutPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    user = db.relationship("User", backref="workout_plans")


# ------------------------------------------------------------
# Social / Public Sharing Models
# ------------------------------------------------------------

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("follower_id", "followed_id", name="unique_follow"),
    )


class WorkoutLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey("workout_plan.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "workout_id", name="unique_workout_like"),
    )


class WorkoutComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey("workout_plan.id"), nullable=False)

    user = db.relationship("User", backref="workout_comments")


# ── Create DB ──
with app.app_context():
    db.create_all()


# ── Rank tier thresholds ──
TIER_THRESHOLDS = [
    (25000, 'Diamond',  '💎', 'rb-diamond'),
    (12000, 'Platinum', '🔷', 'rb-platinum'),
    (5000,  'Gold',     '🥇', 'rb-gold'),
    (2000,  'Silver',   '🥈', 'rb-silver'),
    (500,   'Bronze',   '🥉', 'rb-bronze'),
    (0,     'Unranked', '—',  'rb-unranked'),
]

MUSCLE_GROUPS = ['chest', 'back', 'legs', 'shoulders', 'arms', 'core']

MUSCLE_CONFIG = {
    'chest':     {'label': 'Chest',     'letter': 'C', 'icon_bg': '#EEEDFE', 'icon_color': '#534AB7'},
    'back':      {'label': 'Back',      'letter': 'B', 'icon_bg': '#E1F5EE', 'icon_color': '#085041'},
    'legs':      {'label': 'Legs',      'letter': 'L', 'icon_bg': '#FAECE7', 'icon_color': '#712B13'},
    'shoulders': {'label': 'Shoulders', 'letter': 'S', 'icon_bg': '#FAEEDA', 'icon_color': '#633806'},
    'arms':      {'label': 'Arms',      'letter': 'A', 'icon_bg': '#F1EFE8', 'icon_color': '#444441'},
    'core':      {'label': 'Core',      'letter': 'C', 'icon_bg': '#FBEAF0', 'icon_color': '#72243E'},
}

EXERCISE_MUSCLE_MAP = {
    # chest
    'bench press': 'chest', 'incline bench press': 'chest', 'decline bench press': 'chest',
    'cable fly': 'chest', 'chest fly': 'chest', 'push up': 'chest',
    'dumbbell press': 'chest', 'dumbbell fly': 'chest', 'pec deck': 'chest',
    'dumbbell chest fly': 'chest', 'dumbbell bench press': 'chest',
    # back
    'deadlift': 'back', 'pull up': 'back', 'chin up': 'back',
    'barbell row': 'back', 'lat pulldown': 'back', 'cable row': 'back',
    'seated row': 'back', 't-bar row': 'back', 'single arm row': 'back',
    'seated cable row': 'back', 'single-arm dumbbell row': 'back', 'chest-supported row': 'back',
    # legs
    'barbell squat': 'legs', 'squat': 'legs', 'leg press': 'legs',
    'romanian deadlift': 'legs', 'rdl': 'legs', 'leg curl': 'legs',
    'leg extension': 'legs', 'lunge': 'legs', 'bulgarian split squat': 'legs',
    'calf raise': 'legs', 'hack squat': 'legs', 'goblet squat': 'legs',
    'dumbbell lunge': 'legs', 'hip thrust': 'legs', 'sumo deadlift': 'legs', 'step up': 'legs',
    # shoulders
    'overhead press': 'shoulders', 'ohp': 'shoulders', 'military press': 'shoulders',
    'lateral raise': 'shoulders', 'lateral raises': 'shoulders',
    'arnold press': 'shoulders', 'front raise': 'shoulders',
    'face pull': 'shoulders', 'upright row': 'shoulders',
    'dumbbell shoulder press': 'shoulders',
    'rear delt fly': 'shoulders', 'cable lateral raise': 'shoulders',
    # arms
    'bicep curl': 'arms', 'hammer curl': 'arms', 'preacher curl': 'arms',
    'concentration curl': 'arms', 'cable curl': 'arms',
    'tricep pushdown': 'arms', 'tricep extension': 'arms',
    'skull crusher': 'arms', 'close grip bench press': 'arms', 'dip': 'arms',
    'barbell curl': 'arms', 'tricep dip': 'arms', 'overhead tricep extension': 'arms',
    # core
    'plank': 'core', 'cable crunch': 'core', 'crunch': 'core',
    'hanging leg raise': 'core', 'leg raise': 'core',
    'ab wheel': 'core', 'russian twist': 'core', 'sit up': 'core',
    'ab crunch machine': 'core', 'dead bug': 'core',
}


def get_tier(points):
    v = int(points or 0)
    for i, (threshold, name, icon, css) in enumerate(TIER_THRESHOLDS):
        if v >= threshold:
            if i == 0:
                pct, next_threshold, next_name = 100, None, None
            else:
                next_threshold, next_name, _, _ = TIER_THRESHOLDS[i - 1]
                pct = min(99, int((v - threshold) / (next_threshold - threshold) * 100))
            return {
                'name': name, 'icon': icon, 'css': css,
                'points': v, 'pct': pct,
                'current_threshold': threshold,
                'next_threshold': next_threshold,
                'next_name': next_name,
            }
    return {
        'name': 'Unranked', 'icon': '—', 'css': 'rb-unranked',
        'points': 0, 'pct': 0,
        'current_threshold': 0, 'next_threshold': 500, 'next_name': 'Bronze',
    }


def get_muscle_group_data(user_id):
    """Returns (muscle_data dict, overall_tier dict) based on the user's PRs."""
    prs = PersonalRecord.query.filter_by(user_id=user_id).all()

    group_points = {g: 0 for g in MUSCLE_GROUPS}
    group_exercises = {g: [] for g in MUSCLE_GROUPS}

    for pr in prs:
        group = EXERCISE_MUSCLE_MAP.get(pr.exercise.lower().strip())
        if group:
            pts = int(pr.best_weight * pr.best_reps)
            group_points[group] += pts
            group_exercises[group].append({'name': pr.exercise.title(), 'pts': pts})

    for g in MUSCLE_GROUPS:
        group_exercises[g].sort(key=lambda x: x['pts'], reverse=True)

    muscle_data = {}
    for g in MUSCLE_GROUPS:
        cfg = MUSCLE_CONFIG[g]
        tier = get_tier(group_points[g])
        muscle_data[g] = {
            'label':      cfg['label'],
            'letter':     cfg['letter'],
            'icon_bg':    cfg['icon_bg'],
            'icon_color': cfg['icon_color'],
            'tier_name':  tier['name'],
            'tier_icon':  tier['icon'],
            'css':        tier['css'],
            'points':     tier['points'],
            'pct':        tier['pct'],
            'current_threshold': tier['current_threshold'],
            'next_threshold':    tier['next_threshold'],
            'next_name':         tier['next_name'],
            'exercises':  group_exercises[g][:3],
        }

    total_points = sum(group_points.values())
    avg_points = total_points / len(MUSCLE_GROUPS)
    overall_t = get_tier(avg_points)
    overall_tier = {**overall_t, 'total_points': total_points}

    return muscle_data, overall_tier


# ── Helpers ──
def get_start_of_week():
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)


def get_current_user():
    if 'user_id' not in session:
        return None
    return db.session.get(User, session['user_id'])


def initials(name):
    parts = (name or "").strip().split()

    if not parts:
        return "U"

    if len(parts) == 1:
        return parts[0][:2].upper()

    return (parts[0][0] + parts[1][0]).upper()


def get_plan_tags(plan):
    text = ((plan.title or '') + ' ' + (plan.description or '')).lower()
    tags = []
    if any(w in text for w in ['strength', 'powerlifting', 'deadlift', 'squat', 'bench', 'weightlift']):
        tags.append('Strength')
    if any(w in text for w in ['cardio', 'running', 'cycling', 'hiit', 'endurance', 'aerobic']):
        tags.append('Cardio')
    if any(w in text for w in ['beginner', 'starter', 'easy', 'basic', 'novice']):
        tags.append('Beginner')
    if any(w in text for w in ['intermediate', 'moderate']):
        tags.append('Intermediate')
    if any(w in text for w in ['advanced', 'expert', 'elite']):
        tags.append('Advanced')
    if any(w in text for w in ['upper body', 'chest', 'back', 'shoulder', 'arm', 'push day', 'pull day']):
        tags.append('Upper Body')
    if any(w in text for w in ['lower body', 'leg day', 'quad', 'hamstring', 'glute', 'calf']):
        tags.append('Lower Body')
    if any(w in text for w in ['core', 'abs', 'plank', 'crunch']):
        tags.append('Core')
    if any(w in text for w in ['full body', 'full-body', 'total body']):
        tags.append('Full Body')
    if not tags:
        tags.append('Workout Plan')
    return tags[:3]


@app.context_processor
def inject_logged_in_user():
    if "user_id" in session:
        return {
            "nav_user": db.session.get(User, session["user_id"]),
            "initials": initials,
        }

    return {
        "nav_user": None,
        "initials": initials,
    }


def get_user_rank(user_id):
    start_of_week = get_start_of_week()

    leaderboard_data = (
        db.session.query(
            User.id,
            func.sum(WorkoutSet.weight * WorkoutSet.reps).label('weekly_volume')
        )
        .join(Workout, Workout.user_id == User.id)
        .join(WorkoutSet, WorkoutSet.workout_id == Workout.id)
        .filter(Workout.date >= start_of_week)
        .group_by(User.id)
        .order_by(func.sum(WorkoutSet.weight * WorkoutSet.reps).desc())
        .all()
    )

    for index, item in enumerate(leaderboard_data, start=1):
        if item.id == user_id:
            return index

    return None


def get_pr_list(user_id):
    """Best set per exercise for a user. Uses PersonalRecord if populated; falls back to WorkoutSet."""
    prs = (
        PersonalRecord.query
        .filter_by(user_id=user_id)
        .order_by(PersonalRecord.best_weight.desc())
        .all()
    )

    if prs:
        result = []
        for pr in prs:
            reps = pr.best_reps or 0
            e1rm = round(pr.best_weight * (1 + reps / 30), 1) if reps > 1 else pr.best_weight
            result.append({
                'exercise':    pr.exercise,
                'best_weight': pr.best_weight,
                'best_reps':   reps,
                'date_set':    pr.date_set,
                'e1rm':        e1rm,
            })
        return result

    # Fallback: derive best set per exercise directly from WorkoutSet data
    all_sets = (
        db.session.query(WorkoutSet, Workout.date)
        .join(Workout, Workout.id == WorkoutSet.workout_id)
        .filter(Workout.user_id == user_id)
        .all()
    )

    best = {}
    for ws, date in all_sets:
        key = (ws.exercise or '').lower().strip()
        if not key:
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = (ws, date)
        else:
            ews, edate = existing
            w,  ew = ws.weight or 0, ews.weight or 0
            r,  er = ws.reps   or 0, ews.reps   or 0
            if (w > ew
                    or (w == ew and r > er)
                    or (w == ew and r == er and date and edate and date > edate)):
                best[key] = (ws, date)

    result = []
    for ws, date in sorted(best.values(), key=lambda x: (x[0].weight or 0), reverse=True):
        w = ws.weight or 0
        r = ws.reps   or 0
        e1rm = round(w * (1 + r / 30), 1) if r > 1 else w
        result.append({
            'exercise':    ws.exercise,
            'best_weight': w,
            'best_reps':   r,
            'date_set':    date,
            'e1rm':        e1rm,
        })

    return result


# ── Routes ──
@app.route('/')
def home():
    return redirect('/login')


# REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm']

        if not username:
            flash("Username is required")
            return render_template('register.html', username=username, email=email)

        if not email:
            flash("Email is required")
            return render_template('register.html', username=username, email=email)

        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            flash("Please enter a valid email address")
            return render_template('register.html', username=username, email=email)

        if len(password) < 8:
            flash("Password must be at least 8 characters long")
            return render_template('register.html', username=username, email=email)

        if not re.search(r'[A-Z]', password):
            flash("Password must contain at least one uppercase letter")
            return render_template('register.html', username=username, email=email)

        if not re.search(r'[0-9]', password):
            flash("Password must contain at least one number")
            return render_template('register.html', username=username, email=email)

        if password != confirm:
            flash("Passwords do not match")
            return render_template('register.html', username=username, email=email)

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists")
            return render_template('register.html', username=username, email=email)

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash("Email already exists")
            return render_template('register.html', username=username, email=email)

        hashed_pw = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_pw
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect('/login')

    return render_template('register.html', username="", email="")


# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form['username'].strip().lower()
        password = request.form['password']

        user = User.query.filter(
            or_(
                func.lower(User.username) == login_input,
                func.lower(User.email) == login_input
            )
        ).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect('/dashboard')
        else:
            flash("Invalid username/email or password")

    return render_template('login.html')


# DASHBOARD
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    today = datetime.now()
    current_hour = today.hour

    if current_hour < 12:
        greeting = "Good morning"
        emoji = "☀️"
    elif current_hour < 18:
        greeting = "Good afternoon"
        emoji = "🌤️"
    else:
        greeting = "Good evening"
        emoji = "🌙"
    
    start_of_week = get_start_of_week()

    workouts_count = (
        db.session.query(func.count(func.distinct(Workout.id)))
        .join(WorkoutSet, WorkoutSet.workout_id == Workout.id)
        .filter(
            Workout.user_id == session['user_id'],
            Workout.date >= start_of_week
        )
        .scalar()
    )

    weekly_sets = db.session.query(WorkoutSet).join(Workout).filter(
        Workout.user_id == session['user_id'],
        Workout.date >= start_of_week
    ).all()

    weekly_volume = sum(ws.weight * ws.reps for ws in weekly_sets)
    rank = get_user_rank(session['user_id'])
    total_users = User.query.count()

    top_users = (
        db.session.query(
            User.id,
            User.username,
            User.profile_photo,
            func.sum(WorkoutSet.weight * WorkoutSet.reps).label('weekly_volume')
        )
        .join(Workout, Workout.user_id == User.id)
        .join(WorkoutSet, WorkoutSet.workout_id == Workout.id)
        .filter(Workout.date >= start_of_week)
        .group_by(User.id, User.username, User.profile_photo)
        .order_by(func.sum(WorkoutSet.weight * WorkoutSet.reps).desc())
        .limit(5)
        .all()
    )

    return render_template(
    'dashboard.html',
    user=user,
    today=today,
    greeting=greeting,
    emoji=emoji,
    weekly_volume=weekly_volume,
    workouts_count=workouts_count,
    streak=12,
    rank=rank,
    total_users=total_users,
    top_users=top_users,
)


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# LOG WORKOUT
PLANS_DATA = {
    "push": {
        "name": "Push day",
        "exercises": ["Bench press", "Incline bench press", "Overhead press", "Lateral raises", "Tricep pushdown", "Cable fly"]
    },
    "pull": {
        "name": "Pull day",
        "exercises": ["Pull up", "Barbell row", "Lat pulldown", "Bicep curl", "Hammer curl", "Face pull"]
    },
    "legs": {
        "name": "Leg day",
        "exercises": ["Barbell squat", "Leg press", "Romanian deadlift", "Leg curl", "Leg extension", "Hip thrust", "Calf raise"]
    },
    "upper": {
        "name": "Upper body",
        "exercises": ["Bench press", "Barbell row", "Overhead press", "Lat pulldown", "Bicep curl", "Tricep pushdown", "Lateral raises", "Face pull"]
    },
    "arms_core": {
        "name": "Arms & core",
        "exercises": ["Barbell curl", "Skull crusher", "Hammer curl", "Tricep pushdown", "Plank", "Cable crunch"]
    },
    "full_body": {
        "name": "Full body",
        "exercises": ["Barbell squat", "Bench press", "Deadlift", "Pull up", "Overhead press", "Leg press", "Bicep curl", "Plank"]
    }
}
@app.route('/log_workout', methods=['GET', 'POST'])
def log_workout():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    if request.method == 'POST':
        raw = request.form.get('workout_data', '[]')

        try:
            sets = json.loads(raw)
        except json.JSONDecodeError:
            sets = []

        if not sets:
            flash("Please add at least one workout set before saving.")
            return redirect('/log_workout')

        workout = Workout(user_id=session['user_id'])
        db.session.add(workout)
        db.session.flush()

        for item in sets:
            ws = WorkoutSet(
                workout_id=workout.id,
                exercise=item['exercise'],
                weight=float(item['weight']),
                reps=int(item['reps'])
            )
            db.session.add(ws)

        # Detect and update personal records
        for item in sets:
            exercise_key = item['exercise'].strip().lower()
            weight = float(item['weight'])
            reps = int(item['reps'])
            new_pts = weight * reps

            pr = PersonalRecord.query.filter_by(
                user_id=session['user_id'],
                exercise=exercise_key
            ).first()

            if pr is None:
                db.session.add(PersonalRecord(
                    user_id=session['user_id'],
                    exercise=exercise_key,
                    best_weight=weight,
                    best_reps=reps,
                ))
            elif new_pts > pr.best_weight * pr.best_reps:
                pr.best_weight = weight
                pr.best_reps = reps
                pr.date_set = datetime.utcnow()

        db.session.commit()
        flash("Workout saved successfully!")
        return redirect('/dashboard')

    today = datetime.now()

    selected_plan_key = request.args.get("plan", "push")
    selected_plan = PLANS_DATA.get(selected_plan_key, PLANS_DATA["push"])

    return render_template(
        'log_workout.html',
        today=today,
        user=user,
        rank=get_user_rank(session['user_id']),
        selected_plan=selected_plan
    )


@app.route('/test_add_workout')
def test_add_workout():
    if 'user_id' not in session:
        return redirect('/login')

    workout = Workout(user_id=session['user_id'])
    db.session.add(workout)
    db.session.commit()

    return redirect('/dashboard')


# LEADERBOARD
@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    start_of_week = get_start_of_week()

    leaderboard_data = (
        db.session.query(
            User.id,
            User.username,
            User.profile_photo,
            func.count(func.distinct(Workout.id)).label('workouts_count'),
            func.sum(WorkoutSet.weight * WorkoutSet.reps).label('weekly_volume')
        )
        .join(Workout, Workout.user_id == User.id)
        .join(WorkoutSet, WorkoutSet.workout_id == Workout.id)
        .filter(Workout.date >= start_of_week)
        .group_by(User.id, User.username, User.profile_photo)
        .order_by(func.sum(WorkoutSet.weight * WorkoutSet.reps).desc())
        .all()
    )

    all_prs = PersonalRecord.query.all()
    user_group_pts = {}
    for pr in all_prs:
        uid = pr.user_id
        group = EXERCISE_MUSCLE_MAP.get(pr.exercise.lower().strip())
        if group:
            user_group_pts.setdefault(uid, {g: 0 for g in MUSCLE_GROUPS})
            user_group_pts[uid][group] += int(pr.best_weight * pr.best_reps)
    tier_map = {
        uid: get_tier(sum(gpts.values()) / len(MUSCLE_GROUPS))
        for uid, gpts in user_group_pts.items()
    }

    # PR count and strength score per user
    pr_count_map = {}
    for pr in all_prs:
        pr_count_map[pr.user_id] = pr_count_map.get(pr.user_id, 0) + 1

    strength_map = {uid: tier['points'] for uid, tier in tier_map.items()}

    # Achievement badges — one winner per category
    badges_map = {}
    if leaderboard_data:
        vol_w = max(leaderboard_data, key=lambda r: r.weekly_volume or 0)
        badges_map.setdefault(vol_w.id, []).append('vol')
        freq_w = max(leaderboard_data, key=lambda r: r.workouts_count or 0)
        badges_map.setdefault(freq_w.id, []).append('freq')
    if strength_map:
        badges_map.setdefault(max(strength_map, key=strength_map.get), []).append('str')
    if pr_count_map:
        badges_map.setdefault(max(pr_count_map, key=pr_count_map.get), []).append('pr')

    return render_template(
        'leaderboard.html',
        leaderboard_data=leaderboard_data,
        tier_map=tier_map,
        pr_count_map=pr_count_map,
        strength_map=strength_map,
        badges_map=badges_map,
        current_user_id=session['user_id'],
        user=user,
        rank=get_user_rank(session['user_id']),
        today=datetime.now(timezone.utc),
    )


# PLANS
@app.route('/plans')
def plans():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    user_plans = (
        WorkoutPlan.query
        .filter_by(user_id=session['user_id'])
        .order_by(WorkoutPlan.id.desc())
        .all()
    )
    tags_map = {p.id: get_plan_tags(p) for p in user_plans}

    return render_template(
        'plans.html',
        user=user,
        rank=get_user_rank(session['user_id']),
        user_plans=user_plans,
        tags_map=tags_map,
    )

@app.route('/plans/create', methods=['POST'])
def create_plan():
    user, err = _require_login()
    if err:
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    title = request.form.get('title', '').strip()
    exercises = request.form.getlist('exercises')

    if not title:
        return jsonify({"ok": False, "error": "Plan name is required."}), 400
    if not exercises:
        return jsonify({"ok": False, "error": "Please select at least one exercise."}), 400
    if len(title) > 120:
        return jsonify({"ok": False, "error": "Plan name must be 120 characters or fewer."}), 400

    description = ', '.join(exercises)
    plan = WorkoutPlan(title=title, description=description, user_id=user.id, is_public=False)
    db.session.add(plan)
    db.session.commit()
    return jsonify({"ok": True, "plan_id": plan.id})


@app.route('/plans/<int:plan_id>/edit', methods=['POST'])
def edit_plan(plan_id):
    user, err = _require_login()
    if err:
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    plan = db.session.get(WorkoutPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        return jsonify({"ok": False, "error": "Not found"}), 404

    title = request.form.get('title', '').strip()
    exercises = request.form.getlist('exercises')

    if not title:
        return jsonify({"ok": False, "error": "Plan name is required."}), 400
    if not exercises:
        return jsonify({"ok": False, "error": "Please select at least one exercise."}), 400
    if len(title) > 120:
        return jsonify({"ok": False, "error": "Plan name must be 120 characters or fewer."}), 400

    plan.title = title
    plan.description = ', '.join(exercises)
    db.session.commit()
    return jsonify({"ok": True})


@app.route('/plans/<int:plan_id>/delete', methods=['POST'])
def delete_plan(plan_id):
    user, err = _require_login()
    if err:
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    plan = db.session.get(WorkoutPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        return jsonify({"ok": False, "error": "Not found"}), 404

    db.session.delete(plan)
    db.session.commit()
    return jsonify({"ok": True})


@app.route('/calendar')
def calendar():
    if 'user_id' not in session:
        return redirect('/login')

    schedule_data = {
        "2026-05-07": "push",
        "2026-05-08": "legs",
        "2026-05-10": "pull"
    }

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    return render_template(
        'calendar.html',
        schedule_data=schedule_data,
        user=user,
        rank=get_user_rank(session['user_id'])
    )




# PROFILE
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    if request.method == 'POST':
        user.bio = request.form.get('bio', '').strip()[:280]

        photo = request.files.get('profile_photo')

        if photo and photo.filename:
            if not allowed_image_file(photo.filename):
                flash("Please upload a valid image file: png, jpg, jpeg, gif, or webp.")
                return redirect(url_for('profile'))

            original_filename = secure_filename(photo.filename)
            extension = original_filename.rsplit(".", 1)[1].lower()
            unique_filename = f"user_{user.id}_{uuid4().hex}.{extension}"

            save_path = os.path.join(app.config["PROFILE_UPLOAD_FOLDER"], unique_filename)
            photo.save(save_path)

            user.profile_photo = f"uploads/profile_pictures/{unique_filename}"

        db.session.commit()
        flash("Profile updated successfully.")
        return redirect(url_for('profile'))

    workouts_count = (
        db.session.query(func.count(Workout.id))
        .filter(Workout.user_id == session['user_id'])
        .scalar()
    )

    rank = get_user_rank(session['user_id'])

    recent_workouts = (
        Workout.query
        .filter_by(user_id=session['user_id'])
        .order_by(Workout.date.desc())
        .limit(5)
        .all()
    )

    workout_cards = []

    for workout in recent_workouts:
        sets = WorkoutSet.query.filter_by(workout_id=workout.id).all()
        total_volume = sum(s.weight * s.reps for s in sets)

        exercise_names = []
        for s in sets:
            if s.exercise not in exercise_names:
                exercise_names.append(s.exercise)

        workout_cards.append({
            "date": workout.date,
            "name": "Workout",
            "exercises": exercise_names,
            "volume": total_volume
        })

    prs = PersonalRecord.query.filter_by(user_id=session['user_id']).all()
    prs.sort(key=lambda p: p.best_weight * p.best_reps, reverse=True)

    pr_list = [{
        'exercise': p.exercise.title(),
        'weight': p.best_weight,
        'reps': p.best_reps,
        'pts': int(p.best_weight * p.best_reps),
        'group': EXERCISE_MUSCLE_MAP.get(p.exercise.lower().strip(), 'other'),
        'css': MUSCLE_CONFIG.get(
            EXERCISE_MUSCLE_MAP.get(p.exercise.lower().strip()), {}
        ).get('icon_bg', '#f0f0f0'),
        'css_color': MUSCLE_CONFIG.get(
            EXERCISE_MUSCLE_MAP.get(p.exercise.lower().strip()), {}
        ).get('icon_color', '#333'),
    } for p in prs]

    return render_template(
        'profile.html',
        user=user,
        workouts_count=workouts_count,
        rank=rank,
        recent_workouts=workout_cards,
        pr_list=pr_list,
    )


# RANKS
@app.route('/ranks')
def ranks():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    muscle_data, overall_tier = get_muscle_group_data(session['user_id'])

    return render_template(
        'ranks.html',
        user=user,
        rank=get_user_rank(session['user_id']),
        muscle_data=muscle_data,
        muscle_groups=MUSCLE_GROUPS,
        overall_tier=overall_tier,
    )


# ------------------------------------------------------------
# Social / Public Sharing Routes
# ------------------------------------------------------------

def _require_login():
    """Returns (user, None) on success or (None, redirect_response) when not logged in."""
    if 'user_id' not in session:
        return None, redirect('/login')
    user = db.session.get(User, session['user_id'])
    if user is None:
        session.clear()
        return None, redirect('/login')
    return user, None


@app.route("/feed")
def public_feed():
    user, err = _require_login()
    if err:
        return err

    feed_filter = request.args.get("filter", "all")
    base_q = WorkoutPlan.query.filter_by(is_public=True)

    if feed_filter == "liked":
        plans = (
            base_q
            .outerjoin(WorkoutLike, WorkoutLike.workout_id == WorkoutPlan.id)
            .group_by(WorkoutPlan.id)
            .order_by(func.count(WorkoutLike.id).desc(), WorkoutPlan.id.desc())
            .all()
        )
    elif feed_filter == "following":
        followed_ids = [
            f.followed_id
            for f in Follow.query.filter_by(follower_id=user.id).all()
        ]
        plans = (
            base_q
            .filter(WorkoutPlan.user_id.in_(followed_ids))
            .order_by(WorkoutPlan.id.desc())
            .all()
        ) if followed_ids else []
    else:
        plans = base_q.order_by(WorkoutPlan.id.desc()).all()

    plan_ids = [p.id for p in plans]
    likes_map = {}
    comments_map = {}
    comments_preview_map = {}
    liked_by_user_set = set()

    if plan_ids:
        like_rows = (
            db.session.query(WorkoutLike.workout_id, func.count(WorkoutLike.id))
            .filter(WorkoutLike.workout_id.in_(plan_ids))
            .group_by(WorkoutLike.workout_id)
            .all()
        )
        likes_map = {wid: cnt for wid, cnt in like_rows}

        comment_rows = (
            db.session.query(WorkoutComment.workout_id, func.count(WorkoutComment.id))
            .filter(WorkoutComment.workout_id.in_(plan_ids))
            .group_by(WorkoutComment.workout_id)
            .all()
        )
        comments_map = {wid: cnt for wid, cnt in comment_rows}

        liked_by_user_set = {
            lk.workout_id for lk in
            WorkoutLike.query.filter(
                WorkoutLike.workout_id.in_(plan_ids),
                WorkoutLike.user_id == user.id
            ).all()
        }

        for pid in plan_ids:
            preview = (
                WorkoutComment.query
                .filter_by(workout_id=pid)
                .order_by(WorkoutComment.created_at.desc())
                .limit(2)
                .all()
            )
            if preview:
                comments_preview_map[pid] = preview

    tags_map = {p.id: get_plan_tags(p) for p in plans}

    return render_template(
        "feed.html",
        plans=plans,
        feed_filter=feed_filter,
        likes_map=likes_map,
        comments_map=comments_map,
        comments_preview_map=comments_preview_map,
        liked_by_user_set=liked_by_user_set,
        tags_map=tags_map,
    )


@app.route("/u/<username>")
def public_profile(username):
    user, err = _require_login()
    if err:
        return err

    profile_user = User.query.filter_by(username=username).first_or_404()
    is_own_profile = profile_user.id == user.id
    active_tab = request.args.get("tab", "plans")

    is_following = Follow.query.filter_by(
        follower_id=user.id, followed_id=profile_user.id
    ).first() is not None

    followers_count = Follow.query.filter_by(followed_id=profile_user.id).count()
    following_count = Follow.query.filter_by(follower_id=profile_user.id).count()

    profile_visible = profile_user.profile_public or is_own_profile

    # Defaults — safe fallbacks used when profile is private or data is absent
    public_plans       = []
    public_plans_count = 0
    total_workouts     = 0
    total_volume       = 0
    pr_count           = 0
    personal_records   = []
    workouts_this_week = 0
    likes_map          = {}
    comments_map       = {}
    tags_map           = {}
    badges             = []
    activity           = []

    if profile_visible:
        public_plans = (
            WorkoutPlan.query
            .filter_by(user_id=profile_user.id, is_public=True)
            .order_by(WorkoutPlan.id.desc())
            .all()
        )
        public_plans_count = len(public_plans)

        total_workouts = Workout.query.filter_by(user_id=profile_user.id).count()

        vol_row = (
            db.session.query(func.sum(WorkoutSet.weight * WorkoutSet.reps))
            .join(Workout, Workout.id == WorkoutSet.workout_id)
            .filter(Workout.user_id == profile_user.id)
            .scalar()
        )
        total_volume = int(vol_row or 0)

        pr_count = PersonalRecord.query.filter_by(user_id=profile_user.id).count()
        personal_records = get_pr_list(profile_user.id)

        start_of_week = get_start_of_week()
        workouts_this_week = Workout.query.filter(
            Workout.user_id == profile_user.id,
            Workout.date >= start_of_week
        ).count()

        # Per-plan engagement data
        plan_ids = [p.id for p in public_plans]
        if plan_ids:
            like_rows = (
                db.session.query(WorkoutLike.workout_id, func.count(WorkoutLike.id))
                .filter(WorkoutLike.workout_id.in_(plan_ids))
                .group_by(WorkoutLike.workout_id)
                .all()
            )
            likes_map = {wid: cnt for wid, cnt in like_rows}

            comment_rows = (
                db.session.query(WorkoutComment.workout_id, func.count(WorkoutComment.id))
                .filter(WorkoutComment.workout_id.in_(plan_ids))
                .group_by(WorkoutComment.workout_id)
                .all()
            )
            comments_map = {wid: cnt for wid, cnt in comment_rows}

        tags_map = {p.id: get_plan_tags(p) for p in public_plans}

        # Achievement badges
        if total_workouts == 0:
            badges.append(('Getting Started',   '🌱', 'badge-new'))
        else:
            badges.append(('New Member',        '👋', 'badge-new'))
        if public_plans_count >= 1:
            badges.append(('Community Sharer',  '📤', 'badge-share'))
        if total_workouts >= 10 or workouts_this_week >= 2:
            badges.append(('Consistent Trainer','🗓️',  'badge-consistent'))
        if (pr_count >= 3) or (len(personal_records) >= 3):
            badges.append(('PR Machine',        '🏆', 'badge-pr'))
        if any(r['best_weight'] >= 100 for r in personal_records):
            badges.append(('100kg Club',        '💯', 'badge-100kg'))
        if total_volume >= 5000:
            badges.append(('Strength Builder',  '🔩', 'badge-strength'))
        if total_volume >= 10000:
            badges.append(('Volume Builder',    '💪', 'badge-volume'))
        if total_workouts >= 50:
            badges.append(('Dedicated Athlete', '🔥', 'badge-dedicated'))

        # Recent activity (built from existing tables — no schema change)
        latest_plan = (
            WorkoutPlan.query
            .filter_by(user_id=profile_user.id, is_public=True)
            .order_by(WorkoutPlan.id.desc())
            .first()
        )
        if latest_plan:
            activity.append({
                'icon': '📋',
                'text': f'Shared a workout plan: {latest_plan.title}',
                'link': url_for('workout_detail', plan_id=latest_plan.id),
            })

        latest_comment = (
            WorkoutComment.query
            .filter_by(user_id=profile_user.id)
            .order_by(WorkoutComment.created_at.desc())
            .first()
        )
        if latest_comment:
            commented_plan = (
                WorkoutPlan.query
                .filter_by(id=latest_comment.workout_id, is_public=True)
                .first()
            )
            if commented_plan:
                activity.append({
                    'icon': '💬',
                    'text': f'Commented on: {commented_plan.title}',
                    'link': url_for('workout_detail', plan_id=commented_plan.id),
                })

        latest_like = (
            WorkoutLike.query
            .filter_by(user_id=profile_user.id)
            .order_by(WorkoutLike.created_at.desc())
            .first()
        )
        if latest_like:
            liked_plan = (
                WorkoutPlan.query
                .filter_by(id=latest_like.workout_id, is_public=True)
                .first()
            )
            if liked_plan:
                activity.append({
                    'icon': '❤️',
                    'text': f'Liked: {liked_plan.title}',
                    'link': url_for('workout_detail', plan_id=liked_plan.id),
                })

        latest_pr = (
            PersonalRecord.query
            .filter_by(user_id=profile_user.id)
            .order_by(PersonalRecord.date_set.desc())
            .first()
        )
        if latest_pr:
            activity.append({
                'icon': '🎯',
                'text': (f'Set a PR: {latest_pr.exercise.title()} — '
                         f'{latest_pr.best_weight:g} kg × {latest_pr.best_reps} reps'),
                'link': None,
            })

    return render_template(
        "public_profile.html",
        profile_user=profile_user,
        public_plans=public_plans,
        public_plans_count=public_plans_count,
        is_own_profile=is_own_profile,
        is_following=is_following,
        followers_count=followers_count,
        following_count=following_count,
        profile_visible=profile_visible,
        active_tab=active_tab,
        total_workouts=total_workouts,
        total_volume=total_volume,
        pr_count=pr_count,
        personal_records=personal_records,
        workouts_this_week=workouts_this_week,
        likes_map=likes_map,
        comments_map=comments_map,
        tags_map=tags_map,
        badges=badges,
        activity=activity,
    )


@app.route("/follow/<int:user_id>", methods=["POST"])
def follow_user(user_id):
    user, err = _require_login()
    if err:
        return err

    user_to_follow = User.query.get_or_404(user_id)

    if user_to_follow.id == user.id:
        flash("You cannot follow yourself.", "warning")
        return redirect(url_for("public_profile", username=user_to_follow.username))

    existing = Follow.query.filter_by(
        follower_id=user.id, followed_id=user_to_follow.id
    ).first()

    if not existing:
        db.session.add(Follow(follower_id=user.id, followed_id=user_to_follow.id))
        db.session.commit()
        flash(f"You are now following {user_to_follow.username}.", "success")

    return redirect(url_for("public_profile", username=user_to_follow.username))


@app.route("/unfollow/<int:user_id>", methods=["POST"])
def unfollow_user(user_id):
    user, err = _require_login()
    if err:
        return err

    user_to_unfollow = User.query.get_or_404(user_id)

    follow = Follow.query.filter_by(
        follower_id=user.id, followed_id=user_to_unfollow.id
    ).first()

    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash(f"You unfollowed {user_to_unfollow.username}.", "info")

    return redirect(url_for("public_profile", username=user_to_unfollow.username))


@app.route("/workout/<int:plan_id>")
def workout_detail(plan_id):
    user, err = _require_login()
    if err:
        return err

    plan = WorkoutPlan.query.get_or_404(plan_id)

    if not plan.is_public and plan.user_id != user.id:
        flash("This workout plan is private.", "danger")
        return redirect(url_for("public_feed"))

    likes_count = WorkoutLike.query.filter_by(workout_id=plan.id).count()
    user_has_liked = WorkoutLike.query.filter_by(
        workout_id=plan.id, user_id=user.id
    ).first() is not None

    comments = (
        WorkoutComment.query
        .filter_by(workout_id=plan.id)
        .order_by(WorkoutComment.created_at.desc())
        .all()
    )

    return render_template(
        "workout_detail.html",
        plan=plan,
        likes_count=likes_count,
        user_has_liked=user_has_liked,
        comments=comments,
        is_owner=(plan.user_id == user.id),
    )


@app.route("/workout/<int:plan_id>/like", methods=["POST"])
def toggle_workout_like(plan_id):
    user, err = _require_login()
    if err:
        return err

    plan = WorkoutPlan.query.get_or_404(plan_id)

    if not plan.is_public and plan.user_id != user.id:
        flash("You cannot like a private workout plan.", "danger")
        return redirect(url_for("public_feed"))

    existing_like = WorkoutLike.query.filter_by(
        workout_id=plan.id, user_id=user.id
    ).first()

    if existing_like:
        db.session.delete(existing_like)
    else:
        db.session.add(WorkoutLike(workout_id=plan.id, user_id=user.id))

    db.session.commit()
    return redirect(url_for("workout_detail", plan_id=plan.id))


@app.route("/workout/<int:plan_id>/like/json", methods=["POST"])
def toggle_workout_like_json(plan_id):
    user, err = _require_login()
    if err:
        return jsonify({"error": "not logged in"}), 401

    plan = WorkoutPlan.query.get_or_404(plan_id)

    if not plan.is_public and plan.user_id != user.id:
        return jsonify({"error": "private plan"}), 403

    existing_like = WorkoutLike.query.filter_by(
        workout_id=plan.id, user_id=user.id
    ).first()

    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        db.session.add(WorkoutLike(workout_id=plan.id, user_id=user.id))
        liked = True

    db.session.commit()
    count = WorkoutLike.query.filter_by(workout_id=plan.id).count()
    return jsonify({"liked": liked, "count": count})


@app.route("/workout/<int:plan_id>/comment", methods=["POST"])
def add_workout_comment(plan_id):
    user, err = _require_login()
    if err:
        return err

    plan = WorkoutPlan.query.get_or_404(plan_id)

    if not plan.is_public and plan.user_id != user.id:
        flash("You cannot comment on a private workout plan.", "danger")
        return redirect(url_for("public_feed"))

    body = request.form.get("body", "").strip()

    if not body:
        flash("Comment cannot be empty.", "warning")
        return redirect(url_for("workout_detail", plan_id=plan.id))

    db.session.add(WorkoutComment(body=body, user_id=user.id, workout_id=plan.id))
    db.session.commit()

    flash("Comment added.", "success")
    return redirect(url_for("workout_detail", plan_id=plan.id))


@app.route("/workout/<int:plan_id>/toggle-public", methods=["POST"])
def toggle_plan_visibility(plan_id):
    user, err = _require_login()
    if err:
        return err

    plan = WorkoutPlan.query.get_or_404(plan_id)

    if plan.user_id != user.id:
        flash("You can only change visibility of your own plans.", "warning")
        return redirect(url_for("plans"))

    plan.is_public = not plan.is_public
    db.session.commit()

    status = "public" if plan.is_public else "private"
    flash(f'"{plan.title}" is now {status}.', "success")

    next_url = request.form.get("next") or url_for("plans")
    return redirect(next_url)


@app.route("/search")
def search_page():
    _, err = _require_login()
    if err:
        return err

    query = request.args.get("q", "").strip()
    users = []
    plans = []

    if query:
        users = (
            User.query
            .filter(User.username.ilike(f"%{query}%"))
            .limit(10)
            .all()
        )
        plans = (
            WorkoutPlan.query
            .filter(
                WorkoutPlan.is_public == True,
                WorkoutPlan.title.ilike(f"%{query}%")
            )
            .limit(10)
            .all()
        )

    return render_template("search.html", query=query, users=users, plans=plans)


# ── Run app ──
if __name__ == "__main__":
    app.run(debug=True)
