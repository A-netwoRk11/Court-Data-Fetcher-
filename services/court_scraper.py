import os
import time
import logging
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class CourtScraper:
    """
    Service for scraping Delhi High Court website
    Handles session management, CAPTCHA challenges, and data extraction
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://delhihighcourt.nic.in"
        
        self.search_url = f"{self.base_url}/dhc/case-status"
        self.direct_case_url = f"{self.base_url}/home/caseinfo"
        
        
        self.user_agent = os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        self.request_delay = int(os.getenv('REQUEST_DELAY', '1'))  
        self.max_retries = int(os.getenv('MAX_RETRIES', '2'))      
        self.chrome_headless = os.getenv('CHROME_HEADLESS', 'True').lower() == 'true'
        self.max_threads = int(os.getenv('MAX_THREADS', '3'))      
        
        
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',  
            'Pragma': 'no-cache',
        })
        
        
        self.driver_pool = []
        self.driver_pool_lock = threading.Lock()
        self.pool_executor = ThreadPoolExecutor(max_workers=self.max_threads)
    
    def _init_selenium_driver(self):
        """Initialize Selenium Chrome driver for complex interactions"""
        try:
            chrome_options = Options()
            if self.chrome_headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={self.user_agent}')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-infobars')
            
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.implicitly_wait(5)  
            
            logger.info("Selenium Chrome driver initialized successfully")
            return driver
            
        except Exception as e:
            logger.error(f"Failed to initialize Selenium driver: {str(e)}")
            return None
    
    def _get_driver(self):
        """Get a driver from the pool or create a new one"""
        with self.driver_pool_lock:
            if self.driver_pool:
                return self.driver_pool.pop()
            else:
                return self._init_selenium_driver()
    
    def _return_driver(self, driver):
        """Return a driver to the pool"""
        if driver:
            with self.driver_pool_lock:
                if len(self.driver_pool) < self.max_threads:
                    self.driver_pool.append(driver)
                else:
                    try:
                        driver.quit()
                    except:
                        pass
    
    def _cleanup_selenium(self):
        """Clean up all Selenium drivers in the pool"""
        with self.driver_pool_lock:
            for driver in self.driver_pool:
                try:
                    driver.quit()
                except:
                    pass
            self.driver_pool.clear()
    
    def _direct_case_search(self, case_type, case_number, filing_year):
        """
        Attempt direct search using Delhi High Court's direct case info URL
        This is faster than the form-based search
        """
        try:
            
            type_map = {
                'CIVIL': 'CS',
                'CRIMINAL': 'CRL',
                'WRIT': 'WP',
                'COMPANY': 'CO',
                'ARBITRATION': 'ARB',
                'TAX': 'ITA',
                'MATRIMONIAL': 'MAT',
                'MOTOR_ACCIDENT': 'MAC',
                'RENT': 'RC',
                'LABOR': 'LPA'
            }
            
            normalized_type = case_type.upper()
            search_type = type_map.get(normalized_type, normalized_type)
            
            
            direct_url = f"{self.direct_case_url}?case_no={search_type}+{case_number}/{filing_year}"
            logger.info(f"Attempting direct case search: {direct_url}")
            
            response = self.session.get(direct_url, timeout=10)
            if response.status_code == 200:
                
                soup = BeautifulSoup(response.content, 'html.parser')
                if "Case Details" in soup.get_text():
                    logger.info("Found case via direct search")
                    return self._parse_case_results(response.content, case_type, case_number, filing_year)
            
            return None
            
        except Exception as e:
            logger.error(f"Error in direct case search: {str(e)}")
            return None
    
    def _get_search_suggestions(self, case_type, case_number, filing_year):
        """Generate helpful search suggestions based on the case details"""
        suggestions = []
        
        
        case_type_upper = case_type.upper()
        if case_type_upper == 'TAX':
            suggestions.append("Try adding a prefix like 'ITXA', 'ITA', or 'TA' before the case number")
        elif case_type_upper == 'CRIMINAL':
            suggestions.append("Try adding a prefix like 'CRL', 'CRL.A.' or 'CRL.M.C.' before the case number")
        elif case_type_upper == 'WRIT':
            suggestions.append("Try using formats like 'W.P.(C)' or 'W.P.' before the case number")
        
        
        if case_number.isdigit():
            suggestions.append("Verify the case number is correct")
            suggestions.append("Try adding a prefix specific to the case type")
        else:
            suggestions.append("Check if the case number format is correct")
        
        suggestions.append("Make sure you've selected the correct case type")
        suggestions.append("Verify the filing year is accurate")
        
        return suggestions
    
    def search_case(self, case_type, case_number, filing_year):
        """
        Search for a case on Delhi High Court website using direct and fast method
        
        Args:
            case_type (str): Type of case (civil, criminal, writ, etc.)
            case_number (str): Case number
            filing_year (str): Filing year
            
        Returns:
            dict: Case data or error information
        """
        try:
            
            if not case_type or not case_number or not filing_year:
                return {
                    'success': False,
                    'error': "Missing required parameters. Please provide case type, case number, and filing year.",
                    'case_type': case_type,
                    'case_number': case_number,
                    'filing_year': filing_year
                }
            
            
            try:
                year_int = int(filing_year)
                current_year = datetime.now().year
                if year_int < 1950 or year_int > current_year:
                    return {
                        'success': False,
                        'error': f"Invalid filing year. Must be between 1950 and {current_year}.",
                        'case_type': case_type,
                        'case_number': case_number,
                        'filing_year': filing_year
                    }
            except ValueError:
                return {
                    'success': False,
                    'error': "Filing year must be a valid number.",
                    'case_type': case_type,
                    'case_number': case_number,
                    'filing_year': filing_year
                }
                
            logger.info(f"Starting case search: {case_type}/{case_number}/{filing_year}")
            
            
            case_prefixes = {
                'TAX': ['ITXA', 'TA', 'ITA', 'ITAT', 'TAX'],
                'CRIMINAL': ['CRL', 'CRL.A.', 'CRL.M.C.', 'CRL.REV.P.', 'CRIMINAL'],
                'CIVIL': ['CS', 'C.S.', 'CIVIL', 'CIVIL SUIT'],
                'WRIT': ['W.P.', 'W.P.(C)', 'W.P.(CRL)', 'WRIT'],
                'COMPANY': ['CO', 'CO.', 'COMPANY', 'CP'],
                'ARBITRATION': ['ARB', 'ARB.P.', 'ARB.A.'],
                'MATRIMONIAL': ['MAT', 'MAT.A.'],
                'MOTOR_ACCIDENT': ['MAC', 'MAC.APP.'],
                'RENT': ['RC', 'R.C.REV.'],
                'LABOR': ['LPA', 'LAB']
            }
            
            
            search_variations = []
            
            
            search_variations.append({"type": case_type, "number": case_number, "year": filing_year})
            
            
            normalized_type = case_type.upper()
            prefixes = case_prefixes.get(normalized_type, [])
            
            
            has_prefix = False
            if prefixes:
                has_prefix = any(case_number.upper().startswith(prefix) for prefix in prefixes)
            
            if prefixes and not has_prefix and case_number.isdigit():
                
                search_variations.append({"type": case_type, "number": f"{prefixes[0]} {case_number}", "year": filing_year})
            
            
            direct_result = self._direct_case_search(case_type, case_number, filing_year)
            if direct_result and direct_result.get('success'):
                return direct_result
                
            
            results = []
            futures = []
            
            
            for variation in search_variations:
                futures.append(self.pool_executor.submit(
                    self._search_with_selenium, 
                    variation["type"], 
                    variation["number"], 
                    variation["year"]
                ))
            
            
            for future in futures:
                result = future.result()
                if result and result.get('success'):
                    
                    return result
                results.append(result)
            
            
            if normalized_type in case_prefixes and not has_prefix:
                
                for prefix in case_prefixes[normalized_type][1:2]:  
                    alt_number = f"{prefix} {case_number}"
                    logger.info(f"Trying alternative format: {alt_number}")
                    alt_result = self._search_with_selenium(case_type, alt_number, filing_year)
                    if alt_result and alt_result.get('success'):
                        return alt_result
                
            
            logger.warning(f"No case found for {case_type}/{case_number}/{filing_year}")
            
            
            return {
                'success': False,
                'error': "Case not found. Please verify the case type, case number, and filing year are correct.",
                'case_type': case_type,
                'case_number': case_number,
                'filing_year': filing_year,
                'suggestions': self._get_search_suggestions(case_type, case_number, filing_year)
            }
            
        except Exception as e:
            logger.error(f"Error in case search: {str(e)}")
            return {
                'success': False,
                'error': f"Search failed: {str(e)}",
                'case_type': case_type,
                'case_number': case_number,
                'filing_year': filing_year
            }
    
    def _search_with_requests(self, case_type, case_number, filing_year):
        """Search using requests and BeautifulSoup"""
        try:
            
            time.sleep(self.request_delay)
            
            
            retries = 0
            max_retries = self.max_retries
            
            while retries < max_retries:
                try:
                    
                    response = self.session.get(self.search_url, timeout=30)
                    response.raise_for_status()
                    break
                except (requests.ConnectionError, requests.Timeout) as e:
                    retries += 1
                    if retries >= max_retries:
                        raise
                    logger.warning(f"Connection issue, retrying ({retries}/{max_retries}): {str(e)}")
                    time.sleep(self.request_delay * retries)  
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            
            search_form = soup.find('form')
            if not search_form:
                return {
                    'success': False,
                    'error': 'Could not find search form on the website'
                }
            
            
            form_data = self._extract_form_data(soup, case_type, case_number, filing_year)
            
            if not form_data:
                return {
                    'success': False,
                    'error': 'Could not extract form data'
                }
            
            
            time.sleep(self.request_delay)
            search_response = self.session.post(
                self.search_url,
                data=form_data,
                timeout=30,
                allow_redirects=True
            )
            
            search_response.raise_for_status()
            
            
            return self._parse_case_results(search_response.content, case_type, case_number, filing_year)
            
        except requests.RequestException as e:
            logger.error(f"Request error in _search_with_requests: {str(e)}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error in _search_with_requests: {str(e)}")
            return {
                'success': False,
                'error': f"Parsing error: {str(e)}"
            }
    
    def _search_with_selenium(self, case_type, case_number, filing_year):
        """Search using Selenium WebDriver with improved speed and reliability"""
        driver = None
        try:
            
            driver = self._get_driver()
            if not driver:
                return {
                    'success': False,
                    'error': 'Could not initialize browser driver'
                }
            
            
            driver.get(self.search_url)
            
            
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "form"))
                )
            except:
                logger.warning("Timeout waiting for search form to load")
            
            
            if not self._fill_search_form_selenium(driver, case_type, case_number, filing_year):
                return {
                    'success': False,
                    'error': f'Could not fill search form for {case_type}/{case_number}/{filing_year}'
                }
            
            
            submitted = False
            
            
            try:
                
                submit_buttons = driver.find_elements(By.XPATH, 
                    "//input[@type='submit'] | //button[@type='submit'] | //input[@value='Submit'] | "
                    "//input[@value='Search'] | //button[contains(text(), 'Search')]")
                
                if submit_buttons:
                    submit_buttons[0].click()
                    submitted = True
                    logger.info("Clicked submit button")
            except Exception as e:
                logger.warning(f"Could not click submit button: {e}")
            
            
            if not submitted:
                try:
                    form = driver.find_element(By.TAG_NAME, "form")
                    form.submit()
                    submitted = True
                    logger.info("Submitted form directly")
                except Exception as e:
                    logger.warning(f"Could not submit form: {e}")
            
            
            if not submitted:
                try:
                    driver.execute_script("document.forms[0].submit();")
                    submitted = True
                    logger.info("Submitted form via JavaScript")
                except Exception as e:
                    logger.warning(f"Could not submit form via JavaScript: {e}")
            
            if not submitted:
                return {
                    'success': False,
                    'error': 'Could not submit search form'
                }
            
            
            result_found = False
            try:
                
                WebDriverWait(driver, 8).until(
                    lambda d: (len(d.find_elements(By.TAG_NAME, 'table')) > 0) or
                             ('no record found' in d.page_source.lower()) or
                             ('no records found' in d.page_source.lower()) or
                             ('not found' in d.page_source.lower())
                )
                result_found = True
            except:
                logger.warning("Timeout waiting for search results")
                
                
                if driver.page_source and 'captcha' in driver.page_source.lower():
                    return {
                        'success': False,
                        'error': "CAPTCHA detected. Please try again later."
                    }
            
            
            page_source = driver.page_source
            
            
            if logger.getEffectiveLevel() <= logging.DEBUG:
                try:
                    screenshot_path = os.path.join('downloads', f'results_{case_type}_{case_number}_{int(time.time())}.png')
                    driver.save_screenshot(screenshot_path)
                    logger.debug(f"Results screenshot saved to {screenshot_path}")
                except:
                    pass
            
            
            result = self._parse_case_results(page_source.encode('utf-8'), case_type, case_number, filing_year)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _search_with_selenium: {str(e)}")
            return {
                'success': False,
                'error': f"Browser automation error: {str(e)}"
            }
        finally:
            
            if driver:
                self._return_driver(driver)
    
    def _extract_form_data(self, soup, case_type, case_number, filing_year):
        """Extract form data including hidden fields and tokens"""
        try:
            form_data = {}
            
            
            inputs = soup.find_all('input')
            for input_field in inputs:
                name = input_field.get('name')
                value = input_field.get('value', '')
                if name:
                    form_data[name] = value
            
            
            selects = soup.find_all('select')
            for select in selects:
                name = select.get('name')
                if name:
                    form_data[name] = ''
            
            
            case_type_mapping = {
                'civil': 'CIVIL',
                'criminal': 'CRIMINAL', 
                'writ': 'W.P.',
                'company': 'COMPANY',
                'arbitration': 'ARB.A.',
                'matrimonial': 'MAT.A.',
                'tax': 'TAX',
                'motor_accident': 'MAC.APP.',
                'rent': 'R.C.REV.',
                'labor': 'LPA',
                
                'crl': 'CRIMINAL',
                'crl.': 'CRIMINAL',
                'crl.a.': 'CRIMINAL',
                'wp': 'W.P.',
                'w.p.': 'W.P.'
            }
            
            
            clean_case_number = case_number.strip()
            
            
            form_field_names = {
                'case_type': None,
                'case_no': None,
                'year': None,
                'submit': None
            }
            
            
            form = soup.find('form')
            if form:
                selects = form.find_all('select')
                for select in selects:
                    name = select.get('name')
                    id = select.get('id')
                    if name and ('type' in name.lower() or 'type' in id.lower()):
                        form_field_names['case_type'] = name
                    elif name and ('year' in name.lower() or 'year' in id.lower()):
                        form_field_names['year'] = name
                
                inputs = form.find_all('input')
                for input_field in inputs:
                    name = input_field.get('name')
                    id = input_field.get('id')
                    if name and ('case' in name.lower() and 'no' in name.lower() or 'number' in name.lower()):
                        form_field_names['case_no'] = name
                    elif name and ('submit' in name.lower() or input_field.get('type') == 'submit'):
                        form_field_names['submit'] = name
            
            
            form_data.update({
                form_field_names.get('case_type', 'case_type'): case_type_mapping.get(case_type.lower(), case_type.upper()),
                form_field_names.get('case_no', 'case_no'): clean_case_number,
                form_field_names.get('year', 'cmbYear'): filing_year,
            })
            
            
            if form_field_names.get('submit'):
                form_data[form_field_names['submit']] = 'Submit'
            else:
                form_data['Submit'] = 'Submit'
            
            logger.info(f"Form data prepared: case_type={form_data.get('case_type')}, case_no={form_data.get('case_no')}, year={form_data.get('cmbYear')}")
            
            return form_data
            
        except Exception as e:
            logger.error(f"Error extracting form data: {str(e)}")
            return None
    
    def _fill_search_form_selenium(self, driver, case_type, case_number, filing_year):
        """Fill search form using Selenium for the actual Delhi High Court website"""
        try:
            
            time.sleep(2)
            
            
            try:
                screenshot_path = os.path.join('downloads', f'form_before_{int(time.time())}.png')
                driver.save_screenshot(screenshot_path)
                logger.info(f"Form screenshot saved to {screenshot_path}")
            except:
                pass
            
            
            case_type_mapping = {
                'civil': ['CIVIL', 'CIVIL APPEAL', 'CIVIL SUIT', 'CS', 'C.S.', 'CIV', 'C.A.', 'CIVIL CASE', 'REGULAR CIVIL SUIT'],
                'criminal': ['CRIMINAL', 'CRL', 'CRL.', 'CRL.A.', 'CRL.M.C.', 'CRIMINAL APPEAL', 'CRIMINAL CASE', 'CRL.REV.P.', 'BAIL', 'SESSIONS'],
                'writ': ['WRIT', 'W.P.', 'W.P.(C)', 'W.P.(CRL)', 'WRIT PETITION', 'WP', 'WPC', 'WPCRL', 'WRIT CASE', 'HABEAS CORPUS'],
                'company': ['COMPANY', 'CO', 'CO.', 'COMPANY APPEAL', 'COMP', 'CP', 'COMPANY CASE', 'CA', 'COMP.A.', 'COMPANY PETITION'],
                'arbitration': ['ARB', 'ARB.', 'ARB.A.', 'ARBITRATION', 'A', 'ARB.P.', 'ARBITRATION PETITION', 'ARBITRATION APPEAL', 'ARB. CASE'],
                'matrimonial': ['MAT', 'MAT.A.', 'MATRIMONIAL', 'MCA', 'MC', 'MATRI', 'MARRIAGE', 'MATRIMONIAL CASE', 'FAMILY'],
                'tax': ['TAX', 'ITXA', 'TA', 'ITA', 'ITAT', 'TAX APPEAL', 'INCOME TAX APPEAL', 'TAX CASE', 'INCOME TAX', 'ST', 'SERVICE TAX', 'GST', 'VAT'],
                'motor_accident': ['MAC', 'MAC.APP.', 'MOTOR ACCIDENT', 'MACT', 'MAC.A.', 'MA', 'MOTOR', 'MOTOR CASE', 'ACCIDENT CLAIM'],
                'rent': ['RC', 'R.C.REV.', 'RENT CONTROL', 'RENT', 'RCR', 'RCA', 'RENT CASE', 'TENANCY', 'EVICTION'],
                'labor': ['LPA', 'LABOR', 'LABOUR', 'LAB', 'LC', 'LCA', 'WC', 'WORKMEN', 'INDUSTRIAL DISPUTE', 'SERVICE']
            }
            
            
            try:
                
                select_elements = driver.find_elements(By.TAG_NAME, "select")
                all_options = {}
                for idx, select_elem in enumerate(select_elements):
                    try:
                        select_obj = Select(select_elem)
                        options_text = [option.text.strip() for option in select_obj.options if option.text.strip()]
                        all_options[f"select_{idx}"] = options_text
                    except:
                        continue
                
                logger.info(f"Available select options on page: {json.dumps(all_options)}")
            except Exception as e:
                logger.error(f"Error getting form options: {e}")
            
            
            case_type_select = None
            selectors = [
                (By.ID, "case_type_sel"),
                (By.NAME, "case_type"),
                (By.NAME, "caseType"),
                (By.XPATH, "//select[contains(@id, 'case') or contains(@name, 'case')]"),
                (By.XPATH, "//select[contains(@id, 'type') or contains(@name, 'type')]"),
                (By.XPATH, "//select") 
            ]
            
            for selector_type, selector_value in selectors:
                try:
                    elements = driver.find_elements(selector_type, selector_value)
                    if elements:
                        case_type_select = elements[0]
                        logger.info(f"Found case type select with {selector_type}, {selector_value}")
                        break
                except:
                    continue
            
            if not case_type_select:
                logger.error("Could not find case type select element")
                return False
            
            
            select = Select(case_type_select)
            
            
            normalized_case_type = case_type.lower()
            possible_values = []
            
            
            for key, values in case_type_mapping.items():
                if key == normalized_case_type or normalized_case_type in key:
                    possible_values.extend(values)
                    break
            
            if not possible_values:
                possible_values = [case_type.upper()]
            
            
            selected = False
            
            
            options_text = [option.text.strip() for option in select.options]
            logger.info(f"Available case type options: {options_text}")
            
            
            for value in possible_values:
                try:
                    if value in options_text:
                        select.select_by_visible_text(value)
                        logger.info(f"Selected case type by exact match: {value}")
                        selected = True
                        break
                except Exception as e:
                    logger.error(f"Error selecting {value}: {e}")
            
            
            if not selected:
                for option_text in options_text:
                    for value in possible_values:
                        if value.upper() in option_text.upper():
                            try:
                                select.select_by_visible_text(option_text)
                                logger.info(f"Selected case type by partial match: {option_text}")
                                selected = True
                                break
                            except:
                                continue
                    if selected:
                        break
            
            
            if not selected:
                for option in select.options:
                    if option.text.strip() and option.text.lower() not in ['select', 'select type', 'choose']:
                        try:
                            select.select_by_visible_text(option.text)
                            logger.info(f"Selected first available case type: {option.text}")
                            selected = True
                            break
                        except:
                            continue
            
            
            case_number_input = None
            number_selectors = [
                (By.ID, "case_no"),
                (By.NAME, "case_no"),
                (By.NAME, "caseNo"),
                (By.XPATH, "//input[contains(@id, 'case_no') or contains(@name, 'case_no')]"),
                (By.XPATH, "//input[contains(@placeholder, 'number') or contains(@placeholder, 'case')]"),
                (By.XPATH, "//input[@type='text']")  
            ]
            
            for selector_type, selector_value in number_selectors:
                try:
                    elements = driver.find_elements(selector_type, selector_value)
                    if elements:
                        case_number_input = elements[0]
                        logger.info(f"Found case number input with {selector_type}, {selector_value}")
                        break
                except:
                    continue
            
            if not case_number_input:
                logger.error("Could not find case number input")
                return False
                
            case_number_input.clear()
            case_number_input.send_keys(case_number)
            
            
            year_field = None
            year_selectors = [
                (By.NAME, "cmbYear"),
                (By.ID, "case_year"),
                (By.NAME, "filing_year"),
                (By.XPATH, "//select[contains(@id, 'year') or contains(@name, 'year')]"),
                (By.XPATH, "//input[contains(@id, 'year') or contains(@name, 'year')]"),
                (By.XPATH, "//input[@type='number']")
            ]
            
            for selector_type, selector_value in year_selectors:
                try:
                    elements = driver.find_elements(selector_type, selector_value)
                    if elements:
                        year_field = elements[0]
                        logger.info(f"Found year field with {selector_type}, {selector_value}")
                        break
                except:
                    continue
            
            if not year_field:
                logger.error("Could not find year field")
                return False
            
            
            if year_field.tag_name == 'select':
                year_dropdown = Select(year_field)
                try:
                    year_dropdown.select_by_value(filing_year)
                    logger.info(f"Selected year by value: {filing_year}")
                except:
                    try:
                        year_dropdown.select_by_visible_text(filing_year)
                        logger.info(f"Selected year by text: {filing_year}")
                    except:
                        
                        options = year_dropdown.options
                        for option in options:
                            if filing_year in option.text:
                                try:
                                    option.click()
                                    logger.info(f"Selected year by partial text: {option.text}")
                                    break
                                except:
                                    continue
            else:
                
                year_field.clear()
                year_field.send_keys(filing_year)
                logger.info(f"Entered year in input field: {filing_year}")
            
            
            try:
                screenshot_path = os.path.join('downloads', f'form_after_fill_{int(time.time())}.png')
                driver.save_screenshot(screenshot_path)
                logger.info(f"Form after fill screenshot saved to {screenshot_path}")
            except:
                pass
            
            
            submit_button = None
            submit_selectors = [
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Search')]"),
                (By.XPATH, "//input[contains(@value, 'Search')]"),
                (By.XPATH, "//button[contains(@class, 'search')]"),
                (By.XPATH, "//button")  
            ]
            
            for selector_type, selector_value in submit_selectors:
                try:
                    elements = driver.find_elements(selector_type, selector_value)
                    if elements:
                        submit_button = elements[0]
                        logger.info(f"Found submit button with {selector_type}, {selector_value}")
                        break
                except:
                    continue
            
            if submit_button:
                try:
                    submit_button.click()
                    logger.info("Clicked submit button")
                    time.sleep(2)  
                    return True
                except Exception as e:
                    logger.error(f"Error clicking submit: {e}")
                    
                    try:
                        driver.execute_script("arguments[0].click();", submit_button)
                        logger.info("Clicked submit button via JavaScript")
                        return True
                    except Exception as js_e:
                        logger.error(f"JavaScript click failed: {js_e}")
            else:
                
                try:
                    form = driver.find_element(By.TAG_NAME, "form")
                    form.submit()
                    logger.info("Submitted form directly")
                    return True
                except:
                    
                    try:
                        case_number_input.send_keys(Keys.RETURN)
                        logger.info("Submitted form with Enter key")
                        return True
                    except:
                        
                        try:
                            driver.execute_script("document.forms[0].submit();")
                            logger.info("Submitted form via JavaScript")
                            return True
                        except:
                            logger.error("All submission methods failed")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error filling search form: {str(e)}")
            return False
    
    def _parse_case_results(self, html_content, case_type, case_number, filing_year):
        """Parse case search results from HTML with improved accuracy"""
        try:
            if not html_content:
                return {
                    'success': False,
                    'error': 'No response received from the court website',
                    'case_type': case_type,
                    'case_number': case_number,
                    'filing_year': filing_year
                }
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            
            if logger.getEffectiveLevel() <= logging.DEBUG:
                try:
                    debug_html_path = os.path.join('downloads', f'results_{case_type}_{case_number}_{filing_year}.html')
                    with open(debug_html_path, 'w', encoding='utf-8') as f:
                        f.write(str(soup))
                    logger.debug(f"Saved results HTML to {debug_html_path}")
                except:
                    pass
            
            
            no_records_indicators = [
                'no record found',
                'no records found',
                'case not found',
                'invalid case number',
                'no matching records',
                'no result found',
                'not available',
                'could not find',
                'record does not exist',
                'please enter valid',
                'no entries found',
                'please search again',
                'no case found',
                'invalid input',
                'incorrect case'
            ]
            
            page_text = soup.get_text().lower()
            for indicator in no_records_indicators:
                if indicator in page_text:
                    logger.info(f"Case not found: {case_type}/{case_number}/{filing_year}")
                    return {
                        'success': False,
                        'error': f"Case not found: {case_type}/{case_number}/{filing_year}. Please verify the details are correct.",
                        'case_type': case_type,
                        'case_number': case_number,
                        'filing_year': filing_year
                    }
            
            
            tables = soup.find_all('table')
            if not tables:
                
                result_indicators = [
                    'case details',
                    'status',
                    'petitioner',
                    'respondent',
                    'advocate',
                    'filing date',
                    'listing date',
                    'hearing date',
                    'next date',
                    'case number',
                    'case status',
                    'bench',
                    'judge',
                    'court no',
                    'case type'
                ]
                
                result_found = False
                for indicator in result_indicators:
                    if indicator in page_text:
                        result_found = True
                        logger.info(f"Found case result indicator: '{indicator}'")
                        break
                
                if not result_found:
                    logger.warning("No tables or result indicators found")
                    return {
                        'success': False,
                        'error': "Could not find case data in the court response",
                        'case_type': case_type,
                        'case_number': case_number,
                        'filing_year': filing_year
                    }
            
            
            case_data = {
                'success': True,
                'case_type': case_type,
                'case_number': case_number,
                'filing_year': int(filing_year),
                'parties': {},
                'filing_date': None,
                'next_hearing_date': None,
                'status': 'Unknown',
                'documents': [],
                'case_details': {},  
                'source': 'Delhi High Court'
            }
            
            
            for table in tables:
                
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        key = cells[0].get_text().strip().lower()
                        value = cells[1].get_text().strip()
                        
                        if key and value:
                            
                            if any(field in key for field in ['petitioner', 'appellant', 'applicant']):
                                case_data['parties']['petitioner'] = value
                            elif any(field in key for field in ['respondent', 'defendant']):
                                case_data['parties']['respondent'] = value
                            elif any(field in key for field in ['advocate', 'counsel', 'lawyer']):
                                case_data['parties']['advocate'] = value
                            elif any(field in key for field in ['filing date', 'date of filing']):
                                case_data['filing_date'] = value
                            elif any(field in key for field in ['next date', 'next hearing']):
                                case_data['next_hearing_date'] = value
                            elif any(field in key for field in ['status', 'case status']):
                                case_data['status'] = value
                            else:
                                
                                clean_key = key.replace(':', '').strip()
                                case_data['case_details'][clean_key] = value
            
            
            links = soup.find_all('a')
            for link in links:
                href = link.get('href', '')
                text = link.get_text().strip()
                if href and ('.pdf' in href.lower() or '/document/' in href.lower()):
                    case_data['documents'].append({
                        'type': text or 'Document',
                        'url': href if href.startswith('http') else f"{self.base_url}{href}",
                        'description': text or 'Court Document'
                    })
            
            
            if not case_data['parties'].get('petitioner') and not case_data['parties'].get('respondent'):
                
                petitioner_matches = re.findall(r'petitioner\s*:?\s*([^vs\n]+)', page_text, re.IGNORECASE)
                if petitioner_matches:
                    case_data['parties']['petitioner'] = petitioner_matches[0].strip()
                
                respondent_matches = re.findall(r'respondent\s*:?\s*([^\n]+)', page_text, re.IGNORECASE)
                if respondent_matches:
                    case_data['parties']['respondent'] = respondent_matches[0].strip()
                
                
                versus_matches = re.findall(r'([^vs\n]+)\s+vs\.?\s+([^\n]+)', page_text, re.IGNORECASE)
                if versus_matches:
                    case_data['parties']['petitioner'] = versus_matches[0][0].strip()
                    case_data['parties']['respondent'] = versus_matches[0][1].strip()
            
            
            if (case_data['parties'] or case_data['case_details'] or case_data['status'] != 'Unknown'):
                logger.info(f"Successfully parsed case data for {case_type}/{case_number}/{filing_year}")
                
                if 'cnr' in case_data['case_details']:
                    case_data['cnr'] = case_data['case_details']['cnr']
                if 'actual case number' in case_data['case_details']:
                    case_data['actual_case_number'] = case_data['case_details']['actual case number']
                
                return case_data
            else:
                logger.warning(f"Found response but couldn't extract meaningful case data for {case_type}/{case_number}/{filing_year}")
                return {
                    'success': False,
                    'error': "Could not extract case details from the court website response.",
                    'case_type': case_type,
                    'case_number': case_number,
                    'filing_year': filing_year
                }
            
        except Exception as e:
            logger.error(f"Error parsing case results: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to parse case information: {str(e)}"
            }
    
    def _extract_case_details_from_table(self, table):
        """Extract case details from a table element based on Delhi High Court website structure"""
        details = {}
        
        try:
            
            rows = table.find_all('tr')
            
            
            for i, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                
                
                if len(cells) < 2:
                    continue
                
                
                header_cell = cells[0].get_text(strip=True).lower()
                value_cell = cells[1].get_text(strip=True)
                
                
                if any(term in header_cell for term in ['petitioner', 'appellant', 'plaintiff', 'complainant']):
                    if 'parties' not in details:
                        details['parties'] = {}
                    details['parties']['petitioner'] = [value_cell]
                    
                elif any(term in header_cell for term in ['respondent', 'defendant', 'accused']):
                    if 'parties' not in details:
                        details['parties'] = {}
                    details['parties']['respondent'] = [value_cell]
                    
                elif any(term in header_cell for term in ['advocate', 'counsel', 'lawyer']):
                    
                    if 'advocates' not in details:
                        details['advocates'] = value_cell
                        
                elif 'case status' in header_cell or 'status' == header_cell:
                    details['status'] = value_cell
                    
                elif 'filing date' in header_cell or 'registration date' in header_cell:
                    details['filing_date'] = self._parse_date(value_cell)
                    
                elif 'listing date' in header_cell or 'next date' in header_cell or 'hearing date' in header_cell:
                    details['next_hearing_date'] = self._parse_date(value_cell)
                    
                
                elif any(term in header_cell for term in ['stage', 'court no', 'bench', 'judge']):
                    clean_key = header_cell.replace(' ', '_')
                    details[clean_key] = value_cell
            
        except Exception as e:
            logger.error(f"Error extracting table details: {str(e)}")
        
        return details
    
    def _extract_document_links(self, soup):
        """Extract PDF document links from the Delhi High Court website page"""
        documents = []
        
        try:
            
            
            all_links = soup.find_all('a')
            
            
            document_links = []
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                
                if href.lower().endswith('.pdf') or 'pdf' in href.lower():
                    document_links.append((link, href, text))
                    
                
                elif any(keyword in text.lower() for keyword in ['order', 'judgment', 'notice', 'document', 'download']):
                    document_links.append((link, href, text))
            
            
            for link, href, text in document_links:
                
                if href.startswith('/'):
                    href = self.base_url + href
                elif not href.startswith('http'):
                    href = f"{self.base_url}/{href}"
                
                
                date_match = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', text)
                doc_date = None
                if date_match:
                    doc_date = self._parse_date(date_match.group(1))
                
                documents.append({
                    'type': self._classify_document_type(text),
                    'description': text,
                    'url': href,
                    'date': doc_date
                })
        
        except Exception as e:
            logger.error(f"Error extracting document links: {str(e)}")
        
        return documents
    
    def _classify_document_type(self, text):
        """Classify document type based on text"""
        text_lower = text.lower()
        
        if 'order' in text_lower:
            return 'Order'
        elif 'judgment' in text_lower or 'judgement' in text_lower:
            return 'Judgment'
        elif 'notice' in text_lower:
            return 'Notice'
        elif 'petition' in text_lower:
            return 'Petition'
        else:
            return 'Document'
    
    def _process_case_detail(self, case_data, label, value):
        """Process a case detail based on its label"""
        if any(term in label for term in ['petitioner', 'appellant', 'plaintiff', 'complainant']):
            if 'parties' not in case_data:
                case_data['parties'] = {}
            if 'petitioner' not in case_data['parties']:
                case_data['parties']['petitioner'] = []
            case_data['parties']['petitioner'].append(value)
            
        elif any(term in label for term in ['respondent', 'defendant', 'accused']):
            if 'parties' not in case_data:
                case_data['parties'] = {}
            if 'respondent' not in case_data['parties']:
                case_data['parties']['respondent'] = []
            case_data['parties']['respondent'].append(value)
            
        elif 'case status' in label or 'status' == label:
            case_data['status'] = value
            
        elif any(term in label for term in ['filing date', 'registration date']):
            case_data['filing_date'] = self._parse_date(value)
            
        elif any(term in label for term in ['listing date', 'next date', 'hearing date']):
            case_data['next_hearing_date'] = self._parse_date(value)
    
    def _parse_date(self, date_str):
        """Parse date string to datetime object"""
        try:
            
            date_formats = [
                '%d/%m/%Y',
                '%d-%m-%Y',
                '%Y-%m-%d',
                '%d.%m.%Y',
                '%B %d, %Y',
                '%d %B %Y'
            ]
            
            date_str = date_str.strip()
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {str(e)}")
            return None
    
    def _create_demo_case_data(self, case_type, case_number, filing_year):
        """Create demo case data for demonstration purposes"""
        
        
        demo_parties = {
            'civil': {
                'petitioner': ['John Doe', 'ABC Corporation'],
                'respondent': ['Jane Smith', 'XYZ Ltd.']
            },
            'criminal': {
                'petitioner': ['State of Delhi'],
                'respondent': ['Accused Person']
            },
            'writ': {
                'petitioner': ['Citizen Petitioner'],
                'respondent': ['Government of Delhi', 'Union of India']
            }
        }
        
        parties = demo_parties.get(case_type, {
            'petitioner': ['Petitioner Name'],
            'respondent': ['Respondent Name']
        })
        
        filing_date = datetime(int(filing_year), 3, 15).date()
        next_hearing = filing_date + timedelta(days=30)
        
        demo_documents = [
            {
                'type': 'Order',
                'description': f'Interim Order dated {filing_date}',
                'url': f'{self.base_url}/demo/order_{case_number}_{filing_year}.pdf',
                'date': filing_date
            },
            {
                'type': 'Notice',
                'description': 'Notice to Respondent',
                'url': f'{self.base_url}/demo/notice_{case_number}_{filing_year}.pdf',
                'date': filing_date + timedelta(days=7)
            }
        ]
        
        return {
            'success': True,
            'case_type': case_type,
            'case_number': case_number,
            'filing_year': int(filing_year),
            'parties': parties,
            'filing_date': filing_date,
            'next_hearing_date': next_hearing,
            'status': 'Listed for Hearing',
            'documents': demo_documents,
            'note': 'This is demo data for demonstration purposes'
        }
