from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, or_
from datetime import datetime, timedelta
import re
import json

# ── App setup ──
app = Flask(__name__)
app.secret_key = "your_secret_key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ── Database models ──
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


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
    today = datetime.utcnow()
    start_of_week = today - timedelta(days=today.weekday())
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)


def get_current_user():
    if 'user_id' not in session:
        return None
    return db.session.get(User, session['user_id'])


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

def get_current_streak(user_id):
    workouts = (
        Workout.query
        .filter_by(user_id=user_id)
        .order_by(Workout.date.desc())
        .all()
    )

    if not workouts:
        return 0

    workout_days = {
        workout.date.date()
        for workout in workouts
    }

    streak = 0
    current_day = datetime.utcnow().date()

    while current_day in workout_days:
        streak += 1
        current_day -= timedelta(days=1)

    return streak


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

    today = datetime.utcnow()
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

    daily_rows = (
        db.session.query(
            func.strftime('%w', Workout.date).label('day'),
            func.sum(WorkoutSet.weight * WorkoutSet.reps).label('volume')
        )
        .join(Workout, WorkoutSet.workout_id == Workout.id)
        .filter(
            Workout.user_id == session['user_id'],
            Workout.date >= start_of_week
        )
        .group_by(func.strftime('%w', Workout.date))
        .all()
    )

    daily_volumes = [0, 0, 0, 0, 0, 0, 0]

    for row in daily_rows:
        sqlite_day = int(row.day)
        python_day = (sqlite_day - 1) % 7
        daily_volumes[python_day] = row.volume or 0

    max_volume = max(daily_volumes) if max(daily_volumes) > 0 else 1

    weekly_chart_data = [
        {
            "day": day,
            "volume": int(daily_volumes[index]),
            "height": 0 if daily_volumes[index] == 0 else max(8, int((daily_volumes[index] / max_volume) * 100))
        }
        for index, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ]

    return render_template(
        'dashboard.html',
        user=user,
        today=today,
        weekly_volume=weekly_volume,
        workouts_count=workouts_count,
        streak=get_current_streak(session['user_id']),
        rank=rank,
        total_users=total_users,
        weekly_chart_data=weekly_chart_data
    )


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# LOG WORKOUT
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

    today = datetime.utcnow()

    return render_template(
        'log_workout.html',
        today=today,
        user=user,
        rank=get_user_rank(session['user_id'])
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
            func.count(func.distinct(Workout.id)).label('workouts_count'),
            func.sum(WorkoutSet.weight * WorkoutSet.reps).label('weekly_volume')
        )
        .join(Workout, Workout.user_id == User.id)
        .join(WorkoutSet, WorkoutSet.workout_id == Workout.id)
        .filter(Workout.date >= start_of_week)
        .group_by(User.id, User.username)
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

    return render_template(
        'leaderboard.html',
        leaderboard_data=leaderboard_data,
        tier_map=tier_map,
        current_user_id=session['user_id'],
        user=user,
        rank=get_user_rank(session['user_id'])
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

    return render_template(
        'plans.html',
        user=user,
        rank=get_user_rank(session['user_id'])
    )

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
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

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
        'css': MUSCLE_CONFIG.get(EXERCISE_MUSCLE_MAP.get(p.exercise.lower().strip()), {}).get('icon_bg', '#f0f0f0'),
        'css_color': MUSCLE_CONFIG.get(EXERCISE_MUSCLE_MAP.get(p.exercise.lower().strip()), {}).get('icon_color', '#333'),
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


# ── Run app ──
if __name__ == "__main__":
    app.run(debug=True)
