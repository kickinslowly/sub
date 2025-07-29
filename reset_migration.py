import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('instance/portal.db')
cursor = conn.cursor()

# Check if alembic_version table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
table_exists = cursor.fetchone()

if table_exists:
    print("alembic_version table exists. Dropping it...")
    cursor.execute("DROP TABLE alembic_version")
    conn.commit()
    print("alembic_version table dropped successfully.")
else:
    print("alembic_version table does not exist.")

# Close the connection
conn.close()