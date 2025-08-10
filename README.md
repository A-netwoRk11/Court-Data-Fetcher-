# Court-Data Fetcher & Mini-Dashboard

## Overview
A web application that allows users to search and retrieve case information from the Delhi High Court's public portal. The app provides a simple interface to query case details, display metadata, and access order/judgment documents.

## Court Chosen
**Delhi High Court** (https://delhihighcourt.nic.in/)

This court was selected because:
- It has a publicly accessible case search interface
- Provides comprehensive case information including orders and judgments
- Has a relatively stable structure for web scraping
- Offers downloadable PDF documents for orders/judgments

## Features
- 🔍 Search cases by Case Type, Case Number, and Filing Year
- 📋 Display case metadata (parties, filing dates, hearing dates)
- 📄 View and download order/judgment PDFs
- 💾 Automatic logging of all queries and responses
- 🚫 User-friendly error handling for invalid cases or site issues
- 📱 Responsive web interface

## Technology Stack
- **Backend**: Python Flask
- **Database**: MySQL
- **Web Scraping**: Requests + BeautifulSoup4 + Selenium (for CAPTCHA handling)
- **Frontend**: HTML5, Bootstrap CSS, JavaScript
- **PDF Handling**: PyPDF2 for PDF validation
- **Environment**: python-dotenv for configuration

## CAPTCHA Strategy
The Delhi High Court website uses various anti-bot measures:

1. **Session Management**: Maintains session cookies across requests
2. **User-Agent Rotation**: Uses realistic browser headers
3. **Request Throttling**: Implements delays between requests
4. **Selenium Fallback**: For complex JavaScript-rendered content
5. **Manual Override**: Provides option for manual CAPTCHA solving when needed

## Installation & Setup

### Prerequisites
- Python 3.12
- pip package manager
- Chrome/Chromium browser (for Selenium)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd court-data-fetcher
   ```

2. **Quick Start (Recommended)**
   
   **Windows:**
   ```cmd
   # Double-click start.bat or run:
   start.bat
   ```
   
   **Linux/Mac:**
   ```bash
   # Make executable and run:
   chmod +x start.sh
   ./start.sh
   ```
   
   **Python (All platforms):**
   ```bash
   python run.py
   ```

3. **Manual Installation**

   **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

   **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file with your configuration:
   ```
   FLASK_ENV=development
   FLASK_DEBUG=True
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=mysql://root:password@mysql/court_data
   CHROME_DRIVER_PATH=/path/to/chromedriver
   ```

   **Initialize the database**
   ```bash
   python init_db.py
   ```

   **Run the application**
   ```bash
   python app.py
   ```

4. **Docker Installation (Optional)**
   ```bash
   # Build and run with Docker
   docker build -t court-data-fetcher .
   docker run -p 5000:5000 court-data-fetcher
   
   # Or use Docker Compose
   docker-compose up -d
   ```

The application will be available at `http://localhost:5000`

## Usage

1. **Access the web interface** at `http://localhost:5000`
2. **Select Case Type** from the dropdown (e.g., Civil, Criminal, Writ Petition)
3. **Enter Case Number** and **Filing Year**
4. **Submit the search** to fetch case details
5. **View results** including:
   - Case parties and their advocates
   - Filing and next hearing dates
   - Available orders and judgments
   - Download links for PDF documents

## API Endpoints

- `GET /` - Main search interface
- `POST /search` - Submit case search
- `GET /case/<case_id>` - View specific case details
- `GET /download/<file_id>` - Download PDF documents
- `GET /api/case/<case_number>` - JSON API for case data

## Database Schema

### Cases Table
- `id` - Primary key
- `case_type` - Type of case
- `case_number` - Case number
- `filing_year` - Year of filing
- `parties` - JSON field with petitioner/respondent details
- `filing_date` - Date case was filed
- `next_hearing_date` - Next scheduled hearing
- `status` - Current case status
- `created_at` - Record creation timestamp

### Query_Logs Table
- `id` - Primary key
- `search_params` - JSON of search parameters
- `response_data` - Raw scraped data
- `success` - Whether scraping was successful
- `error_message` - Error details if failed
- `timestamp` - Query timestamp

### Documents Table
- `id` - Primary key
- `case_id` - Foreign key to cases
- `document_type` - Order/Judgment/Other
- `document_date` - Date of document
- `pdf_url` - URL to PDF file
- `local_path` - Local storage path
- `file_size` - Size in bytes

## Error Handling

- **Invalid Case Numbers**: Clear message when case not found
- **Site Downtime**: Graceful handling with retry mechanism
- **CAPTCHA Blocks**: Fallback options and user guidance
- **PDF Download Failures**: Alternative access methods
- **Database Errors**: Transaction rollback and user notification

## Security Considerations

- No hardcoded credentials or API keys
- Input validation and sanitization
- SQL injection prevention using parameterized queries
- Rate limiting to prevent abuse
- Secure session management
- HTTPS enforcement in production

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Code Formatting
```bash
black src/
flake8 src/
```

### Database Migrations
```bash
python manage.py migrate
```

## Deployment

### Docker (Optional)
```bash
docker build -t court-data-fetcher .
docker run -p 5000:5000 court-data-fetcher
```

### Environment Variables for Production
```
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=mysql://user:pass@host:port/dbname
SECRET_KEY=production-secret-key
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is designed for accessing publicly available court information only. Users must comply with the terms of service of the court websites and applicable laws regarding web scraping and data usage.

## Support

For issues or questions, please open an issue on GitHub or contact the development team.

---

**Note**: This is a demonstration project for educational purposes. Ensure compliance with all applicable laws and website terms of service when using this tool.
