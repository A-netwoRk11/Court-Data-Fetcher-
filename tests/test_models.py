import pytest
import json
from datetime import date, datetime
from models import Case, Document, QueryLog

def test_case_model(app_context):
    """Test Case model functionality"""
    
    case = Case(
        case_type='civil',
        case_number='1234',
        filing_year=2023,
        parties=json.dumps({
            'petitioner': ['John Doe'],
            'respondent': ['Jane Smith']
        }),
        filing_date=date(2023, 3, 15),
        status='Active'
    )
    
    
    assert case.case_title == 'John Doe vs Jane Smith'
    assert case.parties_dict['petitioner'] == ['John Doe']
    assert case.parties_dict['respondent'] == ['Jane Smith']
    
    
    case_dict = case.to_dict()
    assert case_dict['case_type'] == 'civil'
    assert case_dict['case_number'] == '1234'
    assert case_dict['filing_year'] == 2023

def test_document_model(app_context):
    """Test Document model functionality"""
    doc = Document(
        case_id=1,
        document_type='Order',
        document_date=date(2023, 3, 20),
        description='Test order',
        file_size=1024000  
    )
    
    assert doc.file_size_mb == 0.98  
    assert not doc.is_downloaded  
    
    doc.local_path = '/path/to/file.pdf'
    assert doc.is_downloaded

def test_query_log_model(app_context):
    """Test QueryLog model functionality"""
    search_params = {
        'case_type': 'civil',
        'case_number': '1234',
        'filing_year': '2023'
    }
    
    response_data = {
        'success': True,
        'case_found': True
    }
    
    log = QueryLog(
        search_params=json.dumps(search_params),
        response_data=json.dumps(response_data),
        success=True
    )
    
    assert log.search_params_dict == search_params
    assert log.response_data_dict == response_data
    assert log.success is True
