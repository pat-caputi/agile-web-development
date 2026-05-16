"""
Selenium UI tests for LiftAGILE.

Requirements:
    pip install selenium webdriver-manager

Run with: python -m pytest tests/test_selenium.py -v
"""

import os
import socket
import sys
import threading
import time
import uuid

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app as app_module

flask_app = app_module.app
db = app_module.db
User = app_module.User

TEST_PORT = 5099
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"
WAIT = 10  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unique_name(prefix="sel"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _make_user(username=None, password="Password1", email=None):
    username = username or unique_name()
    email = email or f"{username}@example.com"
    with flask_app.app_context():
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "username": username, "email": email, "password": password}


def _cleanup_user(username):
    from tests.test_app import cleanup_user
    cleanup_user(username)


def _login(driver, username, password):
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    driver.find_element(By.ID, "username").clear()
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").clear()
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()


# ---------------------------------------------------------------------------
# Session-scoped live server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def live_server():
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )

    # RATELIMIT_ENABLED=False can be ignored if Flask-Limiter cached its state
    # at init time. The request_filter API is the guaranteed way to exempt every
    # request from every limit — including the @limiter.limit("5 per minute")
    # decorator on /login, which covers both GET and POST. Without this, a full
    # test run exhausts the limit and all subsequent /login requests get 429.
    @app_module.limiter.request_filter
    def _exempt_all_test_requests():
        return True

    server_thread = threading.Thread(
        target=lambda: flask_app.run(
            host="127.0.0.1",
            port=TEST_PORT,
            use_reloader=False,
            debug=False,
        ),
        daemon=True,
    )
    server_thread.start()

    for _ in range(30):
        try:
            s = socket.create_connection(("127.0.0.1", TEST_PORT), timeout=1)
            s.close()
            break
        except OSError:
            time.sleep(0.2)

    yield BASE_URL


# ---------------------------------------------------------------------------
# Per-test browser + user fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def driver():
    opts = ChromeOptions()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    d = webdriver.Chrome(options=opts)
    yield d
    d.quit()


@pytest.fixture()
def test_user():
    user = _make_user()
    yield user
    _cleanup_user(user["username"])


@pytest.fixture()
def second_user():
    user = _make_user(username=unique_name("second"))
    yield user
    _cleanup_user(user["username"])


# ---------------------------------------------------------------------------
# 1. Login page loads
# ---------------------------------------------------------------------------

def test_login_page_loads(driver):
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Sign in"))
    assert "Sign in · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 2. Login page has username and password fields
# ---------------------------------------------------------------------------

def test_login_page_has_required_fields(driver):
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    assert driver.find_element(By.ID, "username").is_displayed()
    assert driver.find_element(By.ID, "password").is_displayed()


# ---------------------------------------------------------------------------
# 3. Login page has a link to the register page
# ---------------------------------------------------------------------------

def test_login_page_has_register_link(driver):
    driver.get(f"{BASE_URL}/login")
    link = WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.LINK_TEXT, "Create one"))
    )
    assert "/register" in link.get_attribute("href")


# ---------------------------------------------------------------------------
# 4. Register page loads
# ---------------------------------------------------------------------------

def test_register_page_loads(driver):
    driver.get(f"{BASE_URL}/register")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Create account"))
    assert "Create account · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 5. Register page has all required form fields
# ---------------------------------------------------------------------------

def test_register_page_has_all_fields(driver):
    driver.get(f"{BASE_URL}/register")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    for field_id in ("username", "email", "password", "confirm"):
        assert driver.find_element(By.ID, field_id).is_displayed(), f"Missing field: {field_id}"


# ---------------------------------------------------------------------------
# 6. Register page has a link back to the login page
# ---------------------------------------------------------------------------

def test_register_page_has_login_link(driver):
    driver.get(f"{BASE_URL}/register")
    link = WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.LINK_TEXT, "Sign in"))
    )
    assert "/login" in link.get_attribute("href")


# ---------------------------------------------------------------------------
# 7. Successful login lands on dashboard
# ---------------------------------------------------------------------------

def test_successful_login_redirects_to_dashboard(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    assert "Dashboard · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 8. Wrong password keeps user on login with an error
# ---------------------------------------------------------------------------

def test_wrong_password_shows_error(driver, test_user):
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    old_field = driver.find_element(By.ID, "username")
    old_field.send_keys(test_user["username"])
    driver.find_element(By.ID, "password").send_keys("WrongPassword9")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, WAIT).until(EC.staleness_of(old_field))
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".error-msg")))
    assert "Sign in · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 9. Non-existent username keeps user on login with an error
