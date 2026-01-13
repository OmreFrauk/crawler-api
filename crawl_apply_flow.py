import asyncio
import json
import csv
import re
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

# Configuration
JOB_URL = "https://peak.com/open-positions/product-specialist-games-new-grad"
API_KEY = "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"
MODEL = "openai/gpt-oss-20b:free"
BASE_URL = "https://openrouter.ai/api/v1"

# Step 1: Find the Apply Link
async def find_apply_link(url):
    print(f"Fetching job page: {url}")
    browser_config = BrowserConfig(headless=True, verbose=True)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
    
    if not result.success:
        print("Failed to fetch job page.")
        return None

    soup = BeautifulSoup(result.html, 'html.parser')
    
    # Strategy 1: Look for 'a' tags with 'Apply' in text
    for a in soup.find_all('a', href=True):
        if "apply" in a.get_text().lower():
            link = a['href']
            # Handle relative URLs
            if not link.startswith('http'):
                from urllib.parse import urljoin
                link = urljoin(url, link)
            print(f"Found candidate Apply link (text match): {link}")
            return link

    # Strategy 2: Look for 'lever.co' or 'greenhouse.io' in href
    for a in soup.find_all('a', href=True):
        if "lever.co" in a['href'] or "greenhouse.io" in a['href']:
            return a['href']

    print("Could not find an explicit 'Apply' link. The form might be on the page itself.")
    return url # Return original URL if no separate apply link found

# Step 2: Extract Questions from Application Page
async def extract_questions(url):
    print(f"Extracting questions from: {url}")
    
    instruction = (
        "Extract all questions from the job application form related to 'me and my personal background'. "
        "Include interview questions, behavioral questions, or specific application form fields. "
        "Ignore generic fields like 'Name', 'Email', 'Phone' unless they ask for background info."
    )

    llm_config = LLMConfig(
        provider=MODEL,
        api_token=API_KEY,
        base_url=BASE_URL
    )

    extraction_strategy = LLMExtractionStrategy(
        llm_config=llm_config,
        instruction=instruction,
        verbose=True,
        extra_args={
            "extra_headers": {
                "HTTP-Referer": "https://crawl4ai.com",
                "X-Title": "Crawl4AI"
            },
            "reasoning": {"enabled": True}
        }
    )

    browser_config = BrowserConfig(headless=True, verbose=True)
    run_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        cache_mode=CacheMode.BYPASS
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    return result

async def main():
    # 1. Find the link
    apply_url = await find_apply_link(JOB_URL)
    
    if not apply_url:
        print("Aborting.")
        return

    # 2. Extract Data
    result = await extract_questions(apply_url)

    if not result.success:
        print("Failed to crawl application page.")
        return

    # 3. Process and Export
    extracted_content = result.extracted_content
    print("\n--- Extracted Content ---")
    print(extracted_content)

    # Parse JSON content if it's a string
    data_to_export = []
    try:
        if isinstance(extracted_content, str):
            parsed_content = json.loads(extracted_content)
        else:
            parsed_content = extracted_content
        
        # Ensure it's a list for consistency
        if isinstance(parsed_content, dict):
            parsed_content = [parsed_content]
        elif not isinstance(parsed_content, list):
            parsed_content = [{"content": parsed_content}]
            
        data_to_export = parsed_content
    except Exception as e:
        print(f"Error parsing content: {e}")
        data_to_export = [{"raw_content": str(extracted_content)}]

    # Save JSON
    with open("application_questions.json", "w", encoding="utf-8") as f:
        json.dump(data_to_export, f, indent=2)
    print("\nSaved to application_questions.json")

    # Save CSV
    if data_to_export:
        keys = set().union(*(d.keys() for d in data_to_export))
        with open("application_questions.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sorted(list(keys)))
            writer.writeheader()
            writer.writerows(data_to_export)
        print("Saved to application_questions.csv")

if __name__ == "__main__":
    asyncio.run(main())
