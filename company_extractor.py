import re
import json
import asyncio
import aiohttp
import socket
import ssl
import logging
from typing import List, Optional, Dict, Tuple
from collections import Counter
from tqdm import tqdm
from urllib.parse import urlparse
from functools import lru_cache
from bs4 import BeautifulSoup
import html
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('company_extractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
class ExtractionSettings:
    MAX_CONCURRENT_REQUESTS = 10
    REQUEST_TIMEOUT = 15
    USER_AGENT = "Mozilla/5.0 (compatible; CompanyExtractor/1.0; +https://github.com/companyextractor)"
    ACCEPTED_LANGUAGES = "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    RETRY_ATTEMPTS = 3
    MAX_CACHE_SIZE = 1000

# Enhanced company suffixes with regex patterns
COMPANY_SUFFIXES = [
    "GmbH", "UG", "AG", r"e\.?V\.?", "GbR", "Inc", "Ltd", "SAS", "BV", "AB",
    r"S\.?L\.?", "Oy", "KG", "SE", "LLC", "PLC", "Corp", r"Co\.", "Limited", r"S\.?A\.?",
    "NV", r"S\.?p\.?A\.?", "LP", "LLP", r"Pte\.? Ltd\.?", r"S\.?à r\.?l\.?", r"B\.?V\.?", "KGaA"
]

# Common words to ignore in company names
COMMON_WORDS = {
    "the", "and", "for", "with", "our", "your", "from", "this", "that", "about",
    "contact", "home", "privacy", "terms", "imprint", "legal", "cookies", "blog",
    "news", "careers", "team", "product", "products", "service", "services", "solutions",
    "impressum", "datenschutz", "agb", "kontakt", "cookie", "policy", "rights", "reserved"
}

# Known company names for validation (could be expanded)
KNOWN_COMPANY_NAMES = {
    "acme gmbh", "example ag", "test inc"
}

# HTML meta tags that often contain company names
META_TAGS = [
    'og:site_name', 'og:title', 'twitter:site', 'application-name',
    'apple-mobile-web-app-title', 'company', 'organization', 'author'
]

# Enhanced regex patterns with international support
COMPANY_PATTERN = rf"""
    \b(
        (?:[A-ZÀ-ÖØ-ß][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ-ß][a-zà-öø-ÿ]+)*)  # Company name words
        \s*  # Optional space
        (?:{'|'.join(COMPANY_SUFFIXES)})  # Legal form
        (?!\w)  # Not followed by another word character
    )|
    \b(
        (?:[A-ZÀ-ÖØ-ß][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ-ß][a-zà-öø-ÿ]+)+)  # Multi-word names without suffix
    )\b|
    \b(
        (?:[A-ZÀ-ÖØ-ß]{{2,}}(?:\s+[A-ZÀ-ÖØ-ß]{{2,}})+)  # All-caps names (like IBM)
    )\b
"""

def clean_text(text: str) -> str:
    """Clean and normalize text with better HTML and encoding handling."""
    if not text:
        return ""
        
    # Handle encoding issues
    try:
        text = text.encode('ascii', 'ignore').decode('utf-8')
    except:
        pass
        
    # Decode HTML entities
    text = html.unescape(text)

    # Remove HTML tags and comments
    soup = BeautifulSoup(text, 'html.parser')
    for element in soup(['script', 'style', 'noscript', 'meta', 'link', 'comment']):
        element.decompose()

    # Get text with proper spacing
    text = ' '.join(soup.stripped_strings)

    # Remove invisible characters
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    
    # Normalize whitespace and special characters
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\u00a0\u1680\u2000-\u200f\u2028-\u202f\u205f\u3000\ufeff]', ' ', text)

    return text.strip()

async def is_website_reachable(url: str) -> bool:
    """Check if a website is reachable without loading the full page."""
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc or parsed.path.split('/')[0]

        # First try DNS resolution
        loop = asyncio.get_running_loop()
        await loop.getaddrinfo(hostname, None)

        # Then try SSL handshake
        context = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, 443, ssl=context),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        logger.debug(f"Website {url} not reachable: {str(e)}")
        return False

def extract_from_meta(soup: BeautifulSoup) -> List[str]:
    """Extract potential company names from meta tags."""
    candidates = []

    for tag in META_TAGS:
        meta = soup.find('meta', {'property': tag}) or soup.find('meta', {'name': tag})
        if meta and meta.get('content'):
            content = meta['content'].strip()
            if len(content) > 3 and not any(w in content.lower() for w in COMMON_WORDS):
                candidates.append(content)

    title = soup.title.string if soup.title else None
    if title and len(title) > 3:
        candidates.append(title.strip())

    return candidates

