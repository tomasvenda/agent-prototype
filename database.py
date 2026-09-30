import sqlite3
from datetime import datetime
import os


DB_PATH = os.getenv(
    "WORKSHOP_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "workshop.db"),
)
MAX_PER_DAY = 2   # business rule: max appointments per day


def is_valid_date(date: str) -> bool:
    """Returns True only for real dates in exact YYYY-MM-DD format."""
    try:
        return datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d") == date
    except ValueError:
        return False


def init_db():
    """Initializes the mock dealership database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            service_type TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()


# ======================================================================
# DATA FUNCTIONS: return real Python data. Used by the REST API.
# ======================================================================

def count_appointments(date: str) -> int:
    """How many appointments exist on this date."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM appointments WHERE date = ?', (date,))
    count = c.fetchone()[0]
    conn.close()
    return count


def is_available(date: str) -> bool:
    return count_appointments(date) < MAX_PER_DAY


def list_appointments(date: str | None = None) -> list[dict]:
    """All appointments, or only those on one date if a date is given."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if date is None:
        c.execute('SELECT id, customer_name, service_type, date FROM appointments ORDER BY date, id')
    else:
        c.execute('SELECT id, customer_name, service_type, date FROM appointments WHERE date = ? ORDER BY id', (date,))
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "customer_name": r[1], "service_type": r[2], "date": r[3]}
        for r in rows
    ]


def get_appointment(appointment_id: int) -> dict | None:
    """One appointment by id, or None if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, customer_name, service_type, date FROM appointments WHERE id = ?', (appointment_id,))
    r = c.fetchone()
    conn.close()
    if r is None:
        return None
    return {"id": r[0], "customer_name": r[1], "service_type": r[2], "date": r[3]}


def create_appointment(customer_name: str, service_type: str, date: str) -> int:
    """Inserts a row and returns the new appointment's id. Does NOT check rules."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO appointments (customer_name, service_type, date) VALUES (?, ?, ?)',
              (customer_name, service_type, date))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def delete_appointment(appointment_id: int) -> bool:
    """Deletes by id. Returns True if a row was deleted, False if it didn't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted


# ======================================================================
# AGENT FUNCTIONS: return sentences for Claude to read. Used by agent.py.
# ======================================================================

def check_availability(date: str) -> str:
    if not is_valid_date(date):
        return f"Error: '{date}' is not a valid date. Use YYYY-MM-DD format."
    if is_available(date):
        return f"Yes, {date} is available."
    return f"No, {date} is fully booked."


def book_appointment(customer_name: str, service_type: str, date: str) -> str:
    if not is_valid_date(date):
        return f"Error: '{date}' is not a valid date. Use YYYY-MM-DD format."
    if not is_available(date):
        return f"Error: Cannot book. {date} is already full."
    create_appointment(customer_name, service_type, date)
    return f"Success! Appointment confirmed for {customer_name} on {date} for a {service_type}."


def cancel_appointment(customer_name: str, date: str) -> str:
    if not is_valid_date(date):
        return f"Error: '{date}' is not a valid date. Use YYYY-MM-DD format."
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM appointments WHERE customer_name = ? AND date = ?', (customer_name, date))
    row = c.fetchone()
    conn.close()

    if row is None:
        return f"Error: No appointment found for {customer_name} on {date}."

    delete_appointment(row[0])
    return f"Success! The appointment for {customer_name} on {date} has been cancelled."


if __name__ == "__main__":
    init_db()
    print("Database initialized.")