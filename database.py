import sqlite3
from sqlite3 import Error
from config import DB_NAME
from enum import Enum
import time

class TransactionState(Enum):
    PENDING = 1
    PAID = 2
    CANCELLED = -1
    FAILED = -2

def migrate_database():
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            
            # Check and add columns to users table
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'free_uses_left' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN free_uses_left INTEGER DEFAULT 3")
            if 'purchased_uses' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN purchased_uses INTEGER DEFAULT 0")
            if 'usage_count' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN usage_count INTEGER DEFAULT 0")
            
            # Create transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paycom_transaction_id TEXT UNIQUE,
                    paycom_time TEXT,
                    paycom_state INTEGER,
                    user_id INTEGER,
                    amount INTEGER,
                    uses INTEGER,
                    create_time INTEGER,
                    perform_time INTEGER,
                    cancel_time INTEGER,
                    reason INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            conn.commit()
            print("Database migration completed successfully.")
        except Error as e:
            print(f"Error during database migration: {e}")
        finally:
            conn.close()
    else:
        print("Error! Cannot create the database connection.")

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        return conn
    except Error as e:
        print(e)
    return conn

def create_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                phone_number TEXT,
                usage_count INTEGER DEFAULT 0,
                free_uses_left INTEGER DEFAULT 3,
                purchased_uses INTEGER DEFAULT 0
            )
        ''')
    except Error as e:
        print(e)

def increment_usage_count(user_id):
    conn = create_connection()
    sql = ''' UPDATE users SET usage_count = usage_count + 1 WHERE id = ? '''
    cur = conn.cursor()
    cur.execute(sql, (user_id,))
    conn.commit()
    conn.close()

def get_usage_count(user_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT usage_count FROM users WHERE id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user(user_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def add_user(user_id):
    conn = create_connection()
    sql = ''' INSERT OR IGNORE INTO users(id, free_uses_left, purchased_uses) VALUES(?, 3, 0) '''
    cur = conn.cursor()
    cur.execute(sql, (user_id,))
    conn.commit()
    conn.close()

def update_phone_number(user_id, phone_number):
    conn = create_connection()
    sql = ''' UPDATE users SET phone_number = ? WHERE id = ? '''
    cur = conn.cursor()
    cur.execute(sql, (phone_number, user_id))
    conn.commit()
    conn.close()

def decrement_free_uses(user_id):
    conn = create_connection()
    sql = ''' UPDATE users SET free_uses_left = free_uses_left - 1 WHERE id = ? AND free_uses_left > 0 '''
    cur = conn.cursor()
    cur.execute(sql, (user_id,))
    conn.commit()
    conn.close()

def decrement_purchased_uses(user_id):
    conn = create_connection()
    sql = ''' UPDATE users SET purchased_uses = purchased_uses - 1 WHERE id = ? AND purchased_uses > 0 '''
    cur = conn.cursor()
    cur.execute(sql, (user_id,))
    conn.commit()
    conn.close()

def get_free_uses_left(user_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT free_uses_left FROM users WHERE id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_purchased_uses(user_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT purchased_uses FROM users WHERE id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def add_purchased_uses(user_id, amount):
    conn = create_connection()
    sql = ''' UPDATE users SET purchased_uses = purchased_uses + ? WHERE id = ? '''
    cur = conn.cursor()
    cur.execute(sql, (amount, user_id))
    conn.commit()
    conn.close()


# Transaction-related functions
def create_transaction(user_id: int, paycom_transaction_id: str, amount: int, uses: int, create_time: int) -> int:
    """Create a new transaction record"""
    conn = create_connection()
    try:
        cursor = conn.cursor()
        current_time = int(time.time() * 1000)  # Paycom uses millisecond timestamps
        
        cursor.execute('''
            INSERT INTO transactions (
                paycom_transaction_id, user_id, amount, uses, 
                paycom_state, create_time
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (paycom_transaction_id, user_id, amount, uses, 
              TransactionState.PENDING.value, current_time))
        
        transaction_id = cursor.lastrowid
        conn.commit()
        return transaction_id
    except Error as e:
        print(f"Error creating transaction: {e}")
        raise
    finally:
        conn.close()

def get_transaction_by_paycom_id(paycom_transaction_id: str) -> tuple:
    """Get transaction details by Paycom transaction ID"""
    conn = create_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE paycom_transaction_id = ?
        ''', (paycom_transaction_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def update_transaction_status(paycom_transaction_id: str, state: TransactionState, 
                            perform_time: int = 0, cancel_time: int = 0, 
                            reason: int = None) -> bool:
    """Update transaction status and related fields"""
    conn = create_connection()
    try:
        cursor = conn.cursor()
        
        update_fields = ["paycom_state = ?"]
        params = [state.value]
        
        if perform_time is not None:
            update_fields.append("perform_time = ?")
            params.append(perform_time)
        
        if cancel_time is not None:
            update_fields.append("cancel_time = ?")
            params.append(cancel_time)
        
        if reason is not None:
            update_fields.append("reason = ?")
            params.append(reason)
            
        params.append(paycom_transaction_id)
        
        sql = f'''
            UPDATE transactions 
            SET {", ".join(update_fields)}
            WHERE paycom_transaction_id = ?
        '''
        
        cursor.execute(sql, params)
        
        if state == TransactionState.PAID:
            # Get transaction details
            cursor.execute('''
                SELECT user_id, uses 
                FROM transactions 
                WHERE paycom_transaction_id = ?
            ''', (paycom_transaction_id,))
            transaction = cursor.fetchone()
            
            if transaction:
                user_id, uses = transaction
                # Add purchased uses to user
                cursor.execute('''
                    UPDATE users 
                    SET purchased_uses = purchased_uses + ? 
                    WHERE id = ?
                ''', (uses, user_id))
        
        conn.commit()
        return True
    except Error as e:
        print(f"Error updating transaction: {e}")
        return False
    finally:
        conn.close()

def get_transactions_by_user(user_id: int) -> list:
    """Get all transactions for a specific user"""
    conn = create_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE user_id = ? 
            ORDER BY create_time DESC
        ''', (user_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def get_pending_transaction(user_id: int) -> tuple:
    """Get the latest pending transaction for a user"""
    conn = create_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE user_id = ? AND paycom_state = ? 
            ORDER BY create_time DESC 
            LIMIT 1
        ''', (user_id, TransactionState.PENDING.value))
        return cursor.fetchone()
    finally:
        conn.close()
# Initialize the database
conn = create_connection()
if conn is not None:
    create_table(conn)
    conn.close()
else:
    print("Error! Cannot create the database connection.")