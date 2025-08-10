import pytest
import tempfile
import os
from dotenv import load_dotenv
from app import app, db


load_dotenv()

@pytest.fixture
def client():
    """Create a test client with temporary database"""
    db_fd, app.config['DATABASE'] = tempfile.mkstemp()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'mysql://root:password@127.0.0.1/test_court_data')
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        
    os.close(db_fd)
    os.unlink(app.config['DATABASE'])

@pytest.fixture
def app_context():
    """Create application context for testing"""
    with app.app_context():
        yield app