def extract_from_schema(soup: BeautifulSoup) -> List[str]:
    """Extract company names from schema.org markup."""
    candidates = []
    for script in soup.find_all('script', {'type': 'application/ld+json'}):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                if data.get('@type') in ['Organization', 'Corporation']:
                    if data.get('name'):
                        candidates.append(data['name'])
                elif data.get('publisher', {}).get('name'):
                    candidates.append(data['publisher']['name'])
        except json.JSONDecodeError:
            continue
    return candidates

def score_company_name(name: str) -> int:
    """Score a potential company name based on various factors."""
    score = 0

    # Length score (prefer medium-length names)
    length = len(name)
    if 5 <= length <= 30:
        score += 2
    elif 30 < length <= 50:
        score += 1

    # Legal form presence
    if any(re.search(rf'\b{s}\b'.replace('.', r'\.'), name, flags=re.IGNORECASE)
       for s in COMPANY_SUFFIXES):
        score += 3

    # Capitalization pattern
    if re.match(r'^[A-ZÀ-ÖØ-ß][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ-ß][a-zà-öø-ÿ]+)*(?:\s+(?:{})?)?$'
                .format('|'.join(COMPANY_SUFFIXES)), name):
        score += 2

    # Common word penalty
    common_words_penalty = sum(
        1 for w in COMMON_WORDS if w in name.lower()
    )
    score -= common_words_penalty

    # Dictionary check
    if name.lower() in KNOWN_COMPANY_NAMES:
        score += 5

    return score

def extract_company_names(text: str, soup: Optional[BeautifulSoup] = None) -> List[str]:
    """Extract company names from text with improved heuristics."""
    candidates = []

    # Extract from meta tags first if soup is available
    if soup:
        candidates.extend(extract_from_meta(soup))
        candidates.extend(extract_from_schema(soup))

    # Clean text for regex matching
    text = clean_text(text)

    # Find matches with both patterns
    matches = re.findall(COMPANY_PATTERN, text, flags=re.IGNORECASE | re.VERBOSE)

    # Process matches - each match is a tuple of two groups (with and without suffix)
    for match in matches:
        for group in match:
            if group and len(group) >= 4:  # Minimum reasonable company name length
                # Clean up the match
                cleaned = re.sub(r'[^\w\sà-öø-ÿÀ-ÖØ-ß-]', '', group.strip())
                if not any(w in cleaned.lower() for w in COMMON_WORDS):
                    candidates.append(cleaned)

    return candidates

@lru_cache(maxsize=ExtractionSettings.MAX_CACHE_SIZE)
def get_domain(url: str) -> str:
    """Extract domain from URL with caching for performance."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.lower().replace('www.', '').split('/')[0].split(':')[0]
    except:
        return ""

def normalize_url(url: str) -> str:
    """Normalize URLs to consistent format."""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    # Remove fragments and query params for company name extraction
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def extract_from_domain(url: str) -> Optional[str]:
    """Enhanced domain name extraction with better heuristics."""
    domain = get_domain(url)
    if not domain:
        return None

    # Remove TLD
    main_part = domain.split('.')[0]

    # Remove common prefixes/suffixes
    main_part = re.sub(
        r'^(the|my|get|app|shop|digital|online|we|our|your|go|new|try|use|demo|api|portal)-?',
        '',
        main_part,
        flags=re.IGNORECASE
    )
    main_part = re.sub(
        r'-?(app|shop|tech|health|care|ai|de|gmbh|ag|com|net|org|io|co|eu|uk|us|global|world|online|digital|solutions|group|holding|ventures|capital|partners|studio|labs|inc|llc)$',
        '',
        main_part,
        flags=re.IGNORECASE
    )

    if not main_part or len(main_part) < 3:
        return None

    # Split and clean parts
    parts = []
    for p in re.split(r'[-_]', main_part):
        if len(p) > 2 and not p.isdigit():
            # Handle camelCase
            sub_parts = re.findall(r'([A-ZÀ-ÖØ-ß]?[a-zà-öø-ÿ]+)', p)
            if sub_parts:
                parts.extend(sub_parts)

    if not parts:
        return None

    # Capitalize and join
    company_name = ' '.join(p.capitalize() for p in parts)

    # Add GmbH if no legal form present and name is reasonable
    if (not any(re.search(rf'\b{s}\b'.replace('.', r'\.'), company_name, flags=re.IGNORECASE)
            for s in COMPANY_SUFFIXES)):
        if 3 <= len(company_name.split()) <= 5:  # Reasonable word count
            company_name += " GmbH"
        else:
            return None  # Don't add suffix to very long/short names

    return company_name if 4 <= len(company_name) <= 60 else None

@retry(stop=stop_after_attempt(ExtractionSettings.RETRY_ATTEMPTS), 
       wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_url(session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
    """Fetch URL content with retry logic."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=ExtractionSettings.REQUEST_TIMEOUT)) as response:
            if response.status >= 400:
                raise aiohttp.ClientError(f"HTTP status {response.status}")
            return (url, await response.text())
    except Exception as e:
        logger.warning(f"Error fetching {url}: {str(e)}")
        raise

