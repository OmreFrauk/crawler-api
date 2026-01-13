import os
import asyncio
import json
import csv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

# Configuration
URL = "https://peak.com/open-positions/product-specialist-games-new-grad"
API_KEY = "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"
MODEL = "openai/gpt-oss-20b:free"
BASE_URL = "https://openrouter.ai/api/v1"
INSTRUCTION = "Extract all questions related to 'me and my personal background' such as interview questions, application form questions, or behavioral questions found on the page."

async def main():
    print("Setting up crawler...")
    # 1. Configure LLM
    llm_config = LLMConfig(
        provider=MODEL,
        api_token=API_KEY,
        base_url=BASE_URL
    )

    # 2. Configure Extraction Strategy
    extraction_strategy = LLMExtractionStrategy(
        llm_config=llm_config,
        instruction=INSTRUCTION,
        verbose=True,
        extra_args={
            "extra_headers": {
                "HTTP-Referer": "https://crawl4ai.com",
                "X-Title": "Crawl4AI"
            },
            "reasoning": {"enabled": True}
        }
    )

    # 3. Configure Crawler
    browser_config = BrowserConfig(
        headless=True,
        verbose=True
    )

    crawler_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        cache_mode=CacheMode.BYPASS,
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=3, # Limit depth to avoid going too far
            max_pages=100
        )
    )

    # 4. Run Crawler
    print(f"Starting deep crawl on {URL} with max_pages=100...")
    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(
            url=URL,
            config=crawler_config
        )

    if not isinstance(results, list):
        results = [results]

    print(f"Crawl completed. Found {len(results)} pages.")

    # 5. Export to JSON
    json_data = []
    for result in results:
        # result.extracted_content is usually a JSON string from LLM extraction
        content = result.extracted_content
        try:
            # It might already be a list or dict if LLMExtractionStrategy parsed it
            if isinstance(content, str):
                content = json.loads(content)
        except Exception as e:
            # If parsing fails, keep it as is or log error
            pass
        
        json_data.append({
            "url": result.url,
            "extracted_content": content,
            "metadata": result.metadata
        })

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)
    print("Exported to results.json")

    # 6. Export to CSV
    csv_rows = []
    for item in json_data:
        content = item["extracted_content"]
        base_row = {"url": item["url"]}
        
        if isinstance(content, list):
            for entry in content:
                row = base_row.copy()
                if isinstance(entry, dict):
                    # Flatten simple dicts
                    for k, v in entry.items():
                        if isinstance(v, (dict, list)):
                            row[k] = json.dumps(v)
                        else:
                            row[k] = v
                else:
                    row["content"] = str(entry)
                csv_rows.append(row)
        elif isinstance(content, dict):
            row = base_row.copy()
            for k, v in content.items():
                if isinstance(v, (dict, list)):
                    row[k] = json.dumps(v)
                else:
                    row[k] = v
            csv_rows.append(row)
        else:
            # String or other
            base_row["content"] = str(content)
            csv_rows.append(base_row)

    if csv_rows:
        # Collect all keys
        keys = set()
        for row in csv_rows:
            keys.update(row.keys())
        
        with open("results.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sorted(list(keys)))
            writer.writeheader()
            writer.writerows(csv_rows)
        print("Exported to results.csv")
    else:
        print("No structured data found to export to CSV.")

if __name__ == "__main__":
    asyncio.run(main())
