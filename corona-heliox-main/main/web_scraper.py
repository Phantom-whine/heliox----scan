import requests
from bs4 import BeautifulSoup
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
from urllib.parse import urljoin, urlparse
import time
import logging
from typing import List, Optional, Tuple
import re

class SophisticatedWebScraper:
    def __init__(self, timeout: int = 30, delay: float = 1.0, user_agent: str = None):
        """
        Initialize the web scraper with configurable parameters.
        
        Args:
            timeout: Request timeout in seconds
            delay: Delay between requests to be respectful
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.delay = delay
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        self.session = requests.Session()
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def get_headers(self) -> dict:
        """Return headers for HTTP requests."""
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned and normalized text
        """
        # Remove extra whitespace, newlines, and tabs
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        # Remove common unwanted characters
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        return text
    
    def extract_text_from_soup(self, soup: BeautifulSoup) -> str:
        """
        Extract and clean text from BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Extracted and cleaned text
        """
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()
        
        # Get text from remaining elements
        text = soup.get_text()
        return self.clean_text(text)
    
    def scrape_static(self, url: str) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Scrape static content using requests and BeautifulSoup.
        
        Args:
            url: URL to scrape
            
        Returns:
            Tuple of (text, title, links)
        """
        try:
            self.logger.info(f"Scraping static content from: {url}")
            
            response = self.session.get(
                url, 
                headers=self.get_headers(), 
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else None
            if title:
                title = self.clean_text(title)
            
            # Extract main text content
            text = self.extract_text_from_soup(soup)
            
            # Extract all links
            links = []
            for link in soup.find_all('a', href=True):
                absolute_url = urljoin(url, link['href'])
                if self.is_valid_url(absolute_url):
                    links.append(absolute_url)
            
            # Be respectful - add delay
            time.sleep(self.delay)
            
            return text, title, links
            
        except requests.RequestException as e:
            self.logger.error(f"Error scraping static content from {url}: {e}")
            return None, None, []
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {url}: {e}")
            return None, None, []
    
    async def scrape_dynamic(self, url: str, wait_time: int = 2) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Scrape dynamic content using Playwright.
        
        Args:
            url: URL to scrape
            wait_time: Time to wait for page to load
            
        Returns:
            Tuple of (text, title, links)
        """
        try:
            self.logger.info(f"Scraping dynamic content from: {url}")
            
            if sync_playwright is None:
                return self.scrape_static(url)

            with sync_playwright() as p:
                # Launch browser (headless by default)
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.user_agent)
                page = context.new_page()
                
                # Navigate to page
                page.goto(url, wait_until='domcontentloaded')
                
                # Wait for additional time for JavaScript to execute
                page.wait_for_timeout(wait_time * 1000)
                
                # Wait for network to be mostly idle
                page.wait_for_load_state('networkidle')
                
                # Get page content
                content = page.content()
                
                # Extract title
                title = page.title()
                if title:
                    title = self.clean_text(title)
                
                # Parse with BeautifulSoup for consistent text extraction
                soup = BeautifulSoup(content, 'html.parser')
                text = self.extract_text_from_soup(soup)
                
                # Extract all links
                links = []
                link_elements = page.query_selector_all('a[href]')
                for link_element in link_elements:
                    href = await link_element.get_attribute('href')
                    if href:
                        absolute_url = urljoin(url, href)
                        if self.is_valid_url(absolute_url):
                            links.append(absolute_url)
                
                browser.close()
                
                return text, title, links
                
        except Exception as e:
            self.logger.error(f"Error scraping dynamic content from {url}: {e}")
            return None, None, []
    
    def scrape(
        self, 
        url: str, 
        method: str = 'auto',
        dynamic_wait: int = 2
    ) -> dict:
        """
        Main scraping method.
        
        Args:
            url: URL to scrape
            method: 'static', 'dynamic', or 'auto'
            dynamic_wait: Wait time for dynamic content
            
        Returns:
            Dictionary with scraping results
        """
        if not self.is_valid_url(url):
            return {
                'success': False,
                'error': 'Invalid URL',
                'url': url,
                'text': None,
                'title': None,
                'links': [],
                'method': method
            }
        
        result = {
            'success': False,
            'url': url,
            'text': None,
            'title': None,
            'links': [],
            'method': method,
            'error': None
        }
        
        try:
            if method == 'static':
                text, title, links = self.scrape_static(url)
            elif method == 'dynamic':
                text, title, links = self.scrape_dynamic(url, dynamic_wait)
            else:  # auto - try static first, then dynamic if needed
                text, title, links = self.scrape_static(url)
                if not text or len(text.strip()) < 100:  # If little text, try dynamic
                    self.logger.info("Static content minimal, trying dynamic approach")
                    text, title, links = self.scrape_dynamic(url, dynamic_wait)
                    result['method'] = 'auto(dynamic_fallback)'
            
            result.update({
                'success': text is not None,
                'text': text,
                'title': title,
                'links': links,
                'content_length': len(text) if text else 0
            })
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Error scraping {url}: {e}")
        
        return result

# Example usage and advanced features
class AdvancedWebScraper(SophisticatedWebScraper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def scrape_multiple(self, urls: List[str], method: str = 'auto') -> List[dict]:
        """
        Scrape multiple URLs.
        
        Args:
            urls: List of URLs to scrape
            method: Scraping method to use
            
        Returns:
            List of scraping results
        """
        results = []
        for url in urls:
            result = self.scrape(url, method)
            results.append(result)
            # Respectful delay between requests
            time.sleep(self.delay)
        return results
    
    def extract_metadata(self, text: str) -> dict:
        """
        Extract basic metadata from text.
        
        Args:
            text: Extracted text
            
        Returns:
            Dictionary with metadata
        """
        if not text:
            return {}
        
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        
        return {
            'word_count': len(words),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'avg_sentence_length': len(words) / len(sentences) if sentences else 0,
            'character_count': len(text),
        }

# Usage examples
def main(url):
    """Demonstrate the web scraper usage."""
    
    # Initialize scraper
    scraper = AdvancedWebScraper(delay=1.0)
    
    # Scrape single URL
    print("=== Scraping Single URL ===")
    result = scraper.scrape(url, method='static')

    if result['success']:
        result = f"Title: {result['title']}\n Website text content: {result['text'][:2000]}..."
        print(result)
        return result
    else:
        print(f"Failed to scrape: {result['error']}")
        return None