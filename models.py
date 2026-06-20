import bcrypt
from datetime import datetime, timezone
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    contracts = db.relationship('Contract', back_populates='creator', lazy='dynamic')

    def set_password(self, password: str):
        """Hash and store the password using bcrypt."""
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored bcrypt hash."""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def is_admin(self) -> bool:
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username}>'


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    contract_number = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=True)
    signing_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='draft')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    creator = db.relationship('User', back_populates='contracts')
    attachments = db.relationship('Attachment', back_populates='contract',
                                  cascade='all, delete-orphan', lazy='dynamic')

    VALID_STATUSES = ['draft', 'active', 'completed', 'terminated']

    def __repr__(self):
        return f'<Contract {self.contract_number}>'


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    original_filename = db.Column(db.String(300), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    contract = db.relationship('Contract', back_populates='attachments')

    def is_pdf(self) -> bool:
        return self.original_filename.lower().endswith('.pdf')

    def is_word(self) -> bool:
        lower = self.original_filename.lower()
        return lower.endswith('.doc') or lower.endswith('.docx')

    def size_display(self) -> str:
        """Return human-readable file size."""
        size = self.file_size
        if size < 1024:
            return f'{size} B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f} KB'
        else:
            return f'{size / (1024 * 1024):.1f} MB'

    def __repr__(self):
        return f'<Attachment {self.original_filename}>'