async def extract_from_url(url: str, session: aiohttp.ClientSession) -> dict:
    """Robust URL processing with comprehensive extraction."""
    try:
        url = normalize_url(url)
        
        # First check if website is reachable
        if not await is_website_reachable(url):
            domain_name = extract_from_domain(url)
            if domain_name:
                return {
                    "url": url,
                    "company": domain_name,
                    "candidates": [domain_name],
                    "status": "domain_fallback"
                }
            return {"url": url, "company": None, "status": "unreachable", "error": "Website not reachable"}

        # Fetch the URL content
        try:
            url, content = await fetch_url(session, url)
        except Exception as e:
            domain_name = extract_from_domain(url)
            if domain_name:
                return {
                    "url": url,
                    "company": domain_name,
                    "candidates": [domain_name],
                    "status": "domain_fallback"
                }
            return {"url": url, "company": None, "status": "error", "error": str(e)}

        soup = BeautifulSoup(content, 'html.parser')
        text = clean_text(content)

        # Extract candidates from multiple sources
        candidates = []

        # 1. From meta tags
        candidates.extend(extract_from_meta(soup))

        # 2. From schema.org markup
        candidates.extend(extract_from_schema(soup))

        # 3. From prominent headings (h1, h2)
        for heading in soup.find_all(['h1', 'h2']):
            if heading.text.strip():
                candidates.append(heading.text.strip())

        # 4. From the first paragraph with strong text
        first_p_or_div = soup.find(['p', 'div'])
        if first_p_or_div:
            first_strong = first_p_or_div.find('strong')
            if first_strong and first_strong.text.strip():
                candidates.append(first_strong.text.strip())

        # 5. From regex pattern matching
        candidates.extend(extract_company_names(text, soup))

        # 6. From copyright footer
        copyright_text = soup.find(string=re.compile(r'©|Copyright|All rights reserved', re.IGNORECASE))
        if copyright_text:
            copyright_clean = re.sub(r'.*?(©|Copyright)\s*', '', copyright_text, flags=re.IGNORECASE)
            copyright_clean = re.sub(r'All rights reserved.*', '', copyright_clean, flags=re.IGNORECASE)
            copyright_clean = copyright_clean.strip()
            if copyright_clean:
                candidates.append(copyright_clean)

        # 7. From footer elements
        footer = soup.find('footer') or soup.find(class_=re.compile('footer', re.IGNORECASE))
        if footer:
            footer_text = footer.get_text(separator=' ', strip=True)
            if footer_text:
                candidates.extend(extract_company_names(footer_text))

        if candidates:
            # Score and select best candidate
            scored = []
            for name in set(candidates):
                score = score_company_name(name)
                if score > 0:
                    scored.append((score, name))

            if scored:
                scored.sort(reverse=True)
                best = scored[0][1]

                # Enhanced post-processing
                best = re.sub(r'^[^a-zA-ZÀ-ÖØ-ßà-öø-ÿ]*', '', best)
                best = re.sub(r'[^a-zA-ZÀ-ÖØ-ßà-öø-ÿ0-9\s\-&.,]+$', '', best)
                best = re.sub(r'\s+', ' ', best).strip()
                best = re.sub(r'\b(?:impressum|datenschutz|agb|kontakt|cookie|policy|rights|reserved)\b', '', best, flags=re.IGNORECASE)
                best = best.strip()

                if len(best) >= 4:
                    return {
                        "url": url,
                        "company": best,
                        "candidates": candidates,
                        "status": "success"
                    }

        # Fallback to domain extraction
        domain_name = extract_from_domain(url)
        if domain_name:
            return {
                "url": url,
                "company": domain_name,
                "candidates": [domain_name],
                "status": "domain_fallback"
            }

        return {"url": url, "company": None, "status": "not_found"}

    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}", exc_info=True)
        domain_name = extract_from_domain(url)
        if domain_name:
            return {
                "url": url,
                "company": domain_name,
                "candidates": [domain_name],
                "status": "domain_fallback"
            }
        return {"url": url, "company": None, "status": "error", "error": str(e)}

