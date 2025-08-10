import pytest
import json
from datetime import date, datetime

def test_index_page(client):
    """Test the main search page loads correctly"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Court Case Search' in response.data
    assert b'Case Type' in response.data
    assert b'Case Number' in response.data
    assert b'Filing Year' in response.data

def test_search_missing_parameters(client):
    """Test search with missing parameters"""
    response = client.post('/search', data={
        'case_type': 'civil',
        'case_number': '',  
        'filing_year': '2023'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Please fill in all required fields' in response.data

def test_search_invalid_year(client):
    """Test search with invalid year"""
    response = client.post('/search', data={
        'case_type': 'civil',
        'case_number': '1234',
        'filing_year': '1900'  
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Please enter a valid filing year' in response.data

def test_search_valid_parameters(client):
    """Test search with valid parameters"""
    response = client.post('/search', data={
        'case_type': 'civil',
        'case_number': '1234',
        'filing_year': '2023'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    

def test_stats_page(client):
    """Test the statistics page"""
    response = client.get('/stats')
    assert response.status_code == 200
    assert b'Application Statistics' in response.data
    assert b'Total Cases' in response.data

def test_404_error(client):
    """Test 404 error handling"""
    response = client.get('/nonexistent-page')
    assert response.status_code == 404
    assert b'Page not found' in response.data

def test_api_case_not_found(client):
    """Test API endpoint for non-existent case"""
    response = client.get('/api/case/99999')
    assert response.status_code == 404
    
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Case not found'
