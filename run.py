"""
PolicyWatch - Unified Application Runner
Entry point for running the integrated PolicyWatch Web Application.
"""
import os
import sys

# Ensure repository root and submodule paths are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

models_path = os.path.join(PROJECT_ROOT, 'models')
if models_path not in sys.path:
    sys.path.insert(0, models_path)

from models import database as db
from models.app import app

def main():
    print("=" * 65)
    print("   POLICYWATCH - Privacy Policy & Terms Change Tracker")
    print("   Unified System: Scraping, Storage, Auth, Diff & Alerts")
    print("=" * 65)

    # Initialize database if needed
    db_file = db.DATABASE_FILE
    if not os.path.exists(db_file):
        print("[*] Initializing tracker database...")
        db.init_db()
        from models import sample_data
        sample_data.insert_sample_data()
        print("[+] Seeded sample data successfully.")
    else:
        # Run automatic migrations/upgrades if any column/table was added
        db.ensure_schema_upgrades()
        print(f"[+] Connected to database: {db_file}")

    print("\n[+] Demo Accounts Available:")
    print("    - Admin:    admin / admin123")
    print("    - User:     john_doe / password123")
    print("\n[*] Starting server on http://127.0.0.1:5000 ...")
    print("    Press Ctrl+C to stop.")
    print("=" * 65 + "\n")

    app.run(host="127.0.0.1", port=5000, debug=True)

if __name__ == '__main__':
    main()
