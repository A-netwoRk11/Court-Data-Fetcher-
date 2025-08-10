
"""
Database initialization script for Court Data Fetcher
"""

import os
import sys
from dotenv import load_dotenv


load_dotenv()


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from app import app
from models import db

def init_database():
    """Initialize the database with all tables"""
    try:
        with app.app_context():
            
            print("Dropping existing tables...")
            db.drop_all()
            
            
            print("Creating database tables...")
            db.create_all()
            
            print("Database initialized successfully!")
            
            
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"\nCreated tables:")
            for table in tables:
                columns = inspector.get_columns(table)
                print(f"  - {table} ({len(columns)} columns)")
                for column in columns:
                    print(f"    • {column['name']} ({column['type']})")
                print()
            
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        sys.exit(1)

def create_sample_data():
    """Create sample data for testing"""
    try:
        from models import Case, Document, QueryLog
        from datetime import datetime, date
        import json
        
        with app.app_context():
            
            existing_cases = Case.query.count()
            if existing_cases > 0:
                print(f"Database already contains {existing_cases} cases. Skipping sample data creation.")
                return
            
            print("Creating sample data...")
            
            
            case1 = Case(
                case_type='civil',
                case_number='1234',
                filing_year=2023,
                parties=json.dumps({
                    'petitioner': ['John Doe', 'ABC Corporation'],
                    'respondent': ['Jane Smith', 'XYZ Ltd.']
                }),
                filing_date=date(2023, 3, 15),
                next_hearing_date=date(2024, 2, 10),
                status='Listed for Hearing',
                raw_data=json.dumps({'source': 'sample_data'}),
                created_at=datetime.now()
            )
            db.session.add(case1)
            db.session.flush()
            
            
            doc1 = Document(
                case_id=case1.id,
                document_type='Order',
                document_date=date(2023, 3, 20),
                description='Interim Order dated 20/03/2023',
                pdf_url='https://example.com/sample_order_1.pdf',
                created_at=datetime.now()
            )
            doc2 = Document(
                case_id=case1.id,
                document_type='Notice',
                document_date=date(2023, 3, 22),
                description='Notice to Respondent',
                pdf_url='https://example.com/sample_notice_1.pdf',
                created_at=datetime.now()
            )
            db.session.add_all([doc1, doc2])
            
            
            case2 = Case(
                case_type='criminal',
                case_number='5678',
                filing_year=2024,
                parties=json.dumps({
                    'petitioner': ['State of Delhi'],
                    'respondent': ['Accused Person']
                }),
                filing_date=date(2024, 1, 10),
                next_hearing_date=date(2024, 3, 15),
                status='Under Trial',
                raw_data=json.dumps({'source': 'sample_data'}),
                created_at=datetime.now()
            )
            db.session.add(case2)
            db.session.flush()
            
            
            doc3 = Document(
                case_id=case2.id,
                document_type='Charge Sheet',
                document_date=date(2024, 1, 15),
                description='Charge Sheet filed by Police',
                pdf_url='https://example.com/sample_chargesheet.pdf',
                created_at=datetime.now()
            )
            db.session.add(doc3)
            
            
            case3 = Case(
                case_type='writ',
                case_number='9012',
                filing_year=2024,
                parties=json.dumps({
                    'petitioner': ['Citizen Petitioner'],
                    'respondent': ['Government of Delhi', 'Union of India']
                }),
                filing_date=date(2024, 1, 5),
                next_hearing_date=date(2024, 2, 28),
                status='Admitted',
                raw_data=json.dumps({'source': 'sample_data'}),
                created_at=datetime.now()
            )
            db.session.add(case3)
            db.session.flush()
            
            
            doc4 = Document(
                case_id=case3.id,
                document_type='Petition',
                document_date=date(2024, 1, 5),
                description='Writ Petition under Article 226',
                pdf_url='https://example.com/sample_writ_petition.pdf',
                created_at=datetime.now()
            )
            doc5 = Document(
                case_id=case3.id,
                document_type='Order',
                document_date=date(2024, 1, 20),
                description='Order admitting the petition',
                pdf_url='https://example.com/sample_admission_order.pdf',
                created_at=datetime.now()
            )
            db.session.add_all([doc4, doc5])
            
            
            log1 = QueryLog(
                search_params=json.dumps({
                    'case_type': 'civil',
                    'case_number': '1234',
                    'filing_year': '2023'
                }),
                response_data=json.dumps({'success': True, 'source': 'sample'}),
                success=True,
                timestamp=datetime.now()
            )
            
            log2 = QueryLog(
                search_params=json.dumps({
                    'case_type': 'criminal',
                    'case_number': '9999',
                    'filing_year': '2024'
                }),
                response_data=json.dumps({'success': False}),
                success=False,
                error_message='Case not found',
                timestamp=datetime.now()
            )
            
            db.session.add_all([log1, log2])
            
            
            db.session.commit()
            
            print("Sample data created successfully!")
            print(f"Created {Case.query.count()} cases")
            print(f"Created {Document.query.count()} documents")
            print(f"Created {QueryLog.query.count()} query logs")
            
    except Exception as e:
        print(f"Error creating sample data: {str(e)}")
        db.session.rollback()

def main():
    """Main function"""
    print("Court Data Fetcher - Database Initialization")
    print("=" * 50)
    
    
    init_database()
    
    
    while True:
        choice = input("\nWould you like to create sample data? (y/n): ").lower().strip()
        if choice in ['y', 'yes']:
            create_sample_data()
            break
        elif choice in ['n', 'no']:
            print("Skipping sample data creation.")
            break
        else:
            print("Please enter 'y' for yes or 'n' for no.")
    
    print("\nDatabase setup complete!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the application: python app.py")
    print("3. Open your browser to: http://localhost:5000")

if __name__ == '__main__':
    main()
