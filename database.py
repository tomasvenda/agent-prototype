import sqlite3

def init_db():
    """Initializes the mock dealership database."""
    conn = sqlite3.connect('workshop.db')
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

def check_availability(date: str) -> str:
    """Checks if a specific date has open slots."""
    conn = sqlite3.connect('workshop.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM appointments WHERE date = ?', (date,))
    count = c.fetchone()[0]
    conn.close()
    
    if count < 2:
        return f"Yes, {date} is available."
    return f"No, {date} is fully booked."

def book_appointment(customer_name: str, service_type: str, date: str) -> str:
    """Writes a new appointment to the database."""
    # First, verify availability programmatically as a safeguard
    if "No" in check_availability(date):
        return f"Error: Cannot book. {date} is already full."
        
    conn = sqlite3.connect('workshop.db')
    c = conn.cursor()
    c.execute('INSERT INTO appointments (customer_name, service_type, date) VALUES (?, ?, ?)', 
              (customer_name, service_type, date))
    conn.commit()
    conn.close()
    
    return f"Success! Appointment confirmed for {customer_name} on {date} for a {service_type}."

def cancel_appointment(customer_name: str, date: str) -> str:
    """Cancels an existing appointment for a customer on a specific date."""
    conn = sqlite3.connect('workshop.db')
    c = conn.cursor()
    
    # Check if the appointment actually exists first
    c.execute('SELECT id FROM appointments WHERE customer_name = ? AND date = ?', (customer_name, date))
    row = c.fetchone()
    
    if row is None:
        conn.close()
        return f"Error: No appointment found for {customer_name} on {date}."
        
    # If it exists, delete it
    c.execute('DELETE FROM appointments WHERE id = ?', (row[0],))
    conn.commit()
    conn.close()
    
    return f"Success! The appointment for {customer_name} on {date} has been cancelled."


# Initialize the database when the file is run
if __name__ == "__main__":
    init_db()
    print("Database initialized.")