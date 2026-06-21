import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "users.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT,
            is_diabetic BOOLEAN,
            has_high_bp BOOLEAN,
            heart_condition BOOLEAN,
            weight_loss_goal BOOLEAN,
            is_vegan BOOLEAN
        )
    """)
    conn.commit()
    conn.close()

def get_user(email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None

def create_or_update_user(email: str, name: str, profile_data: dict = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if exists
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    exists = cursor.fetchone() is not None
    
    if not exists:
        cursor.execute(
            "INSERT INTO users (email, name, is_diabetic, has_high_bp, heart_condition, weight_loss_goal, is_vegan) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (email, name, False, False, False, False, False)
        )
    elif profile_data is not None:
        cursor.execute(
            """
            UPDATE users 
            SET is_diabetic = ?, has_high_bp = ?, heart_condition = ?, weight_loss_goal = ?, is_vegan = ?
            WHERE email = ?
            """,
            (
                profile_data.get('is_diabetic', False),
                profile_data.get('has_high_bp', False),
                profile_data.get('heart_condition', False),
                profile_data.get('weight_loss_goal', False),
                profile_data.get('is_vegan', False),
                email
            )
        )
        
    conn.commit()
    conn.close()
    return not exists # Returns True if it was a new user
