from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import csv
import io
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'My_secret_key_is_secret'  # Change this in production!

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Exercise data based on muscle groups
EXERCISES = {
    'Chest': ['Bench Press', 'Incline Bench Press', 'Decline Bench Press', 'Dumbbell Flyes', 'Push-ups', 'Cable Crossover'],
    'Back': ['Deadlift', 'Pull-ups', 'Barbell Row', 'Lat Pulldown', 'T-Bar Row', 'Cable Row'],
    'Shoulders': ['Overhead Press', 'Lateral Raises', 'Front Raises', 'Rear Delt Flyes', 'Shrugs', 'Arnold Press'],
    'Arms': ['Bicep Curls', 'Tricep Dips', 'Hammer Curls', 'Tricep Extensions', 'Preacher Curls', 'Close Grip Bench Press'],
    'Legs': ['Squats', 'Leg Press', 'Lunges', 'Leg Curls', 'Leg Extensions', 'Calf Raises'],
    'Core': ['Plank', 'Crunches', 'Russian Twists', 'Leg Raises', 'Mountain Climbers', 'Bicycle Crunches']
}

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    """Load user from database for Flask-Login"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id, username, email, is_admin FROM users WHERE id = ?', (user_id,))
        user_data = c.fetchone()
        if user_data:
            return User(user_data[0], user_data[1], user_data[2], bool(user_data[3]))
        return None
    finally:
        conn.close()

def get_db_connection():
    """Get a database connection with proper timeout and settings"""
    conn = sqlite3.connect('workouts.db', timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')  # Enable Write-Ahead Logging for better concurrency
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    """Initialize the database with the required schema"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Check if workouts table exists and has old schema
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workouts'")
        table_exists = c.fetchone()
        
        if table_exists:
            # Check if old schema exists (has sets, reps, weight_kg columns)
            c.execute("PRAGMA table_info(workouts)")
            columns = [row[1] for row in c.fetchall()]
            
            if 'sets' in columns or 'reps' in columns or 'weight_kg' in columns:
                # Old schema detected - migrate to new schema
                # Create new workouts table with correct schema
                c.execute('''
                    CREATE TABLE IF NOT EXISTS workouts_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        muscle_group TEXT NOT NULL,
                        exercise TEXT NOT NULL
                    )
                ''')
                
                # Migrate existing data (only basic info, sets will be lost)
                c.execute('''
                    INSERT INTO workouts_new (id, date, time, muscle_group, exercise)
                    SELECT id, date, time, muscle_group, exercise
                    FROM workouts
                ''')
                
                # Drop old table and rename new one
                c.execute('DROP TABLE workouts')
                c.execute('ALTER TABLE workouts_new RENAME TO workouts')
        
        # Workouts table - stores basic workout info
        c.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                muscle_group TEXT NOT NULL,
                exercise TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Add user_id column to workouts if it doesn't exist
        c.execute("PRAGMA table_info(workouts)")
        columns = [row[1] for row in c.fetchall()]
        if 'user_id' not in columns:
            try:
                c.execute('ALTER TABLE workouts ADD COLUMN user_id INTEGER')
            except sqlite3.OperationalError:
                pass  # Column might already exist
        
        # Sessions table - tracks gym sessions
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_minutes REAL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Add user_id column to sessions if it doesn't exist
        c.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in c.fetchall()]
        if 'user_id' not in columns:
            try:
                c.execute('ALTER TABLE sessions ADD COLUMN user_id INTEGER')
            except sqlite3.OperationalError:
                pass  # Column might already exist
        
        # Add session_id to workouts table if it doesn't exist
        c.execute("PRAGMA table_info(workouts)")
        columns = [row[1] for row in c.fetchall()]
        if 'session_id' not in columns:
            try:
                c.execute('ALTER TABLE workouts ADD COLUMN session_id INTEGER')
            except sqlite3.OperationalError:
                pass  # Column might already exist
        
        # Workout sets table - stores individual sets with reps and weight
        c.execute('''
            CREATE TABLE IF NOT EXISTS workout_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                weight_kg REAL NOT NULL,
                FOREIGN KEY (workout_id) REFERENCES workouts (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
    finally:
        conn.close()

# Migration function to assign existing workouts to admin user
def migrate_existing_data_to_admin():
    """Assign all existing workouts and sessions to the admin user"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Find admin user
        c.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        admin_user = c.fetchone()
        
        if admin_user:
            admin_id = admin_user[0]
            
            # Update workouts without user_id
            c.execute('UPDATE workouts SET user_id = ? WHERE user_id IS NULL', (admin_id,))
            
            # Update sessions without user_id
            c.execute('UPDATE sessions SET user_id = ? WHERE user_id IS NULL', (admin_id,))
            
            conn.commit()
        # If admin doesn't exist, that's okay - migration will happen when admin is created
    except Exception as e:
        # Silently fail if migration can't run - admin might not exist yet
        pass
    finally:
        conn.close()

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if username or email already exists
            c.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
            existing_user = c.fetchone()
            
            if existing_user:
                flash('Username or email already exists.', 'error')
                return render_template('register.html')
            
            # Create new user
            password_hash = generate_password_hash(password)
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            c.execute('''
                INSERT INTO users (username, email, password_hash, is_admin, created_at)
                VALUES (?, ?, ?, 0, ?)
            ''', (username, email, password_hash, created_at))
            
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
            return render_template('register.html')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('SELECT id, username, email, password_hash, is_admin FROM users WHERE username = ?', (username,))
            user_data = c.fetchone()
            
            if user_data and check_password_hash(user_data[3], password):
                user = User(user_data[0], user_data[1], user_data[2], bool(user_data[4]))
                login_user(user)
                next_page = request.args.get('next')
                flash(f'Welcome back, {username}!', 'success')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Invalid username or password.', 'error')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Main Application Routes
@app.route('/')
@login_required
def index():
    """Main page displaying the form and last session"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Check if there's an active session for current user
        c.execute('''
            SELECT id, date, start_time
            FROM sessions
            WHERE user_id = ? AND end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''', (current_user.id,))
        active_session_row = c.fetchone()
        active_session = None
        if active_session_row:
            active_session = {
                'id': active_session_row['id'],
                'date': active_session_row['date'],
                'start_time': active_session_row['start_time']
            }
        
        # Get last completed session for current user
        c.execute('''
            SELECT id, date, start_time, end_time, duration_minutes
            FROM sessions
            WHERE user_id = ? AND end_time IS NOT NULL
            ORDER BY date DESC, end_time DESC
            LIMIT 1
        ''', (current_user.id,))
        last_session_row = c.fetchone()
        
        session_data = None
        session_workouts = []
        
        if last_session_row:
            session_id = last_session_row['id']
            # Get all workouts for this session (only current user's workouts)
            c.execute('''
                SELECT id, date, time, muscle_group, exercise
                FROM workouts
                WHERE session_id = ? AND user_id = ?
                ORDER BY time
            ''', (session_id, current_user.id))
            workouts = c.fetchall()
            
            # Get sets for each workout
            for workout in workouts:
                workout_id = workout['id']
                c.execute('''
                    SELECT set_number, reps, weight_kg
                    FROM workout_sets
                    WHERE workout_id = ?
                    ORDER BY set_number
                ''', (workout_id,))
                sets = c.fetchall()
                session_workouts.append({
                    'id': workout['id'],
                    'date': workout['date'],
                    'time': workout['time'],
                    'muscle_group': workout['muscle_group'],
                    'exercise': workout['exercise'],
                    'sets': [(s['set_number'], s['reps'], s['weight_kg']) for s in sets]
                })
            
            session_data = {
                'id': last_session_row['id'],
                'date': last_session_row['date'],
                'start_time': last_session_row['start_time'],
                'end_time': last_session_row['end_time'],
                'duration_minutes': last_session_row['duration_minutes']
            }
        
        # Check for error messages
        error = request.args.get('error')
        if error and active_session:
            # Clear stale error messages when a session is now active
            return redirect(url_for('index'))

        error_message = None
        if error == 'no_session':
            error_message = 'Please start a gym session before logging workouts.'
        
        return render_template('index.html', 
                             active_session=active_session,
                             last_session=session_data, 
                             session_workouts=session_workouts,
                             exercises=EXERCISES,
                             error_message=error_message)
    finally:
        conn.close()

@app.route('/start_session', methods=['POST'])
@login_required
def start_session():
    """Start a new gym session"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Check if there's already an active session for current user
        c.execute('''
            SELECT id FROM sessions
            WHERE user_id = ? AND end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''', (current_user.id,))
        active_session = c.fetchone()
        
        if active_session:
            # Session already active, just redirect
            flash('Session already active.', 'info')
            return redirect(url_for('index'))
        
        # Get current date and time
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        start_time = now.strftime('%H:%M:%S')
        
        # Create new session with user_id
        c.execute('''
            INSERT INTO sessions (user_id, date, start_time)
            VALUES (?, ?, ?)
        ''', (current_user.id, date, start_time))
        
        conn.commit()
        flash('Session started!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        conn.rollback()
        flash('Error starting session.', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/end_session', methods=['POST'])
@login_required
def end_session():
    """End the current gym session and calculate duration"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get active session for current user
        c.execute('''
            SELECT id, date, start_time
            FROM sessions
            WHERE user_id = ? AND end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''', (current_user.id,))
        active_session = c.fetchone()
        
        if not active_session:
            return redirect(url_for('index'))
        
        session_id = active_session['id']
        session_date = active_session['date']
        start_time_str = active_session['start_time']
        
        # Get current time
        now = datetime.now()
        end_date = now.strftime('%Y-%m-%d')
        end_time = now.strftime('%H:%M:%S')
        
        # Calculate duration
        start_datetime = datetime.strptime(f"{session_date} {start_time_str}", "%Y-%m-%d %H:%M:%S")
        end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M:%S")
        
        # Calculate duration in minutes
        duration = (end_datetime - start_datetime).total_seconds() / 60
        
        # Update session with end time and duration
        c.execute('''
            UPDATE sessions
            SET end_time = ?, duration_minutes = ?
            WHERE id = ? AND user_id = ?
        ''', (end_time, duration, session_id, current_user.id))
        
        conn.commit()
        flash('Session ended!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        conn.rollback()
        flash('Error ending session.', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    """Handle form submission and save workout to database"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get active session for current user - REQUIRED for workout submission
        c.execute('''
            SELECT id FROM sessions
            WHERE user_id = ? AND end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''', (current_user.id,))
        active_session = c.fetchone()
        
        if not active_session:
            # No active session - redirect back with error message
            return redirect(url_for('index', error='no_session'))
        
        session_id = active_session['id']
        
        # Get current date and time
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        time = now.strftime('%H:%M:%S')
        
        # Get form data
        muscle_group = request.form.get('muscle_group')
        exercise = request.form.get('exercise')
        
        # Insert workout into database with session_id and user_id
        c.execute('''
            INSERT INTO workouts (user_id, date, time, muscle_group, exercise, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (current_user.id, date, time, muscle_group, exercise, session_id))
        
        workout_id = c.lastrowid
        
        # Get all sets from form (they come as set_1_reps, set_1_weight, set_2_reps, etc.)
        set_number = 1
        while True:
            reps_key = f'set_{set_number}_reps'
            weight_key = f'set_{set_number}_weight'
            
            if reps_key not in request.form or weight_key not in request.form:
                break
            
            reps = int(request.form.get(reps_key, 0))
            weight_kg = float(request.form.get(weight_key, 0))
            
            if reps > 0:  # Only insert if reps > 0
                c.execute('''
                    INSERT INTO workout_sets (workout_id, set_number, reps, weight_kg)
                    VALUES (?, ?, ?, ?)
                ''', (workout_id, set_number, reps, weight_kg))
            
            set_number += 1
        
        conn.commit()
        flash('Workout logged successfully!', 'success')
        return redirect(url_for('index', submitted='1'))
    except Exception as e:
        conn.rollback()
        flash('Error logging workout.', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/exercises/<muscle_group>')
@login_required
def get_exercises(muscle_group):
    """API endpoint to get exercises for a specific muscle group"""
    exercises = EXERCISES.get(muscle_group, [])
    return jsonify({'exercises': exercises})

@app.route('/download_csv')
@login_required
def download_csv():
    """Download workouts as CSV (user's own data, or all data if admin)"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Admin can see all workouts, regular users see only their own
        if current_user.is_admin:
            c.execute('''
                SELECT id, date, time, muscle_group, exercise, user_id
                FROM workouts
                ORDER BY date DESC, time DESC
            ''')
        else:
            c.execute('''
                SELECT id, date, time, muscle_group, exercise, user_id
                FROM workouts
                WHERE user_id = ?
                ORDER BY date DESC, time DESC
            ''', (current_user.id,))
        
        workouts = c.fetchall()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Add user column if admin
        if current_user.is_admin:
            writer.writerow(['User', 'Date', 'Time', 'Muscle Group', 'Exercise', 'Set Number', 'Reps', 'Weight (kg)'])
        else:
            writer.writerow(['Date', 'Time', 'Muscle Group', 'Exercise', 'Set Number', 'Reps', 'Weight (kg)'])
        
        # Write each workout with all its sets
        for workout in workouts:
            workout_id = workout['id']
            date = workout['date']
            time = workout['time']
            muscle_group = workout['muscle_group']
            exercise = workout['exercise']
            user_id = workout['user_id'] if current_user.is_admin else None
            
            # Get username if admin
            username = None
            if current_user.is_admin and user_id:
                c.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                user_data = c.fetchone()
                username = user_data['username'] if user_data else 'Unknown'
            
            # Get all sets for this workout
            c.execute('''
                SELECT set_number, reps, weight_kg
                FROM workout_sets
                WHERE workout_id = ?
                ORDER BY set_number
            ''', (workout_id,))
            sets = c.fetchall()
            
            if sets:
                for set_data in sets:
                    if current_user.is_admin:
                        writer.writerow([username, date, time, muscle_group, exercise, set_data['set_number'], set_data['reps'], set_data['weight_kg']])
                    else:
                        writer.writerow([date, time, muscle_group, exercise, set_data['set_number'], set_data['reps'], set_data['weight_kg']])
            else:
                # Write at least one row even if no sets
                if current_user.is_admin:
                    writer.writerow([username, date, time, muscle_group, exercise, '', '', ''])
                else:
                    writer.writerow([date, time, muscle_group, exercise, '', '', ''])
        
        # Create BytesIO object for Flask
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()
        
        filename = 'workouts.csv' if not current_user.is_admin else 'all_workouts.csv'
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    finally:
        conn.close()

# User Profile Route
@app.route('/profile')
@login_required
def profile():
    """User profile page showing their stats"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get user stats
        c.execute('SELECT COUNT(*) FROM workouts WHERE user_id = ?', (current_user.id,))
        total_workouts = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM sessions WHERE user_id = ?', (current_user.id,))
        total_sessions = c.fetchone()[0]
        
        c.execute('''
            SELECT COUNT(DISTINCT date) FROM workouts WHERE user_id = ?
        ''', (current_user.id,))
        workout_days = c.fetchone()[0]
        
        # Get workouts by muscle group
        c.execute('''
            SELECT muscle_group, COUNT(*) as count
            FROM workouts
            WHERE user_id = ?
            GROUP BY muscle_group
            ORDER BY count DESC
        ''', (current_user.id,))
        workouts_by_group = [(row['muscle_group'], row['count']) for row in c.fetchall()]
        
        # Get recent workouts (last 10)
        c.execute('''
            SELECT date, time, muscle_group, exercise
            FROM workouts
            WHERE user_id = ?
            ORDER BY date DESC, time DESC
            LIMIT 10
        ''', (current_user.id,))
        recent_workouts = [(row['date'], row['time'], row['muscle_group'], row['exercise']) for row in c.fetchall()]
        
        return render_template('user_profile.html',
                             total_workouts=total_workouts,
                             total_sessions=total_sessions,
                             workout_days=workout_days,
                             workouts_by_group=workouts_by_group,
                             recent_workouts=recent_workouts)
    finally:
        conn.close()

# Admin Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard with statistics"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Total users
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]
        
        # Total workouts (all users)
        c.execute('SELECT COUNT(*) FROM workouts')
        total_workouts = c.fetchone()[0]
        
        # Most active users
        c.execute('''
            SELECT u.username, COUNT(w.id) as workout_count
            FROM users u
            LEFT JOIN workouts w ON u.id = w.user_id
            GROUP BY u.id, u.username
            ORDER BY workout_count DESC
            LIMIT 10
        ''')
        most_active_users = [(row['username'], row['workout_count']) for row in c.fetchall()]
        
        # Workouts per day (last 30 days, all users)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        c.execute('''
            SELECT date, COUNT(*) as workout_count
            FROM workouts
            WHERE date >= ?
            GROUP BY date
            ORDER BY date DESC
        ''', (thirty_days_ago,))
        workouts_per_day = [(row['date'], row['workout_count']) for row in c.fetchall()]
        
        # Get all users list
        c.execute('''
            SELECT id, username, email, is_admin, created_at,
                   (SELECT COUNT(*) FROM workouts WHERE user_id = users.id) as workout_count
            FROM users
            ORDER BY created_at DESC
        ''')
        all_users = [(row['id'], row['username'], row['email'], row['is_admin'], row['created_at'], row['workout_count']) for row in c.fetchall()]
        
        return render_template('admin_dashboard.html',
                             total_users=total_users,
                             total_workouts=total_workouts,
                             most_active_users=most_active_users,
                             workouts_per_day=workouts_per_day,
                             all_users=all_users)
    finally:
        conn.close()

@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_view_user(user_id):
    """Admin view of a specific user's workout data"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get user info
        c.execute('SELECT id, username, email, is_admin, created_at FROM users WHERE id = ?', (user_id,))
        user_row = c.fetchone()
        
        if not user_row:
            flash('User not found.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        user_data = (user_row['id'], user_row['username'], user_row['email'], user_row['is_admin'], user_row['created_at'])
        
        # Get user's workouts
        c.execute('''
            SELECT w.id, w.date, w.time, w.muscle_group, w.exercise, s.start_time, s.end_time
            FROM workouts w
            LEFT JOIN sessions s ON w.session_id = s.id
            WHERE w.user_id = ?
            ORDER BY w.date DESC, w.time DESC
        ''', (user_id,))
        user_workouts = [(row['id'], row['date'], row['time'], row['muscle_group'], row['exercise'], row['start_time'], row['end_time']) for row in c.fetchall()]
        
        # Get user's sessions
        c.execute('''
            SELECT id, date, start_time, end_time, duration_minutes
            FROM sessions
            WHERE user_id = ?
            ORDER BY date DESC, start_time DESC
        ''', (user_id,))
        user_sessions = [(row['id'], row['date'], row['start_time'], row['end_time'], row['duration_minutes']) for row in c.fetchall()]
        
        # Get stats
        c.execute('SELECT COUNT(*) FROM workouts WHERE user_id = ?', (user_id,))
        total_workouts = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM sessions WHERE user_id = ?', (user_id,))
        total_sessions = c.fetchone()[0]
        
        return render_template('admin_user_view.html',
                             user_data=user_data,
                             user_workouts=user_workouts,
                             user_sessions=user_sessions,
                             total_workouts=total_workouts,
                             total_sessions=total_sessions)
    finally:
        conn.close()

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Admin delete user (but not themselves)"""
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Check if user exists
        c.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user_data = c.fetchone()
        
        if not user_data:
            flash('User not found.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Delete user (CASCADE will delete their workouts and sessions)
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        flash(f'User {user_data[0]} has been deleted.', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        conn.rollback()
        flash('Error deleting user.', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    # Run migration after initializing database (only if admin exists)
    migrate_existing_data_to_admin()
    app.run(debug=True)
