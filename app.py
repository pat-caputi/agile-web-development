from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
import json
import re

# ── App setup ──
app = Flask(__name__)
app.secret_key = "your_secret_key"   # TODO(security): load from env var (rubric: env vars in config files)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ── Database models ──
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(280))                                            # added (profile)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # added (profile)


class Workout(db.Model):
    """A single workout session belonging to a user. Each session has many sets."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False, default="Workout")
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.String(280))
    user = db.relationship(
        'User',
        backref=db.backref('workouts', lazy=True, cascade='all, delete-orphan',
                           order_by='Workout.date.desc()')
    )

    @property
    def volume(self):
        """Total kg moved this session: sum of weight × reps over every set."""
        return sum((s.weight or 0) * (s.reps or 0) for s in self.sets)

    @property
    def exercise_summary(self):
        """Distinct exercises in this workout, in the order they were performed."""
        seen = []
        for s in self.sets:
            if s.exercise and s.exercise not in seen:
                seen.append(s.exercise)
        return seen


class WorkoutSet(db.Model):
    """A single set: e.g. Bench press × 8 @ 80kg."""
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    exercise = db.Column(db.String(80), nullable=False)
    weight = db.Column(db.Float, nullable=False, default=0)
    reps = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.String(80))
    workout = db.relationship(
        'Workout',
        backref=db.backref('sets', lazy=True, cascade='all, delete-orphan',
                           order_by='WorkoutSet.id')
    )


with app.app_context():
    db.create_all()


# ── Auth helpers ──
def get_current_user():
    """Returns the logged-in User object, or None if anonymous."""
    uid = session.get('user_id')
    if uid is None:
        return None
    return User.query.get(uid)


def login_required(view):
    """Send anonymous visitors to /login instead of letting them through."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if get_current_user() is None:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapper


# ── Display helpers (shared with templates as Jinja globals) ──
AVATAR_PALETTES = [
    ("#FAEEDA", "#633806"),  # amber
    ("#E1F5EE", "#085041"),  # teal
    ("#AFA9EC", "#26215C"),  # purple
    ("#FAECE7", "#712B13"),  # coral
    ("#FBEAF0", "#72243E"),  # pink
    ("#EAF3DE", "#27500A"),  # lime
    ("#EEEDFE", "#3C3489"),  # purple-light
    ("#F1EFE8", "#5F5E5A"),  # gray
]


def initials(name):
    """Two-character avatar initials. 'kawhi' -> 'KA', 'Pat Caputi' -> 'PC'."""
    if not name:
        return "?"
    parts = name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def avatar_palette(user_id):
    """Deterministic avatar colours so a user is always the same colour everywhere."""
    bg, fg = AVATAR_PALETTES[(user_id or 0) % len(AVATAR_PALETTES)]
    return {"bg": bg, "fg": fg}


# Make helpers available inside Jinja templates.
app.jinja_env.globals['initials'] = initials
app.jinja_env.globals['avatar_palette'] = avatar_palette


# ── Stats / leaderboard logic ──
METRIC_LABELS = {
    "volume": "Total volume",
    "frequency": "Frequency",
    "strength": "Strength score",
    "prs": "PRs set",
}


def _week_bounds(week_offset=0):
    """(start, end) datetimes for a Monday-Sunday week. offset=0 is the current week."""
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=week_offset)
    start = datetime.combine(monday, datetime.min.time())
    end = start + timedelta(days=7)
    return start, end


