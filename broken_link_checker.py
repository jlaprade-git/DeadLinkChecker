def should_crawl_url(self, url: str) -> bool:
        """Check if URL should be crawled based on exclusion patterns."""
        import re
        
        # Must be from the same domain
        start_domain = urlparse(self.config['start_url']).netloc
        url_domain = urlparse(url).netloc
        
        if url_domain != start_domain:
            return False
        
        # Use the should_check_url function for consistency
        return self.should_check_url(url)#!/usr/bin/env python3
"""
Website Broken Link Checker
Crawls a website to find broken links and sends email reports.
Designed for basic websites with configurable exclusions
"""

import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from datetime import datetime
import logging
import argparse
import json
import os
from typing import Set, List, Dict, Tuple
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class BrokenLinkChecker:
    def __init__(self, config_file: str = "link_checker_config.json"):
        """Initialize the broken link checker with configuration."""
        self.config = self.load_config(config_file)
        self.visited_urls: Set[str] = set()
        self.broken_links: List[Dict] = []
        self.checked_external_links: Set[str] = set()
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.get('log_level', 'INFO')),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('link_checker.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Setup session with retries and connection pooling
        self.session = requests.Session()
        
        # Configure connection pooling to prevent "connection pool is full" warnings
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,      # Max connections per pool
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504]
            )
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set user agent to look like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file or create default."""
        default_config = {
            "start_url": "https://www.SomeWebsiteOrSomething.com",
            "exclude_patterns": [
                ".*admin.*"
            ],
            "include_external_links": True,
            "max_workers": 3,
            "delay_between_requests": 1,
            "timeout": 30,
            "log_level": "INFO",
            "email": {
                "enabled": True,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "from_email": "your_email@gmail.com",
                "from_password": "your_app_password",
                "to_emails": ["your_email@gmail.com"],
                "subject": "Broken Links Report for {domain}"
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                self.logger.warning(f"Error loading config: {e}. Using defaults.")
        else:
            # Create default config file
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            self.logger.info(f"Created default config file: {config_file}")
        
        return default_config

    def should_check_url(self, url: str) -> bool:
        """Check if URL should be checked for broken links (more aggressive filtering)."""
        import re
        
        # Check link-specific exclusion patterns (more aggressive)
        for pattern in self.config.get('exclude_link_check_patterns', []):
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # Check general exclusion patterns
        for pattern in self.config['exclude_patterns']:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True

    def should_crawl_url(self, url: str) -> bool:
        """Check if URL should be crawled for more pages (less aggressive - only basic exclusions)."""
        import re
        
        # Must be from the same domain
        start_domain = urlparse(self.config['start_url']).netloc
        url_domain = urlparse(url).netloc
        
        if url_domain != start_domain:
            return False
        
        # Only check basic exclusion patterns for crawling (not the aggressive problematic patterns)
        for pattern in self.config['exclude_patterns']:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True

    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and converting to lowercase."""
        parsed = urlparse(url)
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized

    def check_link(self, url: str, source_page: str) -> Tuple[bool, str, int]:
        """Check if a single link is working."""
        try:
            print(f"    Checking: {url}")
            response = self.session.get(url, timeout=self.config['timeout'], allow_redirects=True)
            status = "✅ OK" if response.status_code < 400 else "❌ BROKEN"
            print(f"    {status} [{response.status_code}] {url}")
            return response.status_code < 400, response.reason, response.status_code
        except requests.exceptions.RequestException as e:
            print(f"    ❌ ERROR [0] {url} - {str(e)}")
            return False, str(e), 0

    def extract_links(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """Extract all links from HTML content with their text/descriptions."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Find all anchor tags with href
        for tag in soup.find_all('a', href=True):
            href = tag.get('href')
            if href:
                absolute_url = urljoin(base_url, href)
                # Get the link text, handling nested tags
                link_text = tag.get_text(strip=True) or "[No text]"
                # Get title attribute if available
                title = tag.get('title', '')
                
                links.append({
                    'url': absolute_url,
                    'text': link_text[:100],  # Limit to 100 chars
                    'title': title[:100] if title else '',
                    'type': 'link'
                })
        
        # Find all link tags with href (stylesheets, etc.)
        for tag in soup.find_all('link', href=True):
            href = tag.get('href')
            if href:
                absolute_url = urljoin(base_url, href)
                rel = tag.get('rel', [''])[0] if tag.get('rel') else ''
                
                links.append({
                    'url': absolute_url,
                    'text': f"[{rel} stylesheet]" if rel else "[stylesheet]",
                    'title': '',
                    'type': 'stylesheet'
                })
        
        # Find all image tags with src
        for tag in soup.find_all('img', src=True):
            src = tag.get('src')
            if src:
                absolute_url = urljoin(base_url, src)
                alt_text = tag.get('alt', '')
                title = tag.get('title', '')
                
                links.append({
                    'url': absolute_url,
                    'text': f"[IMG: {alt_text}]" if alt_text else "[Image]",
                    'title': title[:100] if title else '',
                    'type': 'image'
                })
        
        print(f"  Found {len(links)} links on this page")
        return links

    def crawl_page(self, url: str) -> List[Dict[str, str]]:
        """Crawl a single page and return list of links found."""
        try:
            print(f"  📄 Fetching page content...")
            response = self.session.get(url, timeout=self.config['timeout'])
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' in content_type:
                    print(f"  ✅ Page loaded successfully [{response.status_code}]")
                    return self.extract_links(response.text, url)
                else:
                    print(f"  ⚠️  Not an HTML page (content-type: {content_type})")
            else:
                print(f"  ❌ Page failed to load [{response.status_code}]")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error crawling {url}: {e}")
            print(f"  ❌ Error fetching page: {e}")
            return []

    def check_links_on_page(self, page_url: str, links: List[Dict[str, str]]):
        """Check all links found on a specific page."""
        start_domain = urlparse(self.config['start_url']).netloc
        
        print(f"\n  🔍 Checking {len(links)} links found on this page...")
        
        # Filter links to check
        links_to_check = []
        skipped_count = 0
        
        for link_data in links:
            link_url = link_data['url']
            link_domain = urlparse(link_url).netloc
            
            # Skip if we shouldn't check this URL (problematic patterns)
            if not self.should_check_url(link_url):
                skipped_count += 1
                continue
            
            # Skip if external link and we don't want to check them
            if link_domain != start_domain and not self.config['include_external_links']:
                skipped_count += 1
                continue
            
            # Skip if we've already checked this external link
            if link_domain != start_domain and link_url in self.checked_external_links:
                skipped_count += 1
                continue
            
            if link_domain != start_domain:
                self.checked_external_links.add(link_url)
            
            links_to_check.append(link_data)
        
        if skipped_count > 0:
            print(f"  ⏭️  Skipping {skipped_count} links (duplicates or excluded)")
        
        print(f"  🔍 Checking {len(links_to_check)} unique links...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
            future_to_link = {}
            
            for link_data in links_to_check:
                future = executor.submit(self.check_link, link_data['url'], page_url)
                future_to_link[future] = link_data
            
            for future in concurrent.futures.as_completed(future_to_link):
                link_data = future_to_link[future]
                link_url = link_data['url']
                try:
                    is_working, reason, status_code = future.result()
                    if not is_working:
                        self.broken_links.append({
                            'source_page': page_url,
                            'broken_link': link_url,
                            'link_text': link_data['text'],
                            'link_title': link_data['title'],
                            'link_type_html': link_data['type'],
                            'status_code': status_code,
                            'error': reason,
                            'link_type': 'internal' if urlparse(link_url).netloc == start_domain else 'external',
                            'timestamp': datetime.now().isoformat()
                        })
                        print(f"  💥 BROKEN LINK: \"{link_data['text']}\" → {link_url} (Status: {status_code})")
                except Exception as e:
                    self.logger.error(f"Error checking link {link_url}: {e}")
                    print(f"  ⚠️  Error checking {link_url}: {e}")
                
                # Add delay between requests
                time.sleep(self.config['delay_between_requests'])
        
        print(f"  ✅ Finished checking links on this page")

    def crawl_website(self):
        """Main crawling method."""
        start_url = self.config['start_url']
        urls_to_crawl = [start_url]
        
        print(f"\n🚀 Starting crawl of {start_url}")
        print(f"📊 Configuration:")
        print(f"   • Include external links: {self.config['include_external_links']}")
        print(f"   • Max workers: {self.config['max_workers']}")
        print(f"   • Delay between requests: {self.config['delay_between_requests']}s")
        print(f"   • Exclude patterns: {', '.join(self.config['exclude_patterns'])}")
        print(f"\n" + "="*80)
        
        page_count = 0
        
        while urls_to_crawl:
            current_url = urls_to_crawl.pop(0)
            normalized_url = self.normalize_url(current_url)
            
            if normalized_url in self.visited_urls:
                continue
            
            if not self.should_crawl_url(current_url):
                print(f"⏭️  Skipping excluded URL: {current_url}")
                continue
            
            self.visited_urls.add(normalized_url)
            page_count += 1
            
            print(f"\n📄 [{page_count}] Crawling: {current_url}")
            
            # Get all links on this page
            links = self.crawl_page(current_url)
            
            if links:
                # Check all links found on this page
                self.check_links_on_page(current_url, links)
                
                # Add internal links to crawl queue
                new_pages_found = 0
                for link_data in links:
                    link_url = link_data['url']
                    if self.should_crawl_url(link_url):
                        normalized_link = self.normalize_url(link_url)
                        if normalized_link not in self.visited_urls:
                            urls_to_crawl.append(link_url)
                            new_pages_found += 1
                
                if new_pages_found > 0:
                    print(f"  📋 Added {new_pages_found} new pages to crawl queue")
                    print(f"  📊 Queue status: {len(urls_to_crawl)} pages remaining")
            
            print(f"  💤 Waiting {self.config['delay_between_requests']}s before next page...")
            time.sleep(self.config['delay_between_requests'])
        
        print(f"\n🏁 Crawling complete!")
        print(f"📊 Final statistics:")
        print(f"   • Pages crawled: {len(self.visited_urls)}")
        print(f"   • Broken links found: {len(self.broken_links)}")
        print(f"   • External links checked: {len(self.checked_external_links)}")
        
        if self.broken_links:
            print(f"\n💥 Broken links summary:")
            for i, link in enumerate(self.broken_links, 1):
                print(f"   {i}. \"{link['link_text']}\" → {link['broken_link']} [{link['status_code']}]")
                print(f"      Found on: {link['source_page']}")
        else:
            print(f"\n✅ No broken links found! Your website looks great!")
            
        print("="*80)

    def generate_report(self) -> str:
        """Generate HTML report."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Generate HTML report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Broken Links Report - {urlparse(self.config['start_url']).netloc}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .external {{ background-color: #fff3cd; }}
                .internal {{ background-color: #f8d7da; }}
                .error {{ color: #721c24; }}
                .link-text {{ font-weight: bold; color: #0066cc; }}
                .success {{ color: #28a745; font-size: 1.2em; }}
            </style>
        </head>
        <body>
            <h1>Broken Links Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Website:</strong> {self.config['start_url']}</p>
                <p><strong>Scan Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p><strong>Pages Crawled:</strong> {len(self.visited_urls)}</p>
                <p><strong>Broken Links Found:</strong> {len(self.broken_links)}</p>
                <p><strong>Internal Broken Links:</strong> {len([l for l in self.broken_links if l['link_type'] == 'internal'])}</p>
                <p><strong>External Broken Links:</strong> {len([l for l in self.broken_links if l['link_type'] == 'external'])}</p>
            </div>
        """
        
        if self.broken_links:
            html_content += """
            <h2>Broken Links Details</h2>
            <table>
                <tr>
                    <th>Source Page</th>
                    <th>Link Text</th>
                    <th>Broken Link</th>
                    <th>Status Code</th>
                    <th>Error</th>
                    <th>Type</th>
                </tr>
            """
            
            for link in self.broken_links:
                css_class = link['link_type']
                # Escape HTML in link text
                link_text = link['link_text'].replace('<', '&lt;').replace('>', '&gt;')
                html_content += f"""
                <tr class="{css_class}">
                    <td><a href="{link['source_page']}" target="_blank">{link['source_page']}</a></td>
                    <td><span class="link-text">"{link_text}"</span><br><small>{link.get('link_title', '')}</small></td>
                    <td class="error">{link['broken_link']}</td>
                    <td>{link['status_code']}</td>
                    <td>{link['error']}</td>
                    <td>{link['link_type'].title()}</td>
                </tr>
                """
            
            html_content += "</table>"
        else:
            html_content += '<h2 class="success">✅ No broken links found!</h2>'
        
        html_content += """
        </body>
        </html>
        """
        
        html_filename = f"broken_links_report_{timestamp}.html"
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_filename

    def send_email_report(self, html_file: str):
        """Send email report with HTML attachment."""
        if not self.config['email']['enabled']:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['email']['from_email']
            msg['To'] = ', '.join(self.config['email']['to_emails'])
            msg['Subject'] = self.config['email']['subject'].format(
                domain=urlparse(self.config['start_url']).netloc
            )
            
            # Email body
            if self.broken_links:
                body = f"""
Broken Links Report for {self.config['start_url']}

Scan completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Pages crawled: {len(self.visited_urls)}
Broken links found: {len(self.broken_links)}

BROKEN LINKS SUMMARY:
{'='*60}

"""
                for i, link in enumerate(self.broken_links, 1):
                    body += f"""
{i}. BROKEN LINK:
   Text: "{link['link_text']}"
   URL: {link['broken_link']}
   Status: {link['status_code']} - {link['error']}
   Found on: {link['source_page']}
   Type: {link['link_type'].title()}
   {'='*60}
"""
                
                body += f"""

Please see the attached HTML report for a detailed, formatted view.

This is an automated report from your website link checker.
                """
            else:
                body = f"""
✅ GREAT NEWS! No broken links found on {self.config['start_url']}

Scan completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Pages crawled: {len(self.visited_urls)}
External links checked: {len(self.checked_external_links)}

Your website's links are all working properly!

This is an automated report from your website link checker.
                """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach HTML report
            with open(html_file, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {html_file}'
                )
                msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.config['email']['smtp_server'], self.config['email']['smtp_port'])
            server.starttls()
            server.login(self.config['email']['from_email'], self.config['email']['from_password'])
            text = msg.as_string()
            server.sendmail(self.config['email']['from_email'], self.config['email']['to_emails'], text)
            server.quit()
            
            self.logger.info("Email report sent successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")

    def run(self):
        """Run the complete link checking process."""
        start_time = datetime.now()
        self.logger.info("Starting broken link check")
        
        try:
            # Crawl website
            self.crawl_website()
            
            # Generate reports
            html_file = self.generate_report()
            
            # Send email if configured
            self.send_email_report(html_file)
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.logger.info(f"Link check completed in {duration}")
            self.logger.info(f"Found {len(self.broken_links)} broken links")
            self.logger.info(f"Report saved: {html_file}")
            
        except KeyboardInterrupt:
            self.logger.info("Link check interrupted by user")
        except Exception as e:
            self.logger.error(f"Error during link check: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Check website for broken links')
    parser.add_argument('--config', default='link_checker_config.json', 
                       help='Configuration file path')
    args = parser.parse_args()
    
    checker = BrokenLinkChecker(args.config)
    checker.run()

if __name__ == "__main__":
    main()
