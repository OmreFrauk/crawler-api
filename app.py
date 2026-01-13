import os
import json
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

app = FastAPI(title="Job Application Question Extractor")

# Data Models
class CrawlRequest(BaseModel):
    url: str
    api_key: Optional[str] = "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" 
    model: Optional[str] = "openai/gpt-oss-20b:free"

class QuestionResponse(BaseModel):
    job_url: str
    apply_url: Optional[str]
    questions: Any
    status: str
    error: Optional[str] = None

# Core Logic
async def find_apply_link(url: str) -> Optional[str]:
    print(f"Fetching job page: {url}")
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
    
    if not result.success:
        return None

    soup = BeautifulSoup(result.html, 'html.parser')
    
    # Strategy 1: Look for 'a' tags with 'Apply' in text
    for a in soup.find_all('a', href=True):
        if "apply" in a.get_text().lower():
            link = a['href']
            if not link.startswith('http'):
                from urllib.parse import urljoin
                link = urljoin(url, link)
            return link

    # Strategy 2: Look for common ATS domains in href
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(domain in href for domain in ["lever.co", "greenhouse.io", "workable.com", "ashbyhq.com"]):
            return href

    return url # Return original if no specific apply link found (form might be on page)

async def extract_questions_logic(url: str, api_key: str, model: str) -> Any:
    print(f"Extracting questions from: {url}")
    
    instruction = (
        "Extract all questions from the job application form related to 'me and my personal background'. "
        "Include interview questions, behavioral questions, or specific application form fields. "
        "Ignore generic fields like 'Name', 'Email', 'Phone' unless they ask for background info."
    )

    llm_config = LLMConfig(
        provider=model,
        api_token=api_key,
        base_url="https://openrouter.ai/api/v1"
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

    if not result.success:
        raise Exception(f"Failed to crawl {url}: {result.error_message}")

    extracted_content = result.extracted_content
    
    # Try to parse stringified JSON if needed
    try:
        if isinstance(extracted_content, str):
            return json.loads(extracted_content)
    except:
        pass
        
    return extracted_content

# Endpoints
@app.post("/extract", response_model=QuestionResponse)
async def extract_api(request: CrawlRequest):
    try:
        # 1. Find Apply Link
        apply_link = await find_apply_link(request.url)
        
        if not apply_link:
            return QuestionResponse(
                job_url=request.url,
                apply_url=None,
                questions=[],
                status="failed",
                error="Could not load job page"
            )

        # 2. Extract Questions
        try:
            questions = await extract_questions_logic(apply_link, request.api_key, request.model)
            return QuestionResponse(
                job_url=request.url,
                apply_url=apply_link,
                questions=questions,
                status="success"
            )
        except Exception as e:
            return QuestionResponse(
                job_url=request.url,
                apply_url=apply_link,
                questions=[],
                status="failed",
                error=str(e)
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