def _user_metric(user, metric, week_offset=0):
    """Return a single user's score for the requested metric in the given week."""
    start, end = _week_bounds(week_offset)
    week_workouts = [w for w in user.workouts if start <= w.date < end]

    if metric == "volume":
        return int(sum(w.volume for w in week_workouts))

    if metric == "frequency":
        return len(week_workouts)

    if metric == "strength":
        # Sum of best single-set weight across the big-three lifts this week.
        big_three = {"bench press", "squat", "deadlift"}
        bests = {}
        for w in week_workouts:
            for s in w.sets:
                ex = (s.exercise or "").strip().lower()
                if ex in big_three and (s.weight or 0) > bests.get(ex, 0):
                    bests[ex] = s.weight or 0
        return int(sum(bests.values()))

    if metric == "prs":
        # Count this-week sets that match the user's all-time max for that exercise.
        all_max = defaultdict(float)
        for w in user.workouts:
            for s in w.sets:
                if s.exercise:
                    key = s.exercise.strip().lower()
                    if (s.weight or 0) > all_max[key]:
                        all_max[key] = s.weight or 0
        prs = 0
        for w in week_workouts:
            for s in w.sets:
                key = (s.exercise or "").strip().lower()
                if key and (s.weight or 0) > 0 and (s.weight or 0) >= all_max[key]:
                    prs += 1
        return prs

    return 0


def _workout_count(user, week_offset=0):
    start, end = _week_bounds(week_offset)
    return sum(1 for w in user.workouts if start <= w.date < end)


def compute_leaderboard(metric="volume"):
    """Sorted list of {user, rank, score, workouts, change} for every user."""
    users = User.query.all()

    rows = [(u, _user_metric(u, metric, 0)) for u in users]
    # Sort by score descending; tiebreak on user id so ordering is stable.
    rows.sort(key=lambda r: (-r[1], r[0].id))
    this_rank = {u.id: i + 1 for i, (u, _) in enumerate(rows)}

    prev_rows = [(u, _user_metric(u, metric, 1)) for u in users]
    prev_rows.sort(key=lambda r: (-r[1], r[0].id))
    prev_rank = {u.id: i + 1 for i, (u, _) in enumerate(prev_rows)}

    out = []
    for rank, (u, score) in enumerate(rows, start=1):
        # Positive = moved up (better rank), negative = moved down.
        change = prev_rank.get(u.id, rank) - rank
        out.append({
            "user": u,
            "rank": rank,
            "score": score,
            "workouts": _workout_count(u, 0),
            "change": change,
        })
    return out


def metric_unit(metric):
    return {"volume": "kg", "frequency": "workouts",
            "strength": "kg", "prs": "PRs"}.get(metric, "")


# ── Profile stats ──
def personal_records(user):
    """User's all-time best weight per exercise. Returned sorted heaviest first."""
    best = {}
    for w in user.workouts:
        for s in w.sets:
            if not s.exercise:
                continue
            key = s.exercise.strip().lower()
            if (s.weight or 0) > best.get(key, (0, ""))[0]:
                best[key] = (s.weight or 0, s.exercise.strip().capitalize())
    items = [{"exercise": label, "weight": int(weight)} for weight, label in best.values()]
    items.sort(key=lambda x: -x["weight"])
    return items[:6]


def current_streak(user):
    """Consecutive days (ending today, or yesterday if today is a rest day) with a workout."""
    if not user.workouts:
        return 0
    workout_days = {w.date.date() for w in user.workouts}
    today = datetime.utcnow().date()

    cursor = today if today in workout_days else today - timedelta(days=1)
    if cursor not in workout_days:
        return 0

    streak = 0
    while cursor in workout_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ── Routes ──
@app.route('/')
def home():
    return redirect('/login')


