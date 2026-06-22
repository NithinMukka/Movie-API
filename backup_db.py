import subprocess
import datetime
import os
from config import settings

def backup_database():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{timestamp}.sql"
    
    try:
        with open(filename, "w") as f:
            # Secure invocation using subprocess list without shell=True
            subprocess.run(
                ["pg_dump", settings.database_url],
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        print(f"Backup created: {filename}")
    except subprocess.CalledProcessError as e:
        if os.path.exists(filename):
            os.remove(filename)
        print(f"Database backup failed. pg_dump error:\n{e.stderr}")
    except FileNotFoundError:
        if os.path.exists(filename):
            os.remove(filename)
        print("Error: pg_dump executable not found. Please ensure it is installed and added to the PATH.")
    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        print(f"An unexpected error occurred during backup: {e}")

if __name__ == "__main__":
    backup_database()