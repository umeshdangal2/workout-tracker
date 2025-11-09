from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import csv
import io
from datetime import datetime

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
    """Main page displaying the form and last 10 workouts"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        # Get last 10 workouts
        c.execute('''
            SELECT id, date, time, muscle_group, exercise
            FROM workouts
            ORDER BY date DESC, time DESC
            LIMIT 10
        ''')
        workouts = c.fetchall()
        
        # Get sets for each workout
        workouts_with_sets = []
        for workout in workouts:
            workout_id = workout[0]
            c.execute('''
                SELECT set_number, reps, weight_kg
                FROM workout_sets
                WHERE workout_id = ?
                ORDER BY set_number
            ''', (workout_id,))
            sets = c.fetchall()
            workouts_with_sets.append({
                'id': workout[0],
                'date': workout[1],
                'time': workout[2],
                'muscle_group': workout[3],
                'exercise': workout[4],
                'sets': sets
            })
        
        return render_template('index.html', workouts=workouts_with_sets, exercises=EXERCISES)
    finally:
        conn.close()

@app.route('/submit', methods=['POST'])
def submit():
    """Handle form submission and save workout to database"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get current date and time
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        time = now.strftime('%H:%M:%S')
        
        # Get form data
        muscle_group = request.form.get('muscle_group')
        exercise = request.form.get('exercise')
        
        # Insert workout into database
        c.execute('''
            INSERT INTO workouts (date, time, muscle_group, exercise)
            VALUES (?, ?, ?, ?)
        ''', (date, time, muscle_group, exercise))
        
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

