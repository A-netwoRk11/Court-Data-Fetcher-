
"""
Court Data Fetcher - Flask Web Application
Requires Python 3.12
"""

import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from dotenv import load_dotenv
import json
import pymysql


load_dotenv()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///court_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'downloads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 10485760))


from models import db, Case, QueryLog, Document
db.init_app(app)


from services.court_scraper import CourtScraper
from services.pdf_handler import PDFHandler


logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'court_fetcher.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


CASE_TYPES = {
    'civil': 'Civil Cases',
    'criminal': 'Criminal Cases',
    'writ': 'Writ Petitions',
    'company': 'Company Petitions',
    'arbitration': 'Arbitration Petitions',
    'matrimonial': 'Matrimonial Cases',
    'tax': 'Tax Cases',
    'motor_accident': 'Motor Accident Claims',
    'rent': 'Rent Control Cases',
    'labor': 'Labour Cases'
}

@app.route('/')
def index():
    """Main search interface"""
    return render_template('index.html', case_types=CASE_TYPES)

@app.route('/search', methods=['POST'])
def search_case():
    """Handle case search submission"""
    try:
        
        case_type = request.form.get('case_type')
        case_number = request.form.get('case_number')
        filing_year = request.form.get('filing_year')
        
        
        if not all([case_type, case_number, filing_year]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('index'))
        
        
        try:
            year = int(filing_year)
            if year < 1950 or year > datetime.now().year:
                flash('Please enter a valid filing year.', 'error')
                return redirect(url_for('index'))
        except ValueError:
            flash('Please enter a valid filing year.', 'error')
            return redirect(url_for('index'))
        
        
        search_params = {
            'case_type': case_type,
            'case_number': case_number,
            'filing_year': filing_year,
            'timestamp': datetime.now().isoformat()
        }
        
        
        scraper = CourtScraper()
        
        
        existing_case = Case.query.filter_by(
            case_type=case_type,
            case_number=case_number,
            filing_year=year
        ).first()
        
        if existing_case:
            logger.info(f"Case found in database: {case_type}/{case_number}/{filing_year}")
            
            query_log = QueryLog(
                search_params=json.dumps(search_params),
                response_data=json.dumps({'source': 'database'}),
                success=True,
                timestamp=datetime.now()
            )
            db.session.add(query_log)
            db.session.commit()
            
            return render_template('case_details.html', case=existing_case)
        
        
        logger.info(f"Searching court website for: {case_type}/{case_number}/{filing_year}")
        case_data = scraper.search_case(case_type, case_number, filing_year)
        
        if case_data.get('success'):
            
            case = Case(
                case_type=case_type,
                case_number=case_number,
                filing_year=year,
                parties=json.dumps(case_data.get('parties', {})),
                filing_date=case_data.get('filing_date'),
                next_hearing_date=case_data.get('next_hearing_date'),
                status=case_data.get('status', 'Unknown'),
                raw_data=json.dumps(case_data),
                created_at=datetime.now()
            )
            db.session.add(case)
            db.session.flush()  
            
            
            for doc_data in case_data.get('documents', []):
                document = Document(
                    case_id=case.id,
                    document_type=doc_data.get('type', 'Unknown'),
                    document_date=doc_data.get('date'),
                    pdf_url=doc_data.get('url'),
                    description=doc_data.get('description', '')
                )
                db.session.add(document)
            
            
            query_log = QueryLog(
                search_params=json.dumps(search_params),
                response_data=json.dumps(case_data),
                success=True,
                timestamp=datetime.now()
            )
            db.session.add(query_log)
            db.session.commit()
            
            logger.info(f"Case saved successfully: {case.id}")
            flash('Case information retrieved successfully!', 'success')
            return render_template('case_details.html', case=case)
        
        else:
            
            error_message = case_data.get('error', 'Unknown error occurred')
            query_log = QueryLog(
                search_params=json.dumps(search_params),
                response_data=json.dumps(case_data),
                success=False,
                error_message=error_message,
                timestamp=datetime.now()
            )
            db.session.add(query_log)
            db.session.commit()
            
            logger.warning(f"Case search failed: {error_message}")
            
            
            if 'case not found' in error_message.lower():
                flash(f'Unable to find case: {case_type}/{case_number}/{filing_year}. Please verify the case details and try again.', 'error')
                
                
                case_format_tips = {
                    'tax': 'For TAX cases, try adding a prefix like ITXA, TA, ITA, or ITAT before the case number. For example: "ITXA 789" instead of just "789".',
                    'criminal': 'For CRIMINAL cases, try adding a prefix like CRL, CRL.A., or CRL.M.C. before the case number. For example: "CRL 1890" instead of just "1890".',
                    'writ': 'For WRIT cases, try using formats like W.P.(C) or W.P.(CRL) before the case number. For example: "W.P.(C) 123" instead of just "123".',
                    'civil': 'For CIVIL cases, try adding a prefix like CS, C.S., or CIVIL SUIT before the case number. For example: "CS 456" instead of just "456".',
                    'company': 'For COMPANY cases, try adding a prefix like CO or CO. before the case number. For example: "CO 789" instead of just "789".',
                    'arbitration': 'For ARBITRATION cases, try adding a prefix like ARB, ARB.A., or ARB.P. before the case number.',
                    'matrimonial': 'For MATRIMONIAL cases, try adding a prefix like MAT or MAT.A. before the case number.',
                    'motor_accident': 'For MOTOR ACCIDENT cases, try adding a prefix like MAC or MAC.APP. before the case number.',
                    'rent': 'For RENT cases, try adding a prefix like RC or R.C.REV. before the case number.',
                    'labor': 'For LABOR cases, try adding a prefix like LPA or LC before the case number.'
                }
                
                
                if case_type.lower() in case_format_tips:
                    flash(case_format_tips[case_type.lower()], 'info')
                
                
                flash('You can also try different spacing or formats (with/without spaces, with hyphens, etc).', 'info')
                flash('Note: Some cases may not be available in the public database or might require a specific format.', 'info')
            else:
                flash(f'Error retrieving case: {error_message}', 'error')
                
            return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Error in search_case: {str(e)}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/case/<int:case_id>')
