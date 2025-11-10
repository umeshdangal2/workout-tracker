# Setup Instructions for Workout Tracker with Authentication

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask==3.0.0
- Flask-Login==0.6.3
- Werkzeug==3.0.1

## Step 2: Initialize Database

Run the application once to initialize the database:

```bash
python app.py
```

This will create the `workouts.db` file with all necessary tables:
- `users` table (for user authentication)
- `workouts` table (with `user_id` foreign key)
- `sessions` table (with `user_id` foreign key)
- `workout_sets` table

**Note:** If you have existing workout data, it will be preserved. The database migration will assign existing workouts to the admin user when you create the admin account.

## Step 3: Create Admin User

Run the admin creation script:

```bash
python create_admin.py
```

You will be prompted to:
1. Enter a password for the admin account (minimum 6 characters)
2. The admin username is: `admin`
3. Email is set to: `admin@workouttracker.com`

**Important:**
- If admin user already exists, you can update the password
- Any existing workouts and sessions without a `user_id` will be assigned to the admin account
- Keep your admin password safe!

## Step 4: Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

## Step 5: First Login

1. Navigate to `http://localhost:5000`
2. You will be redirected to the login page
3. Login with:
   - Username: `admin`
   - Password: (the password you set in Step 3)

## Step 6: Create Regular Users

1. Click on "Register" in the navigation bar
2. Fill in the registration form:
   - Username (must be unique)
   - Email (must be unique)
   - Password (minimum 6 characters)
   - Confirm Password
3. After registration, you'll be redirected to login
4. Login with your new credentials

## Features Available

### For Regular Users:
- ✅ Log workouts (after starting a session)
- ✅ View your own workout data
- ✅ View your profile with statistics
- ✅ Download your workout data as CSV
- ✅ Start/end gym sessions

### For Admins:
- ✅ All regular user features
- ✅ View admin dashboard
- ✅ View all users
- ✅ View any user's workout data
- ✅ Delete users (except yourself)
- ✅ View statistics (total users, total workouts, most active users, workouts per day)
- ✅ Download all users' workout data as CSV

## Security Notes

⚠️ **Before deploying to production:**

1. Change the `SECRET_KEY` in `app.py` (line 8):
   ```python
   app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
   ```
   Generate a strong random secret key for production use.

2. Consider adding CSRF protection using Flask-WTF if needed

3. Use a production-grade web server (like Gunicorn) instead of Flask's development server

4. Use environment variables for sensitive configuration

## Troubleshooting

### Database Errors
If you encounter database errors:
1. Make sure `workouts.db` file exists
2. Try deleting `workouts.db` and running `app.py` again to recreate it
3. Make sure you have write permissions in the application directory

### Login Issues
- Make sure you've created the admin user using `create_admin.py`
- Check that the password is at least 6 characters
- Verify that the database has been initialized

### Migration Issues
- If existing workouts don't show up after creating admin:
  1. Make sure you ran `create_admin.py` after the database was initialized
  2. Check that the `workouts` table has a `user_id` column
  3. The migration assigns orphaned workouts to admin when admin is created

## Database Schema Changes

The following changes were made to support user authentication:

1. **New `users` table:**
   - `id` (PRIMARY KEY)
   - `username` (UNIQUE)
   - `email` (UNIQUE)
   - `password_hash`
   - `is_admin` (0 or 1)
   - `created_at`

2. **Modified `workouts` table:**
   - Added `user_id` column (FOREIGN KEY to users.id)
   - Existing workouts are assigned to admin user

3. **Modified `sessions` table:**
   - Added `user_id` column (FOREIGN KEY to users.id)
   - Existing sessions are assigned to admin user

## Support

If you encounter any issues:
1. Check the Flask console for error messages
2. Verify all dependencies are installed
3. Make sure the database file is not locked by another process
4. Check that all template files are in the `templates/` directory