# ---------------------------------------------------------------------------

def test_nonexistent_user_login_shows_error(driver):
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    old_field = driver.find_element(By.ID, "username")
    old_field.send_keys("ghost_user_xyz_9999")
    driver.find_element(By.ID, "password").send_keys("Password1")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, WAIT).until(EC.staleness_of(old_field))
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".error-msg")))
    assert "Sign in · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 10. Successful registration redirects to the login page
# ---------------------------------------------------------------------------

def test_successful_registration_redirects_to_login(driver):
    username = unique_name("newreg")
    try:
        driver.get(f"{BASE_URL}/register")
        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
        driver.find_element(By.ID, "username").send_keys(username)
        driver.find_element(By.ID, "email").send_keys(f"{username}@example.com")
        driver.find_element(By.ID, "password").send_keys("Password1")
        driver.find_element(By.ID, "confirm").send_keys("Password1")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        WebDriverWait(driver, WAIT).until(EC.title_contains("Sign in"))
        assert "Sign in · LiftAGILE" == driver.title
    finally:
        _cleanup_user(username)


# ---------------------------------------------------------------------------
# 11. Mismatched passwords on registration shows an error
# ---------------------------------------------------------------------------

def test_register_mismatched_passwords_shows_error(driver):
    username = unique_name("mismatch")
    driver.get(f"{BASE_URL}/register")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "email").send_keys(f"{username}@example.com")
    driver.find_element(By.ID, "password").send_keys("Password1")
    driver.find_element(By.ID, "confirm").send_keys("Different2")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".error-msg")))
    assert "Create account · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 12. Duplicate username on registration shows an error
# ---------------------------------------------------------------------------

def test_register_duplicate_username_shows_error(driver, test_user):
    driver.get(f"{BASE_URL}/register")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    driver.find_element(By.ID, "username").send_keys(test_user["username"])
    driver.find_element(By.ID, "email").send_keys(f"other_{uuid.uuid4().hex[:6]}@example.com")
    driver.find_element(By.ID, "password").send_keys("Password1")
    driver.find_element(By.ID, "confirm").send_keys("Password1")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".error-msg")))
    assert "Create account · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 13. Weak password (no uppercase) on registration shows an error
# ---------------------------------------------------------------------------

def test_register_weak_password_shows_error(driver):
    username = unique_name("weakpw")
    driver.get(f"{BASE_URL}/register")
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.ID, "username")))
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "email").send_keys(f"{username}@example.com")
    driver.find_element(By.ID, "password").send_keys("alllowercase1")
    driver.find_element(By.ID, "confirm").send_keys("alllowercase1")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".error-msg")))
    assert "Create account · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 14. Unauthenticated access to /dashboard redirects to login
# ---------------------------------------------------------------------------

def test_unauthenticated_user_redirected_from_dashboard(driver):
    driver.get(f"{BASE_URL}/dashboard")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Sign in"))
    assert "Sign in · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 15. Dashboard page loads after login
# ---------------------------------------------------------------------------

def test_dashboard_loads_after_login(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    assert "Dashboard · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 16. Plans page loads after login
# ---------------------------------------------------------------------------

def test_plans_page_loads_after_login(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    driver.get(f"{BASE_URL}/plans")
    WebDriverWait(driver, WAIT).until(EC.title_contains("My plans"))
    assert "My plans · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 17. Log Workout page loads after login
# ---------------------------------------------------------------------------

def test_log_workout_page_loads_after_login(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    driver.get(f"{BASE_URL}/log_workout")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Log workout"))
    assert "Log workout · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 18. Profile page loads after login
# ---------------------------------------------------------------------------

def test_profile_page_loads_after_login(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    driver.get(f"{BASE_URL}/profile")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Profile"))
    assert "Profile · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 19. Leaderboard page loads after login
# ---------------------------------------------------------------------------

def test_leaderboard_page_loads_after_login(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    driver.get(f"{BASE_URL}/leaderboard")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Leaderboard"))
    assert "Leaderboard · LiftAGILE" == driver.title


# ---------------------------------------------------------------------------
# 20. Logout sends user back to the login page
# ---------------------------------------------------------------------------

def test_logout_redirects_to_login(driver, test_user):
    _login(driver, test_user["username"], test_user["password"])
    WebDriverWait(driver, WAIT).until(EC.title_contains("Dashboard"))
    driver.get(f"{BASE_URL}/logout")
    WebDriverWait(driver, WAIT).until(EC.title_contains("Sign in"))
    assert "Sign in · LiftAGILE" == driver.title
