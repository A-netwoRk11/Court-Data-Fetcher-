from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import pymysql


db = SQLAlchemy()

class Case(db.Model):
    """Model for storing case information"""
    __tablename__ = 'cases'
    
    id = db.Column(db.Integer, primary_key=True)
    case_type = db.Column(db.String(50), nullable=False)
    case_number = db.Column(db.String(100), nullable=False)
    filing_year = db.Column(db.Integer, nullable=False)
    parties = db.Column(db.Text)  
    filing_date = db.Column(db.Date)
    next_hearing_date = db.Column(db.Date)
    status = db.Column(db.String(100))
    raw_data = db.Column(db.Text)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    
    documents = db.relationship('Document', backref='case', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Case {self.case_type}/{self.case_number}/{self.filing_year}>'
    
    @property
    def parties_dict(self):
        """Parse parties JSON string to dictionary"""
        if self.parties:
            try:
                return json.loads(self.parties)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @property
    def case_title(self):
        """Generate case title from parties"""
        parties = self.parties_dict
        if parties:
            petitioner = parties.get('petitioner', ['Unknown'])
            respondent = parties.get('respondent', ['Unknown'])
            if isinstance(petitioner, list) and petitioner:
                petitioner = petitioner[0]
            if isinstance(respondent, list) and respondent:
                respondent = respondent[0]
            return f"{petitioner} vs {respondent}"
        return f"Case {self.case_number}/{self.filing_year}"
    
    def to_dict(self):
        """Convert case to dictionary"""
        return {
            'id': self.id,
            'case_type': self.case_type,
            'case_number': self.case_number,
            'filing_year': self.filing_year,
            'parties': self.parties_dict,
            'filing_date': self.filing_date.isoformat() if self.filing_date else None,
            'next_hearing_date': self.next_hearing_date.isoformat() if self.next_hearing_date else None,
            'status': self.status,
            'case_title': self.case_title,
            'document_count': len(self.documents),
            'created_at': self.created_at.isoformat()
        }

class QueryLog(db.Model):
    """Model for logging search queries and responses"""
    __tablename__ = 'query_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    search_params = db.Column(db.Text, nullable=False)  
    response_data = db.Column(db.Text)  
    success = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))  
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<QueryLog {self.id} - {"Success" if self.success else "Failed"}>'
    
    @property
    def search_params_dict(self):
        """Parse search params JSON string to dictionary"""
        if self.search_params:
            try:
                return json.loads(self.search_params)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @property
    def response_data_dict(self):
        """Parse response data JSON string to dictionary"""
        if self.response_data:
            try:
                return json.loads(self.response_data)
            except json.JSONDecodeError:
                return {}
        return {}

class Document(db.Model):
    """Model for storing document information"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)  
    document_date = db.Column(db.Date)
    description = db.Column(db.Text)
    pdf_url = db.Column(db.Text)  
    local_path = db.Column(db.String(500))  
    file_size = db.Column(db.Integer)  
    checksum = db.Column(db.String(64))  
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Document {self.id} - {self.document_type}>'
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0
    
    @property
    def is_downloaded(self):
        """Check if document is downloaded locally"""
        return bool(self.local_path and self.file_size)
    
    def to_dict(self):
        """Convert document to dictionary"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'document_type': self.document_type,
            'document_date': self.document_date.isoformat() if self.document_date else None,
            'description': self.description,
            'file_size_mb': self.file_size_mb,
            'is_downloaded': self.is_downloaded,
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat()
        }
