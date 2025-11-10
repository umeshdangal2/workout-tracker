"""
Script to create admin user for Workout Tracker
Run this script to create the admin account with a password you choose.
"""
import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime
import getpass

def create_admin():
    """Create admin user in the database"""
    conn = sqlite3.connect('workouts.db')
    try:
        c = conn.cursor()
        
        # Check if admin user already exists
        c.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        existing_admin = c.fetchone()
        
        if existing_admin:
            print("Admin user already exists!")
            response = input("Do you want to update the admin password? (y/n): ").strip().lower()
            if response != 'y':
                print("Exiting...")
                return
            
            # Update admin password
            password = getpass.getpass("Enter new admin password: ")
            if len(password) < 6:
                print("Password must be at least 6 characters long.")
                return
            
            password_hash = generate_password_hash(password)
            c.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, 'admin'))
            conn.commit()
            print("Admin password updated successfully!")
            return
        
        # Create new admin user
        print("Creating admin user...")
        password = getpass.getpass("Enter admin password (min. 6 characters): ")
        
        if len(password) < 6:
            print("Password must be at least 6 characters long.")
            return
        
        password_hash = generate_password_hash(password)
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, created_at)
            VALUES (?, ?, ?, 1, ?)
        ''', ('admin', 'admin@workouttracker.com', password_hash, created_at))
        
        conn.commit()
        admin_id = c.lastrowid
        
        # Migrate existing workouts and sessions to admin
        c.execute('UPDATE workouts SET user_id = ? WHERE user_id IS NULL', (admin_id,))
        c.execute('UPDATE sessions SET user_id = ? WHERE user_id IS NULL', (admin_id,))
        conn.commit()
        
        print("Admin user created successfully!")
        print("Username: admin")
        print("Any existing workouts and sessions have been assigned to the admin account.")
        print("You can now log in with this account.")
        
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        print("Make sure the database has been initialized by running app.py first.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    create_admin()

