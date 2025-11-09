from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)

# Exercise data based on muscle groups
EXERCISES = {
    'Chest': ['Bench Press', 'Incline Bench Press', 'Decline Bench Press', 'Dumbbell Flyes', 'Push-ups', 'Cable Crossover'],
    'Back': ['Deadlift', 'Pull-ups', 'Barbell Row', 'Lat Pulldown', 'T-Bar Row', 'Cable Row'],
    'Shoulders': ['Overhead Press', 'Lateral Raises', 'Front Raises', 'Rear Delt Flyes', 'Shrugs', 'Arnold Press'],
    'Arms': ['Bicep Curls', 'Tricep Dips', 'Hammer Curls', 'Tricep Extensions', 'Preacher Curls', 'Close Grip Bench Press'],
    'Legs': ['Squats', 'Leg Press', 'Lunges', 'Leg Curls', 'Leg Extensions', 'Calf Raises'],
    'Core': ['Plank', 'Crunches', 'Russian Twists', 'Leg Raises', 'Mountain Climbers', 'Bicycle Crunches']
}

def get_db_connection():
    """Get a database connection with proper timeout and settings"""
    conn = sqlite3.connect('workouts.db', timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')  # Enable Write-Ahead Logging for better concurrency
    return conn

def init_db():
    """Initialize the database with the required schema"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
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
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                muscle_group TEXT NOT NULL,
                exercise TEXT NOT NULL
            )
        ''')
        
        # Sessions table - tracks gym sessions
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_minutes REAL
            )
        ''')
        
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

@app.route('/')
def index():
    """Main page displaying the form and last session"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Check if there's an active session (no end_time)
        c.execute('''
            SELECT id, date, start_time
            FROM sessions
            WHERE end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''')
        active_session = c.fetchone()
        
        # Get last completed session (even if there's an active one, show the last completed)
        c.execute('''
            SELECT id, date, start_time, end_time, duration_minutes
            FROM sessions
            WHERE end_time IS NOT NULL
            ORDER BY date DESC, end_time DESC
            LIMIT 1
        ''')
        last_session = c.fetchone()
        
        session_data = None
        session_workouts = []
        
        if last_session:
            session_id = last_session[0]
            # Get all workouts for this session
            c.execute('''
                SELECT id, date, time, muscle_group, exercise
                FROM workouts
                WHERE session_id = ?
                ORDER BY time
            ''', (session_id,))
            workouts = c.fetchall()
            
            # Get sets for each workout
            for workout in workouts:
                workout_id = workout[0]
                c.execute('''
                    SELECT set_number, reps, weight_kg
                    FROM workout_sets
                    WHERE workout_id = ?
                    ORDER BY set_number
                ''', (workout_id,))
                sets = c.fetchall()
                session_workouts.append({
                    'id': workout[0],
                    'date': workout[1],
                    'time': workout[2],
                    'muscle_group': workout[3],
                    'exercise': workout[4],
                    'sets': sets
                })
            
            session_data = {
                'id': last_session[0],
                'date': last_session[1],
                'start_time': last_session[2],
                'end_time': last_session[3],
                'duration_minutes': last_session[4]
            }
        
        # Check for error messages
        error = request.args.get('error')
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
def start_session():
    """Start a new gym session"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Check if there's already an active session
        c.execute('''
            SELECT id FROM sessions
            WHERE end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''')
        active_session = c.fetchone()
        
        if active_session:
            # Session already active, just redirect
            return redirect(url_for('index'))
        
        # Get current date and time
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        start_time = now.strftime('%H:%M:%S')
        
        # Create new session
        c.execute('''
            INSERT INTO sessions (date, start_time)
            VALUES (?, ?)
        ''', (date, start_time))
        
        conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.route('/end_session', methods=['POST'])
def end_session():
    """End the current gym session and calculate duration"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get active session
        c.execute('''
            SELECT id, date, start_time
            FROM sessions
            WHERE end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''')
        active_session = c.fetchone()
        
        if not active_session:
            return redirect(url_for('index'))
        
        session_id = active_session[0]
        session_date = active_session[1]
        start_time_str = active_session[2]
        
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
            WHERE id = ?
        ''', (end_time, duration, session_id))
        
        conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.route('/submit', methods=['POST'])
def submit():
    """Handle form submission and save workout to database"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get active session - REQUIRED for workout submission
        c.execute('''
            SELECT id FROM sessions
            WHERE end_time IS NULL
            ORDER BY date DESC, start_time DESC
            LIMIT 1
        ''')
        active_session = c.fetchone()
        
        if not active_session:
            # No active session - redirect back with error message
            return redirect(url_for('index', error='no_session'))
        
        session_id = active_session[0]
        
        # Get current date and time
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        time = now.strftime('%H:%M:%S')
        
        # Get form data
        muscle_group = request.form.get('muscle_group')
        exercise = request.form.get('exercise')
        
        # Insert workout into database with session_id
        c.execute('''
            INSERT INTO workouts (date, time, muscle_group, exercise, session_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (date, time, muscle_group, exercise, session_id))
        
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
        return redirect(url_for('index', submitted='1'))
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.route('/exercises/<muscle_group>')
def get_exercises(muscle_group):
    """API endpoint to get exercises for a specific muscle group"""
    exercises = EXERCISES.get(muscle_group, [])
    return {'exercises': exercises}

@app.route('/download_csv')
def download_csv():
    """Download all workouts as CSV"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            SELECT id, date, time, muscle_group, exercise
            FROM workouts
            ORDER BY date DESC, time DESC
        ''')
        workouts = c.fetchall()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Time', 'Muscle Group', 'Exercise', 'Set Number', 'Reps', 'Weight (kg)'])
        
        # Write each workout with all its sets
        for workout in workouts:
            workout_id = workout[0]
            date = workout[1]
            time = workout[2]
            muscle_group = workout[3]
            exercise = workout[4]
            
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
                    writer.writerow([date, time, muscle_group, exercise, set_data[0], set_data[1], set_data[2]])
            else:
                # Write at least one row even if no sets
                writer.writerow([date, time, muscle_group, exercise, '', '', ''])
        
        # Create BytesIO object for Flask
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='workouts.csv'
        )
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

