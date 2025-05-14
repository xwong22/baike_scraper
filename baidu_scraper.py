import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import json
from pathlib import Path
import re
import datetime
import os
import argparse
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

class BaiduBaikeScraper:
    def __init__(self):
        self.base_url = "https://baike.baidu.com"
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 11.5; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
        ]
        self.session = requests.Session()
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        logging.info("BaiduBaikeScraper initialized")

    def get_headers(self):
        """Generate random headers to mimic human behavior"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def random_sleep(self):
        """Sleep for a random time to mimic human behavior"""
        sleep_time = random.uniform(2, 5)
        logging.info(f"Sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)

    def get_page(self, url):
        """Get page content with error handling and retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, headers=self.get_headers(), timeout=10)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                self.random_sleep()

    def clean_text_without_citations(self, text):
        """Remove citation tags from text"""
        if not text:
            return ""
        # Use BeautifulSoup to parse the HTML and remove sup tags
        soup = BeautifulSoup(f"<div>{text}</div>", 'html.parser')
        for sup in soup.find_all('sup'):
            sup.decompose()
        return soup.div.get_text(strip=True)
    
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
                toc.append({
                    'level': level,
                    'text': text
                })
        return toc

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
        
        return {
            'clean': content,
            'with_citations': content_with_citations
        }

    def extract_references(self, soup):
        """Extract references section from the HTML"""
        references = []
        
        # Check for the references section using the class from the image
        ref_div = soup.find('div', class_='lemmaReference_Dc3xe')
        if ref_div:
            logging.info("Found references section")
            ref_list = ref_div.find('ul', class_='referenceList_Qc5h3')
            if ref_list:
                ref_items = ref_list.find_all('li')
                for i, ref_item in enumerate(ref_items, 1):
                    ref_text = ref_item.get_text(strip=True)
                    # Extract title and URL if available
                    ref_link = ref_item.find('a')
                    ref_url = ref_link.get('href') if ref_link else ""
                    
                    references.append({
                        'id': str(i),
                        'title': ref_text,
                        'url': ref_url
                    })

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
        
        # Main content
        if data['content']['clean']:
            md_content += "## Content\n\n"
            for item in data['content']['clean']:
                if item['type'].startswith('h'):
                    md_content += f"{'#' * int(item['type'][1:])} {item['text']}\n\n"
                elif item['type'] == 'ol':
                    # Extract the numbering from the text and then remove it from the text
                    match = re.match(r'^(\d+)\.(.*)', item['text'])
                    print(f"match: {match}")
                    if match:
                        numbering = match.group(1)
                        text_without_number = match.group(2)
                        md_content += f"{numbering}. {text_without_number}\n\n"                    
                elif item['type'] == 'ul':
                    md_content += f"- {item['text']}\n\n"
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
                else:
                    md_content_with_citations += f"{item['text']}\n\n"
        
        # References
        if data['references']:
            md_content += "## References\n\n"
            for ref in data['references']:
                ref_id = ref.get('id', '')
                ref_title = ref.get('title', '')
                ref_url = ref.get('url', '')
                
                if ref_url:
                    md_content += f"{ref_id}. [{ref_title}]({ref_url})\n"
                else:
                    md_content += f"{ref_id}. {ref_title}\n"
                
            md_content_with_citations += "## References\n\n"
            for ref in data['references']:
                ref_id = ref.get('id', '')
                ref_title = ref.get('title', '')
                ref_url = ref.get('url', '')
                
                if ref_url:
                    md_content_with_citations += f"{ref_id}. [{ref_title}]({ref_url})\n"
                else:
                    md_content_with_citations += f"{ref_id}. {ref_title}\n"
                
        return {
            'clean': md_content,
            'with_citations': md_content_with_citations
        }

    def save_to_markdown(self, data, folder_path):
        """Save scraped data to markdown format"""
        # Save clean version
        md_path = folder_path / "content.md"
        md_content = self.generate_markdown_content(data)['clean']
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        # Save version with citations
        md_with_citations_path = folder_path / "content_with_citations.md"
        md_content_with_citations = self.generate_markdown_content(data)['with_citations']
        
        with open(md_with_citations_path, 'w', encoding='utf-8') as f:
            f.write(md_content_with_citations)
            
        logging.info(f"Saved markdown files: {md_path} and {md_with_citations_path}")

    def save_to_json(self, data, folder_path):
        """Save scraped data to JSON format"""
        json_path = folder_path / "data.json"
        
        # Add markdown formatted content to JSON
        data_with_md = data.copy()
        md_content = self.generate_markdown_content(data)
        data_with_md['markdown_content'] = {
            'clean': md_content['clean'],
            'with_citations': md_content['with_citations']
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data_with_md, f, ensure_ascii=False, indent=2)
            
        logging.info(f"Saved JSON data to: {json_path}")

    def scrape_page(self, url):
        """Main method to scrape a Baidu Baike page"""
        logging.info(f"Scraping page: {url}")
        
        # Get HTML content
        html = self.get_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Create output folder for this scrape
        folder_path = self.create_output_folder(url)
        
        # Save raw HTML
        self.save_raw_html(html, folder_path)

        # Extract all required information
        title_element = soup.find('h1', class_='J-lemma-title')
        short_desc_element = soup.find('div', class_='lemmaDescText_nFmCD')
        
        data = {
            'title': title_element.get_text(strip=True) if title_element else '',
            'short_description': short_desc_element.get_text(strip=True) if short_desc_element else '',
            'abstract': self.extract_abstract(soup),
            'info_box': self.extract_info_box(soup),
            'toc': self.extract_toc(soup),
            'content': self.extract_content(soup),
            'references': self.extract_references(soup)
        }

        # Save to markdown and JSON
        self.save_to_markdown(data, folder_path)
        self.save_to_json(data, folder_path)
        
        self.random_sleep()
        return data

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape content from Baidu Baike')
    parser.add_argument('urls', nargs='*', help='URLs to scrape (space-separated)')
    parser.add_argument('-f', '--file', help='File containing URLs to scrape (one URL per line)')
    args = parser.parse_args()
    
    # Get URLs from arguments or use defaults
    urls = []
    
    # Add URLs from command line arguments
    if args.urls:
        urls.extend(args.urls)
    
    # Add URLs from file if specified
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                file_urls = [line.strip() for line in f if line.strip()]
                urls.extend(file_urls)
        except Exception as e:
            logging.error(f"Error reading URL file {args.file}: {str(e)}")
            sys.exit(1)
    
    # Use default URLs if none provided
    if not urls:
        urls = [
            "https://baike.baidu.com/item/华为技术有限公司/6455903",
            # Add more default URLs here as needed
        ]
    
    # Log the URLs to be processed
    logging.info(f"Will process {len(urls)} URLs")
    for i, url in enumerate(urls):
        logging.info(f"URL {i+1}: {url}")
    
    # Create scraper and process URLs
    scraper = BaiduBaikeScraper()
    for url in urls:
        try:
            logging.info(f"\n{'='*50}")
            logging.info(f"Processing URL: {url}")
            scraper.scrape_page(url)
            logging.info(f"Successfully scraped: {url}")
        except Exception as e:
            logging.error(f"Error scraping URL {url}: {str(e)}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            
        # Add an extra sleep between different URLs to be extra careful
        if urls.index(url) < len(urls) - 1:  # Don't sleep after last URL
            sleep_time = random.uniform(5, 10)
            logging.info(f"Sleeping for {sleep_time:.2f} seconds before next URL")
            time.sleep(sleep_time)

if __name__ == "__main__":
    main() 