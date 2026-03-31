from database import SessionLocal
from models import User
import bcrypt

db = SessionLocal()
u = db.query(User).filter(User.username == 'admin').first()
if u:
    print(f"User: {u.username}")
    print(f"Hash: {u.hashed_password[:50]}...")
    valid = bcrypt.checkpw(b"admin123", u.hashed_password.encode())
    print(f"Password valid: {valid}")
else:
    print("No user found")
db.close()