async def process_urls(urls: List[str]) -> List[dict]:
    """Process multiple URLs asynchronously with progress tracking."""
    results = []
    connector = aiohttp.TCPConnector(limit=ExtractionSettings.MAX_CONCURRENT_REQUESTS)
    
    headers = {
        "User-Agent": ExtractionSettings.USER_AGENT,
        "Accept-Language": ExtractionSettings.ACCEPTED_LANGUAGES,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        tasks = [extract_from_url(url, session) for url in urls]
        
        with tqdm(total=len(urls), desc="Processing URLs", unit="URL") as pbar:
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    results.append(result)
                    
                    if result['status'] not in ('success', 'domain_fallback'):
                        logger.info(f"Failed to extract from {result['url']}: {result['status']}")
                except Exception as e:
                    logger.error(f"Exception processing URL: {e}", exc_info=True)
                    results.append({"url": "unknown", "company": None, "status": "error", "error": str(e)})
                finally:
                    pbar.update(1)

    return results

def analyze_results(results: List[dict]) -> Dict[str, int]:
    """Analyze and summarize extraction results."""
    analysis = {
        'total': len(results),
        'success': 0,
        'domain_fallback': 0,
        'not_found': 0,
        'unreachable': 0,
        'error': 0
    }

    for result in results:
        analysis[result['status']] += 1

    return analysis

def print_results(results: List[dict]):
    """Print formatted results."""
    analysis = analyze_results(results)

    print("\n=== Extraction Results ===")
    print(f"Total URLs processed: {analysis['total']}")
    print(f"Successfully extracted: {analysis['success']}")
    print(f"Domain fallback: {analysis['domain_fallback']}")
    print(f"Not found: {analysis['not_found']}")
    print(f"Unreachable URLs: {analysis['unreachable']}")
    print(f"Errors: {analysis['error']}\n")

    print("=== Detailed Results ===")
    for result in results:
        status = result['status'].upper()
        if result['company']:
            print(f"{status.ljust(15)} {result['url']} -> {result['company']}")
        else:
            print(f"{status.ljust(15)} {result['url']} -> NOT FOUND ({result.get('error', '')})")

async def main():
    test_urls = [
        'https://www.acalta.de',
        'https://www.actimi.com',
        'https://www.emmora.de',
        'https://www.alfa-ai.com',
        'https://www.apheris.com',
        'https://www.aporize.com/',
        'https://www.arztlena.com/',
        'https://shop.getnutrio.com/',
        'https://www.auta.health/',
        'https://visioncheckout.com/',
        'https://www.avayl.tech/',
        'https://www.avimedical.com/avi-impact',
        'https://de.becureglobal.com/',
        'https://bellehealth.co/de/',
        'https://www.biotx.ai/',
        'https://www.brainjo.de/',
        'https://brea.app/',
        'https://breathment.com/',
        'https://de.caona.eu/',
        'https://www.careanimations.de/',
        'https://sfs-healthcare.com',
        'https://www.climedo.de/',
        'https://www.cliniserve.de/',
        'https://cogthera.de/#erfahren',
        'https://www.comuny.de/',
        'https://curecurve.de/elina-app/',
        'https://www.cynteract.com/de/rehabilitation',
        'https://www.healthmeapp.de/de/',
        'https://deepeye.ai/',
        'https://www.deepmentation.ai/',
        'https://denton-systems.de/',
        'https://www.derma2go.com/',
        'https://www.dianovi.com/',
        'http://dopavision.com/',
        'https://www.dpv-analytics.com/',
        'http://www.ecovery.de/',
        'https://elixionmedical.com/',
        'https://www.empident.de/',
        'https://eye2you.ai/',
        'https://www.fitwhit.de',
        'https://www.floy.com/',
        'https://fyzo.de/assistant/',
        'https://www.gesund.de/app',
        'https://www.glaice.de/',
        'https://gleea.de/',
        'https://www.guidecare.de/',
        'https://www.apodienste.com/',
        'https://www.help-app.de/',
        'https://www.heynanny.com/',
        'https://incontalert.de/',
        'https://home.informme.info/',
        'https://www.kranushealth.com/de/therapien/haeufiger-harndrang',
        'https://www.kranushealth.com/de/therapien/inkontinenz'
    ]

    # Clean URLs (some had incorrect protocols)
    cleaned_urls = []
    for url in test_urls:
        if url.startswith('https:/') and not url.startswith('https://'):
            url = url.replace('https:/', 'https://')
        elif url.startswith('http:/') and not url.startswith('http://'):
            url = url.replace('http:/', 'http://')
        cleaned_urls.append(url)

    results = await process_urls(cleaned_urls)
    print_results(results)

if __name__ == "__main__":
    asyncio.run(main())