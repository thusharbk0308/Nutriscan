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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_intake (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            date TEXT NOT NULL, -- YYYY-MM-DD format
            product_name TEXT NOT NULL,
            energy_kcal REAL DEFAULT 0,
            sugars_g REAL DEFAULT 0,
            sodium_mg REAL DEFAULT 0,
            saturated_fat_g REAL DEFAULT 0,
            protein_g REAL DEFAULT 0,
            carbohydrates_g REAL DEFAULT 0,
            fat_g REAL DEFAULT 0,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(email) REFERENCES users(email)
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

def log_intake(email: str, date_str: str, product_name: str, nutrients: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO daily_intake (
            email, date, product_name, energy_kcal, sugars_g, sodium_mg, 
            saturated_fat_g, protein_g, carbohydrates_g, fat_g, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email,
            date_str,
            product_name,
            nutrients.get("energy_kcal", 0.0) or 0.0,
            nutrients.get("sugars_g", 0.0) or 0.0,
            nutrients.get("sodium_mg", 0.0) or 0.0,
            nutrients.get("saturated_fat_g", 0.0) or 0.0,
            nutrients.get("protein_g", 0.0) or 0.0,
            nutrients.get("carbohydrates_g", 0.0) or 0.0,
            nutrients.get("fat_g", 0.0) or 0.0,
            now_ts
        )
    )
    conn.commit()
    conn.close()

def get_daily_intake(email: str, date_str: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM daily_intake WHERE email = ? AND date = ? ORDER BY timestamp DESC",
        (email, date_str)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_intake_item(item_id: int, email: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_intake WHERE id = ? AND email = ?", (item_id, email))
    conn.commit()
    conn.close()

def get_daily_totals(email: str, date_str: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            SUM(energy_kcal) as energy_kcal,
            SUM(sugars_g) as sugars_g,
            SUM(sodium_mg) as sodium_mg,
            SUM(saturated_fat_g) as saturated_fat_g,
            SUM(protein_g) as protein_g,
            SUM(carbohydrates_g) as carbohydrates_g,
            SUM(fat_g) as fat_g
        FROM daily_intake 
        WHERE email = ? AND date = ?
        """,
        (email, date_str)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] is not None:
        return {
            "energy_kcal": float(row[0] or 0.0),
            "sugars_g": float(row[1] or 0.0),
            "sodium_mg": float(row[2] or 0.0),
            "saturated_fat_g": float(row[3] or 0.0),
            "protein_g": float(row[4] or 0.0),
            "carbohydrates_g": float(row[5] or 0.0),
            "fat_g": float(row[6] or 0.0),
        }
    return {
        "energy_kcal": 0.0,
        "sugars_g": 0.0,
        "sodium_mg": 0.0,
        "saturated_fat_g": 0.0,
        "protein_g": 0.0,
        "carbohydrates_g": 0.0,
        "fat_g": 0.0,
    }

