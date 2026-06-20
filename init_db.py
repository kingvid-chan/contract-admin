"""
Database initialization script for Contract Admin.
Creates all tables and inserts the default admin user.

Usage:
    python init_db.py

Default admin credentials:
    Username: demo
    Password: demo123
"""

from app import create_app
from models import db, User, Contract, Attachment

app = create_app()

with app.app_context():
    # Create all tables
    db.create_all()
    print('[OK] Database tables created.')

    # Check if demo admin already exists
    existing = User.query.filter_by(username='demo').first()
    if existing:
        print(f'[SKIP] Demo admin already exists (id={existing.id}).')
    else:
        admin = User(username='demo', role='admin')
        admin.set_password('demo123')
        db.session.add(admin)
        db.session.commit()
        print('[OK] Default admin created: username=demo, password=demo123')

    # Summary
    user_count = User.query.count()
    print(f'[INFO] Total users: {user_count}')
    print('[DONE] Database initialization complete.')