def view_case(case_id):
    """View specific case details"""
    case = Case.query.get_or_404(case_id)
    return render_template('case_details.html', case=case)

@app.route('/download/<int:document_id>')
def download_document(document_id):
    """Download PDF document"""
    try:
        document = Document.query.get_or_404(document_id)
        
        
        pdf_handler = PDFHandler()
        
        
        file_path = pdf_handler.download_pdf(document.pdf_url, document_id)
        
        if file_path and os.path.exists(file_path):
            
            document.local_path = file_path
            document.file_size = os.path.getsize(file_path)
            db.session.commit()
            
            return send_file(
                file_path,
                as_attachment=True,
                download_name=f"document_{document_id}.pdf",
                mimetype='application/pdf'
            )
        else:
            flash('Unable to download document. Please try again later.', 'error')
            return redirect(request.referrer or url_for('index'))
    
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        flash('Error downloading document.', 'error')
        return redirect(request.referrer or url_for('index'))

@app.route('/api/case/<case_number>')
def api_case(case_number):
    """JSON API for case data"""
    try:
        
        case = Case.query.filter_by(case_number=case_number).order_by(Case.created_at.desc()).first()
        
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        
        case_data = {
            'id': case.id,
            'case_type': case.case_type,
            'case_number': case.case_number,
            'filing_year': case.filing_year,
            'parties': json.loads(case.parties) if case.parties else {},
            'filing_date': case.filing_date.isoformat() if case.filing_date else None,
            'next_hearing_date': case.next_hearing_date.isoformat() if case.next_hearing_date else None,
            'status': case.status,
            'documents': [
                {
                    'id': doc.id,
                    'type': doc.document_type,
                    'date': doc.document_date.isoformat() if doc.document_date else None,
                    'description': doc.description,
                    'download_url': url_for('download_document', document_id=doc.id, _external=True)
                }
                for doc in case.documents
            ],
            'created_at': case.created_at.isoformat()
        }
        
        return jsonify(case_data)
    
    except Exception as e:
        logger.error(f"Error in API case lookup: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/stats')
def stats():
    """Application statistics"""
    try:
        total_cases = Case.query.count()
        total_queries = QueryLog.query.count()
        successful_queries = QueryLog.query.filter_by(success=True).count()
        total_documents = Document.query.count()
        
        case_types_stats = db.session.query(
            Case.case_type,
            db.func.count(Case.id).label('count')
        ).group_by(Case.case_type).all()
        
        stats_data = {
            'total_cases': total_cases,
            'total_queries': total_queries,
            'successful_queries': successful_queries,
            'success_rate': round((successful_queries / total_queries * 100) if total_queries > 0 else 0, 2),
            'total_documents': total_documents,
            'case_types': [{'type': ct[0], 'count': ct[1]} for ct in case_types_stats]
        }
        
        return render_template('stats.html', stats=stats_data)
    
    except Exception as e:
        logger.error(f"Error generating stats: {str(e)}")
        flash('Error loading statistics.', 'error')
        return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error='Internal server error'), 500

if __name__ == '__main__':
    
    with app.app_context():
        db.create_all()
    
    
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )
