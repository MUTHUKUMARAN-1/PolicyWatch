import os
from models import database as db
from models.app import app

db_file = db.DATABASE_FILE

if not os.path.exists(db_file):
    db.init_db()
    from models import sample_data
    sample_data.insert_sample_data()
else:
    db.ensure_schema_upgrades()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)