@app.route('/ranks')
def ranks():
    return render_template('ranks.html')


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

        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return render_template('register.html', username=username, email=email)
        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return render_template('register.html', username=username, email=email)

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
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
                func.lower(User.email) == login_input,
            )
        ).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect('/dashboard')
        flash("Invalid username/email or password")
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    today = datetime.utcnow()

    # Weekly stats from the database (replaces hardcoded mockup numbers).
    workouts_count = _workout_count(user, week_offset=0)
    weekly_volume = _user_metric(user, 'volume', week_offset=0)

    # Where do I sit on the volume leaderboard right now?
    lb = compute_leaderboard('volume')
    my_row = next((r for r in lb if r["user"].id == user.id), None)
    rank = my_row["rank"] if my_row else None

    return render_template(
        'dashboard.html',
        user=user,
        today=today,
        workouts_count=workouts_count,
        weekly_volume=weekly_volume,
        streak=current_streak(user),
        rank=rank,
        total_users=len(lb),
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/log_workout', methods=['GET', 'POST'])
@login_required
def log_workout():
    user = get_current_user()

    if request.method == 'POST':
        # Frontend (templates/log_workout.html) submits a hidden field
        # 'workout_data' containing a JSON list of completed sets:
        #   [{"exercise": "Bench press", "weight": 80, "reps": 8}, ...]
        try:
            sets = json.loads(request.form.get('workout_data', '[]'))
        except (ValueError, TypeError):
            sets = []

        if not sets:
            flash("No sets to save — add at least one completed set first.")
            return redirect(url_for('log_workout'))

        # Create the parent Workout session and attach all the sets.
        workout = Workout(user_id=user.id, name="Workout")
        db.session.add(workout)
        db.session.flush()  # populates workout.id before we use it

        for item in sets:
            try:
                ws = WorkoutSet(
                    workout_id=workout.id,
                    exercise=str(item.get('exercise', '')).strip()[:80] or 'Exercise',
                    weight=float(item.get('weight') or 0),
                    reps=int(item.get('reps') or 0),
                )
                db.session.add(ws)
            except (ValueError, TypeError):
                # Skip malformed rows rather than crashing the whole save.
                continue

        db.session.commit()
        flash("Workout saved successfully!")
        return redirect(url_for('dashboard'))

    return render_template('log_workout.html', today=datetime.utcnow())


@app.route('/plans')
def plans():
    return render_template('plans.html')


# ── Leaderboard & Profile (this PR) ──
@app.route('/leaderboard')
@login_required
def leaderboard():
    metric = request.args.get('metric', 'volume')
    if metric not in METRIC_LABELS:
        metric = 'volume'
    rows = compute_leaderboard(metric)
    return render_template(
        'leaderboard.html',
        rows=rows,
        metric=metric,
        metric_label=METRIC_LABELS[metric],
        metric_unit=metric_unit(metric),
        me=get_current_user(),
    )


@app.route('/api/leaderboard')
@login_required
def api_leaderboard():
    """JSON endpoint that powers the leaderboard's pill-tab AJAX switching."""
    metric = request.args.get('metric', 'volume')
    if metric not in METRIC_LABELS:
        metric = 'volume'
    rows = compute_leaderboard(metric)
    me = get_current_user()
    return jsonify({
        "metric": metric,
        "label": METRIC_LABELS[metric],
        "unit": metric_unit(metric),
        "rows": [
            {
                "rank": r["rank"],
                "user_id": r["user"].id,
                "username": r["user"].username,
                "initials": initials(r["user"].username),
                "palette": avatar_palette(r["user"].id),
                "workouts": r["workouts"],
                "score": r["score"],
                "change": r["change"],
                "is_me": me is not None and me.id == r["user"].id,
            } for r in rows
        ],
    })


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()

    if request.method == 'POST':
        bio = (request.form.get('bio') or '').strip()
        user.bio = bio[:280]   # enforce model length cap
        db.session.commit()
        flash("Profile updated")
        return redirect(url_for('profile'))

    all_workouts = sorted(user.workouts, key=lambda w: w.date, reverse=True)

    # Where do I sit on the volume leaderboard?
    lb = compute_leaderboard('volume')
    my_row = next((r for r in lb if r["user"].id == user.id), None)

    return render_template(
        'profile.html',
        user=user,
        total_workouts=len(all_workouts),
        recent_workouts=all_workouts[:8],
        rank=my_row["rank"] if my_row else None,
        total_users=len(lb),
        streak=current_streak(user),
        records=personal_records(user),
    )


# ── Run app ──
if __name__ == "__main__":
    app.run(debug=True)
