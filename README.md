# Workout Tracker

A simple web application for tracking workouts built with Flask and SQLite.

## Features

- Log workouts with muscle group, exercise, sets, reps, and weight
- Auto-filled date and time
- View last 10 workouts in a table
- Download all workout data as CSV
- Mobile-friendly interface with Tailwind CSS

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Run the Flask app:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

1. Select a muscle group from the dropdown
2. Select an exercise (populated based on muscle group)
3. Enter sets, reps, and weight
4. Date and time are automatically filled
5. Click "Submit Workout" to save
6. View your last 10 workouts in the table below
7. Click "Download CSV" to export all data

## Database

The application uses SQLite with a database file named `workouts.db` that is automatically created on first run.

Schema:
- id (INTEGER PRIMARY KEY)
- date (TEXT)
- time (TEXT)
- muscle_group (TEXT)
- exercise (TEXT)
- sets (INTEGER)
- reps (INTEGER)
- weight_kg (REAL)

