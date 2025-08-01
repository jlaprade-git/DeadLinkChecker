# Website Broken Link Checker

A Python script that crawls websites to find broken links and sends detailed email reports. Perfect for maintaining website health and SEO.

## Features

- **Comprehensive Crawling**: Recursively crawls all pages on your website
- **Link Validation**: Checks internal links, external links, images, and stylesheets
- **Smart Filtering**: Configurable exclusion patterns for pages and link types
- **Detailed Reports**: Generates HTML reports with link text and source pages
- **Email Notifications**: Automatically sends reports via SMTP
- **Concurrent Processing**: Multi-threaded link checking for speed
- **Browser-like Requests**: Uses realistic user agents to avoid bot blocking

## Installation

1. Clone this repository:
```bash
git clone https://github.com/your-username/broken-link-checker.git
cd broken-link-checker
```

2. Install required dependencies:
```bash
pip install requests beautifulsoup4 lxml
```

## Configuration

Create a `link_checker_config.json` file:

```json
{
  "start_url": "https://your-website.com",
  "exclude_patterns": [
    ".*admin.*",
    ".*login.*"
  ],
  "exclude_link_check_patterns": [
    ".*\\.jpg$",
    ".*\\.png$",
    ".*\\.css$",
    ".*\\.js$"
  ],
  "include_external_links": true,
  "max_workers": 3,
  "delay_between_requests": 1,
  "timeout": 30,
  "log_level": "INFO",
  "email": {
    "enabled": true,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "from_email": "your-email@gmail.com",
    "from_password": "your-app-password",
    "to_emails": ["recipient@example.com"],
    "subject": "Broken Links Report for {domain}"
  }
}
```

## Usage

### Basic Usage
```bash
python broken_link_checker.py
```

### Custom Config File
```bash
python broken_link_checker.py --config my_config.json
```

## Configuration Options

### General Settings
- `start_url`: The website to crawl
- `include_external_links`: Whether to check external links (default: true)
- `max_workers`: Number of concurrent threads (default: 3)
- `delay_between_requests`: Seconds to wait between requests (default: 1)
- `timeout`: Request timeout in seconds (default: 30)

### Exclusion Patterns
- `exclude_patterns`: Regex patterns for pages to skip crawling
- `exclude_link_check_patterns`: Additional patterns for links to skip checking

### Email Settings
- Configure SMTP settings for automated email reports
- Supports Gmail, Office 365, and other SMTP providers
- Reports include both summary and detailed HTML attachment

## Example Output

```
🚀 Starting crawl of https://example.com
📊 Configuration:
   • Include external links: true
   • Max workers: 3
   • Delay between requests: 1s

📄 [1] Crawling: https://example.com
  ✅ Page loaded successfully [200]
  Found 25 links on this page
  🔍 Checking 25 unique links...
    ✅ OK [200] https://example.com/about
    ❌ BROKEN [404] https://example.com/old-page
  💥 BROKEN LINK: "Old News Page" → https://example.com/old-page (Status: 404)

🏁 Crawling complete!
📊 Final statistics:
   • Pages crawled: 15
   • Broken links found: 1
   • External links checked: 8
```

## Email Reports

The script generates comprehensive email reports containing:
- Summary statistics
- List of all broken links with their source pages
- HTML attachment with detailed, formatted results
- Link text to help you quickly identify and fix issues

## Scheduling

### Linux/macOS (Cron)
```bash
# Run every Sunday at 9 AM
0 9 * * 0 cd /path/to/script && python3 broken_link_checker.py
```

### Docker
```bash
docker run --rm \
  -v /path/to/config:/app \
  python:3.9-slim \
  bash -c "cd /app && pip install requests beautifulsoup4 lxml && python broken_link_checker.py"
```

## Common Use Cases

- **SEO Maintenance**: Regular broken link checking for better search rankings
- **Content Auditing**: Ensure all references and citations are still valid
- **Website Migration**: Verify all links work after moving or restructuring
- **Quality Assurance**: Automated testing as part of deployment pipeline

## Troubleshooting

### SSL Certificate Errors
Some sites have SSL issues. Add problematic domains to `exclude_link_check_patterns`:
```json
"exclude_link_check_patterns": [".*problematic-site\\.com.*"]
```

### 403 Forbidden Errors
Some sites block automated requests. The script uses browser-like headers, but you may need to exclude certain domains.

### Rate Limiting
Increase `delay_between_requests` if you encounter rate limiting.

## Contributing

Pull requests are welcome! Please ensure your code follows the existing style and includes appropriate tests.

## License

MIT License - see LICENSE file for details.