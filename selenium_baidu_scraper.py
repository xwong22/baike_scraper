import argparse
import datetime
import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

class BaiduBaikeSeleniumScraper:
    """A scraper for Baidu Baike pages using Selenium to handle dynamic content"""
    
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Set up Chrome options - keeping it simple for visible browser
        self.chrome_options = Options()
        self.chrome_options.add_argument("--window-size=1920,1080")
        
        logging.info("Initialized Baidu Baike Selenium Scraper with visible browser mode")
    
    def setup_driver(self):
        """Set up Selenium WebDriver with visible browser"""
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                logging.info(f"Setting up visible Chrome WebDriver (attempt {attempt+1}/{max_retries})")
                print(f"Starting Chrome browser in visible mode (attempt {attempt+1})")
                
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=self.chrome_options)
                
                logging.info("Chrome browser launched successfully in visible mode")
                print("Chrome browser launched successfully. You should now see the browser window.")
                return driver
            except Exception as e:
                logging.error(f"Failed to set up WebDriver: {str(e)}")
                print(f"Error starting Chrome: {str(e)}")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying in {retry_delay} seconds...")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error("All WebDriver setup attempts failed")
                    print("Failed to start Chrome after multiple attempts. Check your Chrome installation.")
                    raise
    
    def scrape_page(self, url):
        """Scrape a Baidu Baike page and extract structured data"""
        # Clean URL - remove spaces
        url = url.replace(" ", "")
        logging.info(f"Cleaning URL: {url}")
        print(f"Scraping: {url}")
        
        max_retries = 3
        retry_delay = 5  # seconds
        driver = None
        
        try:
            # Try to set up the driver and load the page with retries
            for attempt in range(max_retries):
                try:
                    if driver:
                        # If we're retrying, quit the previous driver first
                        try:
                            driver.quit()
                        except:
                            pass
                    
                    driver = self.setup_driver()
                    logging.info(f"Loading page (attempt {attempt+1}/{max_retries}): {url}")
                    print(f"Loading page... (you should see this in the browser)")
                    driver.get(url)
                    
                    # Wait for the main content to load
                    try:
                        print("Waiting for page content to load...")
                        WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "J-lemma-title"))
                        )
                        print("Page loaded successfully!")
                        break  # Success, exit the retry loop
                    except:
                        # If J-lemma-title is not found, try another common element
                        try:
                            print("Trying alternative page element...")
                            WebDriverWait(driver, 15).until(
                                EC.presence_of_element_located((By.CLASS_NAME, "J-summary"))
                            )
                            print("Page loaded successfully with alternative element!")
                            break  # Success with alternate element, exit the retry loop
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logging.warning(f"Page load attempt {attempt+1} failed: {str(e)}")
                                logging.info(f"Retrying in {retry_delay} seconds...")
                                print(f"Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                            else:
                                logging.error("All page load attempts failed")
                                print("Failed to load page after multiple attempts. Check your internet connection.")
                                raise
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.warning(f"Navigation attempt {attempt+1} failed: {str(e)}")
                        logging.info(f"Retrying in {retry_delay} seconds...")
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logging.error("All navigation attempts failed")
                        print("Failed to navigate to the page after multiple attempts. Check your internet connection.")
                        raise
            
            # Add a small delay to ensure all dynamic content is loaded
            time.sleep(3)
            
            # Create output folder
            folder_path = self.create_output_folder(url)
            print(f"Created output folder: {folder_path}")
            
            # Get the page HTML after JavaScript execution
            html_content = driver.page_source
            
            # Save the raw HTML
            self.save_raw_html(html_content, folder_path)
            print(f"Saved raw HTML to: {folder_path / 'raw.html'}")
            
            # Parse the HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract structured data
            logging.info("Extracting page title")
            title = self.extract_title(soup)
            print(f"Extracted title: {title}")
            
            logging.info("Extracting short description")
            short_description = self.extract_short_description(soup)
            
            logging.info("Extracting abstract")
            abstract = self.extract_abstract(soup)
            
            logging.info("Extracting info box")
            info_box = self.extract_info_box(soup)
            
            logging.info("Extracting table of contents")
            toc = self.extract_toc(soup)
            
            logging.info("Extracting main content")
            content = self.extract_content(soup)
            print("Main content extracted successfully")
            
            logging.info("Extracting references")
            references = self.extract_references(soup)
            
            # Wait explicitly for references if they might be dynamically loaded
            try:
                print("Looking for references section with CSS selector...")
                # Use CSS selector to look for div with class that starts with lemmaReference
                reference_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class^='lemmaReference']"))
                )
                # Get updated HTML after waiting for references
                html_content = driver.page_source
                soup = BeautifulSoup(html_content, 'html.parser')
                # Try extracting references again
                logging.info("Re-extracting references after waiting")
                references = self.extract_references(soup)
                print(f"Found {len(references)} references")
            except:
                logging.warning("References section not found even after waiting")
                print("No references section found")
            
            # Combine structured data
            data = {
                'url': url,
                'title': title,
                'short_description': short_description,
                'abstract': abstract,
                'info_box': info_box,
                'toc': toc,
                'content': content,
                'references': references
            }
            
            # Check if tables were found
            if content.get('tables') and len(content['tables']) > 0:
                print(f"Including {len(content['tables'])} tables in output data")
                
                # Also save tables as a separate CSV file for each table
                for table in content['tables']:
                    table_index = table.get('table_index', 0)
                    headers = table.get('headers', [])
                    rows = table.get('rows', [])
                    
                    # Create a DataFrame for the table
                    if headers and rows:
                        try:
                            # Create DataFrame with headers
                            df = pd.DataFrame(rows, columns=headers)
                            
                            # Save as CSV
                            csv_path = folder_path / f"table_{table_index}.csv"
                            df.to_csv(csv_path, index=False, encoding='utf-8')
                            print(f"Saved Table {table_index} as CSV: {csv_path}")
                        except Exception as e:
                            logging.error(f"Error saving table {table_index} as CSV: {str(e)}")
                            print(f"Error saving table {table_index} as CSV: {str(e)}")
            
            # Also check for inline tables in the content
            inline_table_count = 0
            if 'clean' in content:
                for i, item in enumerate(content['clean']):
                    if item.get('type') == 'table':
                        inline_table_count += 1
                        table_data = item.get('text', {})
                        headers = table_data.get('headers', [])
                        rows = table_data.get('rows', [])
                        
                        # Create a DataFrame for the table
                        if headers and rows:
                            try:
                                # Create DataFrame with headers
                                df = pd.DataFrame(rows, columns=headers)
                                
                                # Save as CSV
                                csv_path = folder_path / f"inline_table_{inline_table_count}.csv"
                                df.to_csv(csv_path, index=False, encoding='utf-8')
                                print(f"Saved inline table {inline_table_count} as CSV: {csv_path}")
                            except Exception as e:
                                logging.error(f"Error saving inline table {inline_table_count} as CSV: {str(e)}")
                                print(f"Error saving inline table {inline_table_count} as CSV: {str(e)}")
            
            if inline_table_count > 0:
                print(f"Found and saved {inline_table_count} inline tables")
            
            # Generate markdown content
            logging.info("Generating markdown content")
            print("Generating markdown content...")
            markdown = self.generate_markdown_content(data)
            
            # Save data as JSON
            json_path = folder_path / "data.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.info(f"Saved JSON data to: {json_path}")
            print(f"Saved JSON data to: {json_path}")
            
            # Save clean markdown
            md_path = folder_path / "content.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown['clean'])
            logging.info(f"Saved clean markdown to: {md_path}")
            print(f"Saved clean markdown to: {md_path}")
            
            # Save markdown with citations
            md_citations_path = folder_path / "content_with_citations.md"
            with open(md_citations_path, 'w', encoding='utf-8') as f:
                f.write(markdown['with_citations'])
            logging.info(f"Saved markdown with citations to: {md_citations_path}")
            print(f"Saved markdown with citations to: {md_citations_path}")
            
            print(f"\nScraping completed successfully for: {title}")
            print(f"All data saved to: {folder_path}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error scraping URL: {url}")
            logging.error(f"Exception: {str(e)}")
            return None
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def extract_title(self, soup):
        """Extract title of the page"""
        title_div = soup.find('h1', class_='J-lemma-title')
        if title_div:
            return title_div.get_text(strip=True)
        return ""
    
    def extract_short_description(self, soup):
        """Extract short description below title"""
        desc_div = soup.find('div', id='lemmaDesc')
        if desc_div:
            return desc_div.get_text(strip=True)
        return ""
    
    def clean_text_without_citations(self, html):
        """Clean text by removing citation tags"""
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove all sup tags (citations)
        for sup in soup.find_all('sup'):
            sup.decompose()
            
        # Get the text content
        text = soup.get_text(strip=True)
        # Clean up any remaining citation patterns
        text = re.sub(r'\[\d+\]', '', text)
        return text.strip()
    
    def format_text_with_citations(self, text):
        """Format text with citation tags in [1, 2, 3] format"""
        if not text:
            return ""
        
        # Use BeautifulSoup to parse the HTML
        soup = BeautifulSoup(f"<div>{text}</div>", 'html.parser')
        
        # Find all sup tags
        all_sups = soup.find_all('sup')
        if not all_sups:
            return soup.div.get_text(strip=True)
        
        logging.info(f"Found {len(all_sups)} citation tags")
        
        # Create a simpler approach - create a clean version of text first
        clean_text = soup.div.get_text(strip=True)
        
        # Remove the duplicated citation patterns that look like [123] [123]
        clean_text = re.sub(r'\[(\d+)\]\s+\[\1\]', r'[\1]', clean_text)
        
        # Handle range citations like [91-92] and convert to [91, 92]
        def replace_range_citations(match):
            range_str = match.group(1)
            if '-' in range_str:
                start, end = map(int, range_str.split('-'))
                # Create a comma-separated list of numbers in the range
                numbers = list(range(start, end + 1))
                return f"[{', '.join(map(str, numbers))}]"
            return match.group(0)
        
        clean_text = re.sub(r'\[([\d\-]+)\]', replace_range_citations, clean_text)
        
        # Fix complex citations like [262] [411] -> [262, 411]
        # First identify all citations
        citation_pattern = r'\[(\d+(?:,\s*\d+)*)\]'
        citations = re.finditer(citation_pattern, clean_text)
        
        # Build a map of positions to citation numbers
        position_to_citation = {}
        for match in citations:
            citation_str = match.group(1)
            start_pos = match.start()
            end_pos = match.end()
            position_to_citation[(start_pos, end_pos)] = citation_str
        
        # Sort positions by start position
        sorted_positions = sorted(position_to_citation.keys())
        
        # Group adjacent citations (within 3 characters of each other)
        citation_groups = []
        current_group = []
        current_positions = []
        
        for i, pos in enumerate(sorted_positions):
            if not current_group:
                # First citation in a new group
                current_group.append(position_to_citation[pos])
                current_positions.append(pos)
            else:
                # Check if this citation is close to the previous one
                prev_end = current_positions[-1][1]
                curr_start = pos[0]
                
                if curr_start - prev_end <= 3:  # If they're close enough
                    # Add to current group
                    current_group.append(position_to_citation[pos])
                    current_positions.append(pos)
                else:
                    # Finish current group and start a new one
                    citation_groups.append((current_group, current_positions))
                    current_group = [position_to_citation[pos]]
                    current_positions = [pos]
        
        # Don't forget the last group
        if current_group:
            citation_groups.append((current_group, current_positions))
        
        # Now replace each group with a single citation
        # Work from back to front to avoid position shifting
        result_text = clean_text
        for group, positions in reversed(citation_groups):
            if len(group) > 1:
                # Multiple citations to combine
                # Find start of first and end of last citation
                start_pos = min(p[0] for p in positions)
                end_pos = max(p[1] for p in positions)
                
                # Combine all citation numbers
                all_numbers = []
                for citation in group:
                    all_numbers.extend([num.strip() for num in citation.split(',')])
                
                # Create combined citation
                combined_citation = f"[{', '.join(sorted(set(all_numbers), key=int))}]"
                
                # Replace in text
                result_text = result_text[:start_pos] + combined_citation + result_text[end_pos:]
        
        return result_text.strip()

    def extract_abstract(self, soup):
        """Extract abstract with and without citations"""
        abstract_div = soup.find('div', class_='lemmaSummary_yKMC1')
        
        if not abstract_div:
            return {"clean": "", "with_citations": ""}
            
        # Get the HTML for processing
        abstract_html = str(abstract_div)
        
        # Get the versions with and without citations
        abstract_without_citations = self.clean_text_without_citations(abstract_html)
        abstract_with_citations = self.format_text_with_citations(abstract_html)
        
        return {
            "clean": abstract_without_citations,
            "with_citations": abstract_with_citations
        }

    def extract_info_box(self, soup):
        """Extract information from the info box"""
        info_box = {}
        info_box_with_citations = {}
        info_div = soup.find('div', class_='J-basic-info')
        if info_div:
            for item in info_div.find_all('div', class_='itemWrapper_ZNZh3'):
                name = item.find('dt', class_='itemName_LS0Jv')
                value = item.find('dd', class_='itemValue_AYbkR')
                if name and value:
                    name_text = name.get_text(strip=True)
                    # Get original HTML for the value
                    value_html = str(value)
                    # Create versions with and without citations
                    value_without_citations = self.clean_text_without_citations(value_html)
                    value_with_citations = self.format_text_with_citations(value_html)
                    
                    info_box[name_text] = value_without_citations
                    info_box_with_citations[name_text] = value_with_citations
        return {
            'clean': info_box,
            'with_citations': info_box_with_citations
        }

    def extract_toc(self, soup):
        """Extract table of contents"""
        toc = []
        toc_div = soup.find('div', class_='catalogList_MR9Nd')
        if toc_div:
            for li in toc_div.find_all('li'):
                class_name = li.get('class', [''])[0]
                level = 0
                if class_name.startswith('level'):
                    # Extract just the number part using regex
                    match = re.search(r'level(\d+)', class_name)
                    if match:
                        level = int(match.group(1))
                    else:
                        logging.warning(f"Could not extract level from class name: {class_name}")
                # get the text from the li tag
                text = li.get_text(strip=True)
                # remove ▪ from the text
                text = text.replace('▪', '')
                if level == 1:
                    # remove the numbering (in front of the text)
                    text = re.sub(r'^\d+\s*', '', text)
                toc.append({
                    'level': level,
                    'text': text
                })
        return toc

    def extract_table(self, table_element):
        """Extract data from a table element"""
        table_data = {
            'headers': [],
            'rows': []
        }
        
        try:
            # Try to find table headers (th elements)
            headers = table_element.find_all('th')
            if headers:
                table_data['headers'] = [header.get_text(strip=True) for header in headers]
            
            # If no headers found, try to use the first row as headers
            if not table_data['headers']:
                first_row = table_element.find('tr')
                if first_row:
                    cells = first_row.find_all(['th', 'td'])
                    if cells:
                        table_data['headers'] = [cell.get_text(strip=True) for cell in cells]
            
            # Get all rows
            rows = table_element.find_all('tr')
            
            # Skip the first row if it was used for headers
            start_idx = 1 if table_data['headers'] and len(rows) > 0 else 0
            
            # Find the max number of columns in the table (for handling merged cells)
            max_cols = len(table_data['headers']) if table_data['headers'] else 0
            for row in rows:
                cells = row.find_all('td')
                max_cols = max(max_cols, len(cells))
            
            # Process each row
            for row in rows[start_idx:]:
                cells = row.find_all('td')
                if cells:
                    # Extract text from each cell
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    
                    # Handle rowspan and colspan by looking for these attributes
                    for i, cell in enumerate(cells):
                        # Look for colspan attribute
                        colspan = cell.get('colspan')
                        if colspan:
                            try:
                                colspan = int(colspan)
                                # Add empty cells for the spanned columns
                                if colspan > 1:
                                    for _ in range(colspan - 1):
                                        row_data.insert(i + 1, "")
                            except (ValueError, TypeError):
                                pass
                    
                    # Pad the row if it has fewer cells than max_cols
                    while len(row_data) < max_cols:
                        row_data.append("")
                    
                    # Add the row data
                    table_data['rows'].append(row_data)
            
            print(f"Extracted table with {len(table_data['headers'])} headers and {len(table_data['rows'])} rows")
            logging.info(f"Extracted table with {len(table_data['headers'])} columns and {len(table_data['rows'])} rows")
            return table_data
            
        except Exception as e:
            logging.error(f"Error extracting table: {str(e)}")
            print(f"Error extracting table: {str(e)}")
            return table_data

    def extract_content(self, soup):
        """Extract main content with headings and paragraphs"""
        content = []
        content_with_citations = []
        content_div = soup.find('div', class_='J-lemma-content')
        if content_div:            
            # Find all divs, ordered lists, and unordered lists in the content
            logging.info("Extracting content elements (divs, ol, ul)")
            for element in content_div.find_all(['div', 'ol', 'ul'], recursive=False):                   
                if 'paraTitle_WslP_' in element.get('class', []):
                    # Handle headings
                    for class_name in element.get('class', []):
                        if class_name.startswith('level-'):
                            # Extract just the number part using regex
                            match = re.search(r'level-(\d+)', class_name)
                            if match:
                                level = int(match.group(1))
                                # get the text from the h tag
                                h_tag = element.find('h' + str(level+1))
                                if h_tag:
                                    text = h_tag.get_text(strip=True)
                                else:
                                    text = element.get_text(strip=True)
                                
                                # Add to both versions (headings typically don't have citations)
                                content.append({
                                    'type': f'h{level}',
                                    'text': text
                                })
                                content_with_citations.append({
                                    'type': f'h{level}',
                                    'text': text
                                })
                            else:
                                logging.warning(f"Could not extract level from class name: {class_name}")
                elif 'content_pzMvr' in element.get('class', []):
                    # Handle content
                    # Get the original HTML
                    div_html = str(element)
                    
                    # Create clean version
                    text_without_citations = self.clean_text_without_citations(div_html)
                    content.append({
                        'type': 'paragraph',
                        'text': text_without_citations
                    })
                    
                    # Create version with citations
                    text_with_citations = self.format_text_with_citations(div_html)
                    content_with_citations.append({
                        'type': 'paragraph',
                        'text': text_with_citations
                    })
                elif "ordered_PAfTw" in element.get('class', []):
                    # Handle list
                    for li in element.find_all('li'):
                        text = li.get_text(strip=True)
                        # Create clean version
                        text_without_citations = self.clean_text_without_citations(str(li))
                        content.append({
                            'type': 'ol',
                            'text': text_without_citations
                        })
                        
                        # Create version with citations
                        text_with_citations = self.format_text_with_citations(str(li))
                        content_with_citations.append({
                            'type': 'ol',
                            'text': text_with_citations
                        })
                elif "unordered_ev4ae" in element.get('class', []):
                    # Handle list
                    for li in element.find_all('li'):
                        text = li.get_text(strip=True)
                        # Create clean version
                        text_without_citations = self.clean_text_without_citations(str(li))
                        content.append({
                            'type': 'ul',
                            'text': text_without_citations
                        })  
                        # Create version with citations
                        text_with_citations = self.format_text_with_citations(str(li))
                        content_with_citations.append({
                            'type': 'ul',
                            'text': text_with_citations
                        })
                elif "table" in element.get('data-module-type', []):
                    # Handle table
                    table_data = self.extract_table(element)
                    # Create a version without citations
                    table_data_without_citations = {
                        'headers': table_data['headers'],
                        'rows': []
                    }
                    for row in table_data['rows']:
                        row_without_citations = []
                        for cell in row:
                            cell_without_citations = self.clean_text_without_citations(str(cell))
                            row_without_citations.append(cell_without_citations)
                        table_data_without_citations['rows'].append(row_without_citations)
                    content.append({
                        'type': 'table',
                        'text': table_data_without_citations
                    })
                    # Create version with citations 
                    table_data_with_citations = {
                        'headers': table_data['headers'],
                        'rows': []
                    }
                    for row in table_data['rows']:
                        row_with_citations = []
                        for cell in row:
                            cell_with_citations = self.format_text_with_citations(str(cell))
                            row_with_citations.append(cell_with_citations)
                        table_data_with_citations['rows'].append(row_with_citations)
                    content_with_citations.append({
                        'type': 'table',
                        'text': table_data_with_citations
                    })
        
        return {
            'clean': content,
            'with_citations': content_with_citations,
        }

    def extract_references(self, soup):
        """Extract references section from the HTML"""
        references = []
        
        # Look for a div with classname that starts with lemmaReference
        logging.info("Looking for references section with classname that starts with 'lemmaReference'")
        print("Looking for references section...")
        
        # Use CSS selector to find div with class that starts with lemmaReference
        ref_div = soup.find('div', class_=lambda x: x and x.startswith('lemmaReference'))
        
        if ref_div:
            logging.info(f"Found references section with class: {ref_div.get('class')}")
            print(f"Found references section with class: {ref_div.get('class')}")
                        
            # Try finding a ul with class that starts with referenceList
            ref_list = ref_div.find('ul', class_=lambda x: x and x.startswith('referenceList'))
            
            # If not found, try any ul inside the reference div
            if not ref_list:
                ref_list = ref_div.find('ul')
            
            # If still not found, use the div itself (may contain direct li elements)
            if not ref_list:
                ref_list = ref_div
                
            if ref_list:
                ref_items = ref_list.find_all('li')
                
                if not ref_items:
                    # If no li items found directly, try other elements
                    ref_items = ref_list.find_all(['p', 'div', 'span'], class_=lambda x: x and ('reference' in x.lower()))
                
                for i, ref_item in enumerate(ref_items, 1):
                    try:
                        # Extract title and URL if available
                        # find the a tag with class that starts with refLink
                        ref_link = ref_item.find('a', class_=lambda x: x and x.startswith('refLink'))
                        ref_url = ref_link.get('href') if ref_link else ""
                        ref_text = ref_link.get_text(strip=True) if ref_link else ""
                        
                        # find a span in ref_item that has text that starts with [引用日期
                        ref_date = ref_item.find('span', string=lambda x: x and x.startswith(' [引用日期'))
                        # get the date from the span
                        ref_date_text = ref_date.get_text(strip=True) if ref_date else ""
                        # remove the [引用日期 from the date text
                        ref_date_text = ref_date_text.replace('[', '').strip()
                        # remove 引用日期 from the date text
                        ref_date_text = ref_date_text.replace('引用日期', '').strip()
                        # remove the ] from the date text
                        ref_date_text = ref_date_text.replace(']', '').strip()

                        # Additional checks for URL formatting
                        if ref_url and not (ref_url.startswith('http://') or ref_url.startswith('https://')):
                            if ref_url.startswith('//'):
                                ref_url = 'https:' + ref_url
                            elif ref_url.startswith('/'):
                                ref_url = 'https://baike.baidu.com' + ref_url
                        
                        references.append({
                            'id': str(i),
                            'title': ref_text,
                            'url': ref_url,
                            'ref_date': ref_date_text
                        })
                        logging.info(f"Extracted reference {i}: {ref_text[:50]}...")
                    except Exception as e:
                        logging.error(f"Error extracting reference {i}: {str(e)}")
                
                if references:
                    print(f"Successfully extracted {len(references)} references")
            else:
                logging.warning("Reference list not found inside reference div")
                print("Reference list not found inside reference section")
        else:
            logging.warning("References section not found in the HTML")
            print("References section not found in the page")
        
        # If no references were found but there are citation numbers in the text,
        # we can try to extract them from the citations themselves
        if not references:
            try:
                print("Trying to extract references from citation numbers...")
                # Find all sup elements which typically contain citation numbers
                all_sups = soup.find_all('sup')
                citation_numbers = set()
                
                for sup in all_sups:
                    # Try to extract the citation number
                    citation_text = sup.get_text(strip=True)
                    # Look for patterns like [1], [2-3], etc.
                    match = re.search(r'\[(\d+)(?:-(\d+))?\]', citation_text)
                    if match:
                        if match.group(2):  # Range citation [x-y]
                            start, end = int(match.group(1)), int(match.group(2))
                            for num in range(start, end + 1):
                                citation_numbers.add(num)
                        else:  # Single citation [x]
                            citation_numbers.add(int(match.group(1)))
                
                # Create placeholder references for the citation numbers
                for i, num in enumerate(sorted(citation_numbers)):
                    references.append({
                        'id': str(num),
                        'title': f'Reference {num}',
                        'url': ''
                    })
                
                if references:
                    logging.info(f"Created {len(references)} placeholder references from citation numbers")
                    print(f"Created {len(references)} placeholder references from citation numbers")
            except Exception as e:
                logging.error(f"Error creating placeholder references: {str(e)}")
                print(f"Error creating placeholder references: {str(e)}")
        
        return references

    def create_output_folder(self, url):
        """Create a folder for this specific scrape"""
        # Extract page name from URL
        page_name = url.split('/')[-1]
        
        # Create timestamp for unique folder
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create folder with page name and timestamp
        folder_name = f"{page_name}_{timestamp}"
        folder_path = self.output_dir / folder_name
        folder_path.mkdir(exist_ok=True)
        
        logging.info(f"Created output folder: {folder_path}")
        return folder_path

    def save_raw_html(self, html_content, folder_path):
        """Save the raw HTML content"""
        html_path = folder_path / "raw.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"Saved raw HTML to: {html_path}")

    def generate_markdown_content(self, data):
        """Generate markdown content from structured data for JSON output"""
        md_content = ""
        md_content_with_citations = ""
        
        # Title
        md_content += f"# {data['title']}\n\n"
        md_content_with_citations += f"# {data['title']}\n\n"
        
        # Short description
        if data['short_description']:
            md_content += f"{data['short_description']}\n\n"
            md_content_with_citations += f"{data['short_description']}\n\n"
        
        # Abstract
        if data['abstract']['clean']:
            md_content += "## Abstract\n\n"
            md_content += f"{data['abstract']['clean']}\n\n"
            
            md_content_with_citations += "## Abstract\n\n"
            md_content_with_citations += f"{data['abstract']['with_citations']}\n\n"
        
        # Info box
        if data['info_box']['clean']:
            md_content += "## Information\n\n"
            for key, value in data['info_box']['clean'].items():
                md_content += f"**{key}**: {value}\n"
            md_content += "\n"
            
            md_content_with_citations += "## Information\n\n"
            for key, value in data['info_box']['with_citations'].items():
                md_content_with_citations += f"**{key}**: {value}\n"
            md_content_with_citations += "\n"
        
        # Table of contents
        if data['toc']:
            md_content += "## Table of Contents\n\n"
            for item in data['toc']:
                indent = "  " * (item['level'] - 1)
                md_content += f"{indent}- {item['text']}\n"
            md_content += "\n"
            
            md_content_with_citations += "## Table of Contents\n\n"
            for item in data['toc']:
                indent = "  " * (item['level'] - 1)
                md_content_with_citations += f"{indent}- {item['text']}\n"
            md_content_with_citations += "\n"
        
        # Helper function to render a table in markdown
        def render_table_markdown(table):
            table_md = ""
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            # Create markdown table
            if headers:
                # Create header row
                table_md += "| " + " | ".join(headers) + " |\n"
                
                # Create separator row
                table_md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                
                # Create data rows
                for row in rows:
                    # Ensure row has the same number of columns as headers
                    while len(row) < len(headers):
                        row.append("")
                        
                    # Truncate row if it's longer than headers
                    if len(row) > len(headers):
                        row = row[:len(headers)]
                        
                    table_md += "| " + " | ".join(row) + " |\n"
            else:
                # No headers, just output the data rows
                if rows:
                    # Determine the number of columns from the first row
                    num_cols = len(rows[0]) if rows else 0
                    
                    if num_cols > 0:
                        # Create header separator row (empty headers)
                        table_md += "| " + " | ".join([""] * num_cols) + " |\n"
                        table_md += "| " + " | ".join(["---"] * num_cols) + " |\n"
                        
                        # Create data rows
                        for row in rows:
                            # Ensure row has the same number of columns
                            while len(row) < num_cols:
                                row.append("")
                                
                            # Truncate row if it's longer
                            if len(row) > num_cols:
                                row = row[:num_cols]
                                
                            table_md += "| " + " | ".join(row) + " |\n"
                    else:
                        table_md += "*Empty table*\n\n"
                else:
                    table_md += "*Empty table*\n\n"
            
            table_md += "\n"
            return table_md
        
        # Main content - including inline tables
        if data['content']['clean']:
            md_content += "## Content\n\n"
            for item in data['content']['clean']:
                if item['type'].startswith('h'):
                    md_content += f"{'#' * int(item['type'][1:])} {item['text']}\n\n"
                elif item['type'] == 'ol':
                    # Extract the numbering from the text and then remove it from the text
                    match = re.match(r'^(\d+)\.(.*)', item['text'])
                    if match:
                        numbering = match.group(1)
                        text_without_number = match.group(2)
                        md_content += f"{numbering}. {text_without_number}\n\n"                    
                elif item['type'] == 'ul':
                    md_content += f"- {item['text']}\n\n"
                elif item['type'] == 'table':
                    # Directly render the table data that's embedded in the content
                    table_data = item.get('text', {})
                    if table_data and (table_data.get('headers') or table_data.get('rows')):
                        md_content += "**Table:**\n\n"
                        md_content += render_table_markdown(table_data)
                    else:
                        md_content += "*Empty table*\n\n"
                else:
                    md_content += f"{item['text']}\n\n"
            
            md_content_with_citations += "## Content\n\n"
            
            for item in data['content']['with_citations']:
                if item['type'].startswith('h'):
                    md_content_with_citations += f"{'#' * int(item['type'][1:])} {item['text']}\n\n"
                elif item['type'] == 'ol':
                    # Extract the numbering from the text and then remove it from the text
                    match = re.match(r'^(\d+)\.(.*)', item['text'])
                    if match:
                        numbering = match.group(1)
                        text_without_number = match.group(2)
                        md_content_with_citations += f"{numbering}. {text_without_number}\n\n"
                elif item['type'] == 'ul':
                    md_content_with_citations += f"- {item['text']}\n\n"
                elif item['type'] == 'table':
                    # Directly render the table data that's embedded in the content
                    table_data = item.get('text', {})
                    if table_data and (table_data.get('headers') or table_data.get('rows')):
                        md_content_with_citations += "**Table:**\n\n"
                        md_content_with_citations += render_table_markdown(table_data)
                    else:
                        md_content_with_citations += "*Empty table*\n\n"
                else:
                    md_content_with_citations += f"{item['text']}\n\n"
        
        # References
        if data['references']:
            md_content += "## References\n\n"
            for ref in data['references']:
                ref_id = ref.get('id', '')
                ref_title = ref.get('title', '')
                ref_url = ref.get('url', '')
                ref_date = ref.get('ref_date', '')

                ref_date_string = f" (引用日期：{ref_date})" if ref_date else ""

                if ref_url:
                    md_content += f"{ref_id}. [{ref_title}]({ref_url}){ref_date_string}\n"
                else:
                    md_content += f"{ref_id}. {ref_title} {ref_date_string}\n"
                
            md_content_with_citations += "## References\n\n"
            for ref in data['references']:
                ref_id = ref.get('id', '')
                ref_title = ref.get('title', '')
                ref_url = ref.get('url', '')
                ref_date = ref.get('ref_date', '')
                
                ref_date_string = f" (引用日期：{ref_date})" if ref_date else ""

                if ref_url:
                    md_content_with_citations += f"{ref_id}. [{ref_title}]({ref_url}){ref_date_string}\n"
                else:
                    md_content_with_citations += f"{ref_id}. {ref_title} {ref_date_string}\n"
                
        return {
            'clean': md_content,
            'with_citations': md_content_with_citations
        }
    
    def scrape_multiple_pages(self, urls):
        """Scrape multiple Baidu Baike pages"""
        results = []
        total_urls = len(urls)
        
        print(f"\nStarting to scrape {total_urls} pages in sequence")
        print("=" * 50)
        
        for i, url in enumerate(urls):
            print(f"\n[{i+1}/{total_urls}] Processing URL: {url}")
            print("-" * 50)
            start_time = time.time()
            
            data = self.scrape_page(url)
            
            if data:
                results.append(data)
                elapsed_time = time.time() - start_time
                print(f"✅ Successfully scraped: {data['title']}")
                print(f"⏱️ Time taken: {elapsed_time:.2f} seconds")
            else:
                print(f"❌ Failed to scrape URL: {url}")
            
            # Add some spacing between pages
            print("-" * 50)
            
            # If we have more pages to scrape, add a short delay
            if i < total_urls - 1:
                delay = 3  # seconds
                print(f"Waiting {delay} seconds before next page...")
                time.sleep(delay)
        
        successful = len(results)
        print(f"\nCompleted scraping {successful}/{total_urls} pages successfully")
        
        return results
    
    def export_to_excel(self, data_list, output_path):
        """Export data to Excel format"""
        # Create a list to hold flattened data
        flattened_data = []
        
        for data in data_list:
            # Flatten info_box
            info_box = {}
            if data.get('info_box', {}).get('clean'):
                for key, value in data['info_box']['clean'].items():
                    info_box[f"info_{key}"] = value
            
            # Create a flattened entry
            entry = {
                'url': data.get('url', ''),
                'title': data.get('title', ''),
                'short_description': data.get('short_description', ''),
                'abstract': data.get('abstract', {}).get('clean', ''),
                **info_box,  # Add all info box items
                'reference_count': len(data.get('references', []))
            }
            
            flattened_data.append(entry)
        
        # Convert to DataFrame and save
        df = pd.DataFrame(flattened_data)
        df.to_excel(output_path, index=False)
        logging.info(f"Exported data to Excel: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Baidu Baike Selenium Scraper (Visible Browser Mode)')
    parser.add_argument('urls', nargs='*', help='URLs of Baidu Baike pages to scrape')
    parser.add_argument('-f', '--file', help='File containing URLs to scrape (one URL per line)')
    parser.add_argument('--output', default='output', help='Output directory')
    parser.add_argument('--excel', help='Export data to Excel file')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("Baidu Baike Scraper - VISIBLE BROWSER MODE")
    print("="*80)
    print("This scraper will open Chrome browser windows to scrape Baidu Baike pages.")
    print("You will be able to see the scraping process in real-time.")
    print("="*80 + "\n")
    
    # Get URLs from command line arguments and/or file
    all_urls = []
    
    # Add URLs from command line arguments
    if args.urls:
        logging.info(f"Adding {len(args.urls)} URLs from command line arguments")
        print(f"Will scrape {len(args.urls)} URLs from command line arguments")
        all_urls.extend(args.urls)
    
    # Add URLs from file if specified
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                file_urls = [line.strip() for line in f if line.strip()]
                logging.info(f"Adding {len(file_urls)} URLs from file {args.file}")
                print(f"Will scrape {len(file_urls)} URLs from file: {args.file}")
                all_urls.extend(file_urls)
        except Exception as e:
            logging.error(f"Error reading URL file {args.file}: {str(e)}")
            print(f"Error reading URL file {args.file}: {str(e)}")
    
    # Use default URLs if none provided
    if not all_urls:
        default_urls = [
            "https://baike.baidu.com/item/华为技术有限公司/6455903",
            # Add more default URLs here as needed
        ]
        logging.info(f"No URLs provided, using {len(default_urls)} default URLs")
        print(f"No URLs provided, using default URL: {default_urls[0]}")
        all_urls = default_urls
    
    # Log URLs to be processed
    logging.info(f"Will process {len(all_urls)} URLs:")
    print(f"\nPreparing to scrape {len(all_urls)} URLs:")
    for i, url in enumerate(all_urls):
        logging.info(f"  URL {i+1}: {url}")
        print(f"  {i+1}. {url}")
    
    print("\nOutput will be saved to:", args.output)
    print("\nStarting the scraper with visible Chrome browser...\n")
    
    # Create scraper
    scraper = BaiduBaikeSeleniumScraper(output_dir=args.output)
    
    # Scrape pages
    results = scraper.scrape_multiple_pages(all_urls)
    
    # Export to Excel if requested
    if args.excel:
        print(f"\nExporting data to Excel file: {args.excel}")
        scraper.export_to_excel(results, args.excel)
        print(f"Excel export completed: {args.excel}")
    
    logging.info(f"Scraped {len(results)} pages successfully!")
    print(f"\n✅ Successfully scraped {len(results)} out of {len(all_urls)} pages!")
    print(f"All data has been saved to: {args.output}")
    print("\nThank you for using the Baidu Baike Scraper!")

if __name__ == "__main__":
    main() 