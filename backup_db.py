import psycopg2
import datetime
import os

# Use your actual database credentials
DB_URL = "postgresql://neondb_owner:npg_i1SGmv3azwOH@ep-royal-dew-aq9ups96.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def backup_database():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{timestamp}.sql"
    # This uses the pg_dump command (Postgres tool)
    # Ensure pg_dump is in your system PATH
    os.system(f"pg_dump {DB_URL} > {filename}")
    print(f"Backup created: {filename}")

if __name__ == "__main__":
    backup_database()