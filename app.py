from flask import Flask, render_template, request, redirect, session, flash
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

# ── Database model ──
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

# ── Create DB ──
with app.app_context():
    db.create_all()

def get_user_rank(user_id):
    today = datetime.utcnow()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

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

# ── Routes ──
@app.route('/')
def home():
    return redirect('/login')
@app.route('/ranks')
def ranks():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')

    today = datetime.utcnow()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    rank = get_user_rank(session['user_id'])

    return render_template(
        'ranks.html',
        user=user,
        rank=rank
    )

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

    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    # All sessions this week
    workouts_count = (
        db.session.query(func.count(func.distinct(Workout.id)))
        .join(WorkoutSet, WorkoutSet.workout_id == Workout.id)
        .filter(
            Workout.user_id == session['user_id'],
            Workout.date >= start_of_week
        )
        .scalar()
    )

    # All sets this week (via join)
    weekly_sets = db.session.query(WorkoutSet).join(Workout).filter(
        Workout.user_id == session['user_id'],
        Workout.date >= start_of_week
    ).all()

    weekly_volume = sum(ws.weight * ws.reps for ws in weekly_sets)
    
    rank = get_user_rank(session['user_id'])

    return render_template(
        'dashboard.html',
        user=user,
        today=today,
        weekly_volume=weekly_volume,
        workouts_count=workouts_count,
        streak=12,
        rank=rank
    )


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/log_workout', methods=['GET', 'POST'])
def log_workout():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        raw = request.form.get('workout_data', '[]')
        sets = json.loads(raw)

        # First, create a training session.
        workout = Workout(user_id=session['user_id'])
        db.session.add(workout)
        db.session.flush()  # 拿到 workout.id

        # Save all sets again
        for item in sets:
            ws = WorkoutSet(
                workout_id=workout.id,
                exercise=item['exercise'],
                weight=float(item['weight']),
                reps=int(item['reps'])
            )
            db.session.add(ws)

        db.session.commit()
        flash("Workout saved successfully!")
        return redirect('/dashboard')

    today = datetime.utcnow()
    user = db.session.get(User, session['user_id'])

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

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    user = db.session.get(User, session['user_id'])

    if user is None:
        session.clear()
        return redirect('/login')
    today = datetime.utcnow()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

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

    return render_template(
        'leaderboard.html',
        leaderboard_data=leaderboard_data,
        current_user_id=session['user_id'],
        user=user,
        rank=get_user_rank(session['user_id'])
    )

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


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)

# ── Run app ──
if __name__ == "__main__":
    app.run(debug=True)