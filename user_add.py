from werkzeug.security import generate_password_hash

from app import app, db, User
with app.app_context():
    db.create_all()
    user = User(username='admin', password_hash=generate_password_hash('1234'), role='admin')
    db.session.add(user)
    db.session.commit()