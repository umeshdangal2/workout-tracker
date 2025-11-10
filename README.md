# Workout Tracker

A web application for tracking workouts built with Flask, SQLite, and Flask-Login. Features user authentication, user-specific workout tracking, and an admin panel.

## Features

- **User Authentication**
  - User registration and login
  - Password hashing for security
  - Session management with Flask-Login
  - User-specific workout data

- **Workout Tracking**
  - Log workouts with muscle group, exercise, sets, reps, and weight
  - Gym session management (start/end sessions)
  - Auto-filled date and time
  - View last session workouts
  - Download workout data as CSV (user's own data, or all data for admins)

- **User Dashboard**
  - View personal workout statistics
  - See workouts by muscle group
  - View recent workouts
  - User profile page

- **Admin Panel**
  - View all users
  - View any user's workout data
  - Statistics dashboard (total users, total workouts, most active users, workouts per day)
  - Delete users (except own account)

- **UI/UX**
  - Clean, mobile-friendly interface with Tailwind CSS
  - Flash messages for success/errors
  - Protected routes with login requirement
  - Consistent navigation bar

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Initialize the database by running the app once:
```bash
python app.py
```

3. Create the admin account:
```bash
python create_admin.py
```
   - Enter a password when prompted (minimum 6 characters)
   - The admin username is: `admin`
   - Any existing workouts and sessions will be assigned to the admin account

## Running the Application

1. Run the Flask app:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. You will be redirected to the login page if not authenticated.

## Usage

### For Regular Users

1. **Register a new account** or **login** with existing credentials
2. **Start a gym session** before logging workouts
3. Select a muscle group from the dropdown
4. Select an exercise (populated based on muscle group)
5. Enter sets, reps, and weight
6. Click "Submit Workout" to save
7. View your last session workouts in the table below
8. Click "Download CSV" to export your workout data
9. Visit your **Profile** page to see statistics

### For Admins

1. **Login** with the admin account (username: `admin`)
2. Access the **Admin Dashboard** from the navigation bar
3. View all users, statistics, and user workout data
4. Delete users (except your own account)
5. Download CSV exports include all users' data

## Database Schema

### Users Table
- `id` (INTEGER PRIMARY KEY)
- `username` (TEXT UNIQUE)
- `email` (TEXT UNIQUE)
- `password_hash` (TEXT)
- `is_admin` (INTEGER, 0 or 1)
- `created_at` (TEXT)

### Workouts Table
- `id` (INTEGER PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY to users.id)
- `date` (TEXT)
- `time` (TEXT)
- `muscle_group` (TEXT)
- `exercise` (TEXT)
- `session_id` (INTEGER, FOREIGN KEY to sessions.id)

### Sessions Table
- `id` (INTEGER PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY to users.id)
- `date` (TEXT)
- `start_time` (TEXT)
- `end_time` (TEXT)
- `duration_minutes` (REAL)

### Workout Sets Table
- `id` (INTEGER PRIMARY KEY)
- `workout_id` (INTEGER, FOREIGN KEY to workouts.id)
- `set_number` (INTEGER)
- `reps` (INTEGER)
- `weight_kg` (REAL)

## Security

- Passwords are hashed using Werkzeug's password hashing
- Sessions are managed with Flask-Login
- All routes are protected with `@login_required` decorator
- Admin routes are protected with `@admin_required` decorator
- Users can only see their own workout data (unless admin)
- CSRF protection can be added by enabling Flask-WTF if needed

## Creating the Admin User

To create or update the admin user:

```bash
python create_admin.py
```

- Enter the password when prompted
- The script will create the admin user if it doesn't exist
- If the admin user already exists, you can update the password
- Existing workouts and sessions without a user_id will be assigned to admin

## Migration

The application automatically migrates existing workout data when:
1. The database is initialized (on first run)
2. The admin user is created (assigns orphaned workouts to admin)

Existing workouts and sessions without a `user_id` will be assigned to the admin account when the admin user is first created.

## Notes

- Change the `SECRET_KEY` in `app.py` before deploying to production
- The database file `workouts.db` is created automatically
- All user data is isolated - users can only see their own workouts
- Admins have full access to view all user data and delete users
