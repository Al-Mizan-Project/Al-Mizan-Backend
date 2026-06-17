import psycopg2

conn = psycopg2.connect(
    dbname="almizan_db",
    user="almizan_user",
    password="almizan_password",
    host="127.0.0.1",
    port="5433"
)
cursor = conn.cursor()
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
for row in cursor.fetchall():
    print(row[0])
conn.close()
