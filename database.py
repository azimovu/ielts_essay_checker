import sqlite3
from sqlite3 import Error
from config import DB_NAME

def migrate_database():
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            # Check if the columns exist, if not, add them
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'free_uses_left' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN free_uses_left INTEGER DEFAULT 3")
            
            if 'purchased_uses' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN purchased_uses INTEGER DEFAULT 0")
            
            if 'usage_count' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN usage_count INTEGER DEFAULT 0")
            
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

def create_transaction_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                state INTEGER,
                create_time INTEGER,
                perform_time INTEGER,
                cancel_time INTEGER,
                reason TEXT,
                order_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
    except Error as e:
        print(e)

def add_transaction(transaction_id, user_id, amount, state, create_time, order_id):
    conn = create_connection()
    sql = '''INSERT INTO transactions(id, user_id, amount, state, create_time, order_id)
             VALUES(?, ?, ?, ?, ?, ?)'''
    cur = conn.cursor()
    cur.execute(sql, (transaction_id, user_id, amount, state, create_time, order_id))
    conn.commit()
    conn.close()

def get_transaction(transaction_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    transaction = cur.fetchone()
    conn.close()
    return transaction

def update_transaction(transaction_id, state, perform_time=None, cancel_time=None, reason=None):
    conn = create_connection()
    sql = '''UPDATE transactions
             SET state = ?, perform_time = ?, cancel_time = ?, reason = ?
             WHERE id = ?'''
    cur = conn.cursor()
    cur.execute(sql, (state, perform_time, cancel_time, reason, transaction_id))
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = create_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE order_id = ?", (order_id,))
    order = cur.fetchone()
    conn.close()
    return order

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

# Initialize the database
conn = create_connection()
if conn is not None:
    create_table(conn)
    create_transaction_table(conn)
    conn.close()
else:
    print("Error! Cannot create the database connection.")