#web_search.py
import json
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
import os
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")


def _get_api_key() -> str:
    return os.environ.get("GROQ_API_KEY", "")

def _get_tavily_key() -> str:
    return os.environ.get("TAVILY_API_KEY", "")


def _llm_search(query: str) -> str:
    from google import genai

    client   = genai.Client(api_key=_get_api_key())
    response = client.models.generate_content(
        model="qwen3:8b",
        contents=query,
        config={"tools": [{"google_search": {}}]},
    )

    text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            text += part.text

    text = text.strip()
    if not text:
        raise ValueError("LLM returned an empty response.")
    return text

def _tavily_search(query: str, max_results: int = 5) -> str:
    import requests
    api_key = _get_tavily_key()
    if not api_key:
        raise ValueError("Tavily API key not found in config.")
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "include_images": False,
        "include_raw_content": False,
        "max_results": max_results
    }
    
    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    answer = data.get("answer")
    if answer:
        return answer
        
    results = data.get("results", [])
    if not results:
        return f"No results found for: {query}"
        
    lines = [f"Tavily Search Results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '')}")
        lines.append(f"   {r.get('content', '')}")
        lines.append(f"   {r.get('url', '')}\n")
    
    return "\n".join(lines).strip()


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title":   r.get("title",  ""),
                "snippet": r.get("body",   ""),
                "url":     r.get("href",   ""),
            })
    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()

def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )
    try:
        return _llm_search(query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ LLM compare failed: {e} — falling back to DDG")

    # DDG fallback: fetch results per item and merge
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
    return "\n".join(lines)

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 Query: {query!r}  Mode: {mode}")

    if mode == "compare":
        return _compare(items, aspect)

    try:
        print("[WebSearch] Trying Tavily...")
        result = _tavily_search(query)
        print("[WebSearch] ✅ Tavily OK.")
        return result
    except Exception as e:
        print(f"[WebSearch] ⚠️ Tavily failed ({e}) — trying OpenRouter...")
        try:
            from or_client import client
            result = client.chat(
                query,
                system="You are a web search assistant. Answer factually and concisely based on your general knowledge."
            )
            print("[WebSearch] ✅ OpenRouter OK.")
            return result
        except Exception as e2:
            print(f"[WebSearch] ⚠️ OpenRouter failed ({e2}) — trying DDG...")
            try:
                results = _ddg_search(query)
                result  = _format_ddg(query, results)
                print(f"[WebSearch] ✅ DDG: {len(results)} result(s).")
                return result
            except Exception as e3:
                print(f"[WebSearch] ❌ All backends failed: {e3}")
                return f"Search failed, sir: {e3}"