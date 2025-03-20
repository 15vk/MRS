import sys
import os

# Add the 'instances' directory to the Python module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'instances')))

from MRS15 import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)