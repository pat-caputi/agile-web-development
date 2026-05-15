# LiftAGILE 

LiftAGILE is a fitness-focused social web application designed to help users plan, track, and stay motivated throughout their fitness journey. The platform combines workout logging, workout scheduling, personal progress tracking, and social interaction into one modern web application.

The purpose of LiftAGILE is to provide users with an all-in-one digital gym companion that not only helps them manage their workouts, but also encourages consistency and engagement through community-driven features such as public workout plans, likes, follows, rankings, leaderboards, and activity feeds.

Unlike traditional workout trackers, LiftAGILE integrates both productivity and social motivation into a single platform, allowing users to stay accountable while interacting with other fitness enthusiasts.

---

# Team Members

| STUDENT ID | Name | GitHub Username |
|--------|------|----------------|
| 23738739 | Aung Phone Hein | Aung-Phone-Hein |
| 24161516 | Donglin Chen | ChenFan-excellent |
| 24272065 | Patrick Caputi | Pat-Caputi |
| 23213251 | Wayne Mataruse | waynecancode |


# Features

## Authentication & Security

LiftAGILE includes multiple security-focused backend protections:

- User registration and login system
- Secure password hashing using Werkzeug
- CSRF protection using Flask-WTF
- Rate limiting for login attempts using Flask-Limiter
- Secure session cookie configuration
- Protected routes requiring authentication
- Authorization checks to prevent users accessing or modifying unauthorised resources
- File upload restrictions for profile images

These protections help improve application security and protect against common web vulnerabilities such as brute-force attacks, CSRF attacks, and unauthorised access.

---

## Workout Logging

Users can track their gym sessions in real time using the workout logging interface.

Features include:

- Logging exercises
- Recording:
  - sets
  - repetitions
  - weights
  - workout notes
- Live workout timer
- Set completion progress tracking
- Dynamic exercise addition/removal
- Automatic personal record (PR) detection
- Workout history storage

The workout logger allows users to track progress efficiently while maintaining a smooth and interactive experience.

---

## Workout Plans

Users can create and manage reusable workout routines.

Features include:

- Create custom workout plans
- Edit workout plans
- Delete workout plans
- Public/private visibility controls
- Drag-and-drop exercise reordering
- Start workout plans directly from the plans page
- Exercise categorisation by muscle group
- Quick loading of plans into workout logging

This feature improves usability by allowing users to reuse and customise structured workout routines.

---

## Calendar Scheduling

LiftAGILE includes a workout calendar for scheduling future sessions.

Features include:

- Schedule workouts on selected dates
- View upcoming scheduled workouts
- Weekly workout overview
- Start scheduled workouts directly from calendar entries
- Schedule rest days
- Automatically load the correct workout plan when starting scheduled sessions

This helps users plan their weekly training schedule and stay consistent.

---

## Social Features

LiftAGILE includes social networking functionality to encourage accountability and engagement.

Features include:

- Public user profiles
- Follow/unfollow users
- Like/unlike public workout plans
- Social activity feed
- Search users
- Community plan sharing
- Public workout plan browsing

These features make the application feel more interactive and community-driven rather than being a standalone tracker.

---

## Progress Tracking

Users can monitor performance improvements over time.

Features include:

- Weekly workout statistics
- Training volume tracking
- Personal records
- Ranking system
- Leaderboard comparisons
- Profile workout summaries

This allows users to visualise consistency and competitive progress.

---

# Application Design

LiftAGILE was designed with a modern dark-themed interface inspired by contemporary fitness applications.

The design prioritises:

- simplicity
- usability
- responsiveness
- smooth interaction
- social motivation

The interface was intentionally styled to resemble premium fitness applications, using interactive animations, clear visual hierarchy, and gym-themed aesthetics.

---

## Design Principles

The application was built around the following design principles:

- Clean fitness-inspired visual design
- Responsive layout for multiple screen sizes
- Interactive animations and transitions
- Fast access to core features
- Clear user feedback for actions
- Social motivation through community engagement
- Minimal friction for workout tracking

---

# Technologies Used

## Backend

- Python
- Flask
- Flask-SQLAlchemy
- Flask-WTF
- Flask-Limiter
- Werkzeug
- python-dotenv

Backend responsibilities include:

- authentication
- session management
- routing
- business logic
- validation
- database interactions
- security enforcement

---

## Frontend

- HTML5
- CSS3
- JavaScript
- Jinja2 templating
- Font Awesome

Frontend responsibilities include:

- dynamic UI interactions
- animations
- drag-and-drop functionality
- form validation
- responsive layouts
- asynchronous requests (fetch API)

---

## Database

- SQLite

Database stores:

- users
- workout plans
- workout logs
- personal records
- calendar schedules
- likes
- follows
- profile information

---

# How to Launch the Application

## 1. Clone the repository

```bash
git clone https://github.com/Pat-Caputi/Agile-Web-Development.git
cd Agile-Web-Development
```

---

## 2. Create a virtual environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Mac/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

If required:

```bash
pip install flask flask-sqlalchemy flask-wtf flask-limiter python-dotenv werkzeug pytest
```

---

## 4. Configure environment variables (optional)

For improved security, you may create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
```

If no `.env` file is provided, the application will use the default development secret key.
```

---

## 5. Initialise database

If database seeding is required:

```bash
python seed_data.py
```

Otherwise:

```bash
python app.py
```

---

## 6. Run application

```bash
python app.py
```

---

## 7. Open in browser

```text
http://127.0.0.1:5000
```

---

# Running Tests

LiftAGILE includes automated backend testing using pytest.

To run tests:

```bash
python -m pytest
```

Expected output:

```bash
23 passed
```

---

## Test Coverage

Automated tests currently cover:

### Authentication
- successful login
- invalid login
- duplicate registration
- weak password rejection
- protected route access

### Workout Features
- workout logging
- personal record creation
- workout plan creation
- workout plan editing
- workout plan deletion

### Calendar Features
- workout scheduling
- calendar entry validation
- scheduled workout loading

### Social Features
- follow/unfollow users
- like/unlike workout plans
- privacy restrictions for private plans

### Security
- CSRF enforcement
- access control
- route protection
- authorization validation

These tests improve reliability and demonstrate software engineering best practices.

---

# Security Features

Implemented security measures include:

- password hashing
- CSRF protection
- rate-limited login attempts
- secure session cookie settings
- access control validation
- private resource protection
- upload restrictions
- route authorization checks

These measures help mitigate:

- brute-force attacks
- CSRF attacks
- session abuse
- unauthorised access
- malicious uploads

---

# Project Structure

```text
Agile-Web-Development/
│
├── app.py
├── requirements.txt
├── README.md
├── .env
│
├── static/
│   ├── css/
│   ├── js/
│   ├── uploads/
│
├── templates/
│
├── tests/
│   └── test_app.py
│
└── instance/
```

---

# Future Improvements

Potential future enhancements:

- password reset
- email verification
- push notifications
- cloud database deployment
- direct messaging
- mobile-first optimisation
- exercise video integration
- AI workout recommendations

