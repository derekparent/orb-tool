# Web Search API Comparison for Marine Diesel Engine Troubleshooting App

**Use Case:** Flask web app aboard ships with Claude LLM assistant for CAT engine troubleshooting (3516, C18, C32). "Check online" feature to search web for known issues, service bulletins, and field experience, then feed clean results into Claude for synthesis.

**Key Requirements:**
- Clean text/snippets suitable for LLM ingestion (no raw HTML parsing)
- Niche technical domain: Caterpillar diesel engines, marine engineering
- Low volume: ~10–30 searches/day
- Free tier matters (solo developer)
- Python SDK or simple HTTP integration
- Fast response time (ship internet is slow/intermittent)
- Ability to prioritize/restrict specific domains (caterpillar.com, diesel forums, etc.)

---

## Head-to-Head Comparison

### 1. Tavily (Search API Built for LLM/RAG)

| Attribute | Details |
|---|---|
| **Free Tier** | 1,000 credits/month (basic search = 1 credit, advanced = 2 credits). No credit card required. |
| **Paid Plans** | Pay-as-you-go $0.008/credit; $30/mo for 4,000 credits; scales to enterprise |
| **Clean Text Output** | ✅ **Best in class.** Returns pre-cleaned snippets in `content` field, relevance-scored. Optional `include_raw_content` returns cleaned/parsed full-page Markdown. Separate `/extract` endpoint returns clean text/markdown from URLs. |
| **Niche Technical Quality** | Good. Aggregates from multiple search sources. Quality depends on what's indexed across those sources. Not a proprietary index—sources are undisclosed but broad. |
| **Python SDK** | ✅ Official `tavily-python` SDK. `pip install tavily-python`. Clean, well-documented. |
| **Latency** | Basic search: ~1–3 seconds typical. Fast/Ultra-fast modes: sub-second. Advanced: 3–10 seconds. Community reports occasional spikes. |
| **Domain Filtering** | ✅ **Native `include_domains` and `exclude_domains` parameters.** Up to 300 include domains, 150 exclude domains. First-class support. |
| **LLM Integration** | ✅ Purpose-built. Optional `include_answer` returns LLM-generated summary. LangChain, LlamaIndex, CrewAI integrations. |
| **Gotchas** | Advanced search uses 2 credits (halves your free quota). `include_raw_content` can increase latency and occasionally return noisy text (menus, footers). Some community reports of `/extract` returning irrelevant page chrome. |

**Free tier math:** At 20 searches/day × 30 days = 600 basic searches/month. Comfortably within 1,000 free credits.

---

### 2. Brave Search API

| Attribute | Details |
|---|---|
| **Free Tier** | 2,000 queries/month, 1 query/second rate limit. No credit card required. |
| **Paid Plans** | Base AI: $5/1,000 requests; Pro AI: $9/1,000 requests |
| **Clean Text Output** | ⚠️ **Partial.** Returns structured JSON with title, URL, description snippets, and optional extra snippets. Does NOT return full-page clean text—snippets only. You get search result descriptions, not full article content. Suitable for feeding snippets into LLM but less content per result than Tavily. |
| **Niche Technical Quality** | Good. Brave has its own independent search index (30B+ pages, 100M daily updates). Quality on niche CAT engine queries may be slightly lower than Google-sourced results, but the independent index means less SEO spam. |
| **Python SDK** | ❌ No official Python SDK. Simple REST API with `requests` library. Easy to integrate but you write your own wrapper. |
| **Latency** | ✅ **Fastest tested.** Benchmarked at ~669ms median. Consistently sub-2 seconds. Excellent for slow ship internet. |
| **Domain Filtering** | ⚠️ **Via query operators only.** Use `site:caterpillar.com` in the query string. Brave also supports **Goggles**—custom ranking rules that can boost/downrank/discard specific domains. Goggles are powerful but require creating a Goggles file. No native `include_domains` parameter in the API. Multiple `site:` operators with `OR` have reported bugs. |
| **Gotchas** | No full-page content extraction—snippets only. Multi-site OR filtering has known issues. Free tier rate limit of 1 QPS could bottleneck if you fire multiple concurrent requests. Independent index may miss some niche forum content that Google indexes. |

**Free tier math:** 20 searches/day × 30 days = 600 queries/month. Well within 2,000 free queries.

---

### 3. SerpAPI (Google Search Wrapper)

| Attribute | Details |
|---|---|
| **Free Tier** | 100 searches/month (was 250, recently reduced). No credit card required. |
| **Paid Plans** | $75/mo for 5,000 searches; $150/mo for 15,000 searches |
| **Clean Text Output** | ⚠️ **Structured JSON of Google SERP data.** Returns organic results with title, link, snippet, plus rich elements (knowledge graph, related questions, etc.). Snippets are Google's own descriptions—clean but brief. No full-page content extraction. |
| **Niche Technical Quality** | ✅ **Best quality.** It's Google search results. Google has the deepest index for niche technical content—Caterpillar service docs, obscure diesel forums, marine engineering resources. |
| **Python SDK** | ✅ Official `google-search-results` Python package. Well-maintained. |
| **Latency** | ✅ Fast. Benchmarked at ~0.73s average, 1.45s p99. Very consistent. |
| **Domain Filtering** | ⚠️ Via `site:` operator in query string (standard Google search operators). Works reliably. No dedicated API parameter. |
| **Gotchas** | **100 free searches/month is not enough for your use case** (you need 600+/month). Cheapest paid plan is $75/month—way overkill and expensive for 600 queries. Pricing is designed for SEO professionals, not small RAG apps. Returns SERP metadata (ads, PAA, etc.) that you don't need. |

**Free tier math:** 100/month ÷ 30 days ≈ 3 searches/day. **Insufficient for your needs.**

---

### 4. Serper.dev (Lightweight Google Wrapper)

| Attribute | Details |
|---|---|
| **Free Tier** | 2,500 one-time free credits (not monthly). No credit card required. After that, pay-as-you-go. |
| **Paid Plans** | $50 for 50,000 credits (~$1/1,000 queries). Credits valid 6 months. |
| **Clean Text Output** | ⚠️ Returns structured JSON with Google SERP results. Title, link, snippet for each result. Clean but snippet-only (no full-page text). Optional Knowledge Graph and People Also Ask data. |
| **Niche Technical Quality** | ✅ **Excellent.** Google results, same quality as SerpAPI. |
| **Python SDK** | ❌ No official SDK. Simple REST API via `requests`. Very easy to integrate (single POST endpoint). |
| **Latency** | ✅ Very fast. ~0.83s average, 2.1s p99. Among the fastest. |
| **Domain Filtering** | ⚠️ Via `site:` in query string. Standard Google operators. |
| **Gotchas** | Free credits are **one-time only**, not recurring. At 20 searches/day, you'll burn through 2,500 credits in ~4 months, then you're paying. However, $50 for 50,000 credits is extremely affordable ($1/1,000 = $0.001/query). For your volume that's maybe $0.60/month—effectively free. But it's not truly free-tier-forever. |

**Free tier math:** 2,500 one-time credits ÷ 20/day = ~125 days (~4 months). Then $50 lasts 50,000 ÷ 600/month ≈ 83 months. Effectively negligible cost.

---

### 5. Google Custom Search JSON API

| Attribute | Details |
|---|---|
| **Free Tier** | 100 queries/day (3,000/month). No paid plan needed for your volume. |
| **Paid Plans** | $5 per 1,000 additional queries, up to 10,000 queries/day |
| **Clean Text Output** | ⚠️ Returns JSON with title, link, snippet (HTML-formatted snippet with `<b>` tags that need stripping). Slightly more parsing needed than other options. No full-page content. |
| **Niche Technical Quality** | ✅ Google results. However, you must configure a **Programmable Search Engine** first, which can be set to search the whole web or a specific set of sites. Whole-web mode quality is close to regular Google but not identical. |
| **Python SDK** | ⚠️ No dedicated SDK. Use `google-api-python-client` (general Google API library) or plain `requests`. More setup than competitors. |
| **Latency** | Moderate. Generally 1–3 seconds. |
| **Domain Filtering** | ✅ Built into the Programmable Search Engine configuration. You can define a set of sites to search, or search the whole web and boost specific sites. Also supports `siteSearch` and `siteSearchFilter` parameters in the API call. |
| **Gotchas** | **Requires creating a Programmable Search Engine in Google's console first.** Results may differ from regular Google search. Snippets contain HTML markup (`<b>` tags) that need cleaning. 100 queries/day means you're fine at 10–30/day but have no headroom for testing/development. Rate limiting is per-day (resets at midnight Pacific), not rolling. |

**Free tier math:** 100/day is more than your 10–30/day max. Fits the requirement but leaves limited headroom.

---

### 6. Bing Web Search API ⚠️ RETIRED

| Attribute | Details |
|---|---|
| **Status** | **RETIRED on August 11, 2025.** No longer available for new signups or existing users. |
| **Replacement** | "Grounding with Bing Search" in Azure AI Foundry. $35/1,000 transactions. Requires Azure AI Agent Service. Cannot access raw search results—results are processed through an LLM before delivery. |
| **Recommendation** | **Do not use.** The replacement is expensive ($35/1,000 vs. free alternatives), requires Azure ecosystem lock-in, and doesn't return raw results you can feed into your own Claude pipeline. It's designed for Microsoft's own agent architecture, not custom RAG setups. |

---

### 7. You.com Search API

| Attribute | Details |
|---|---|
| **Free Tier** | $100 in free credits for developers. Standard search API is billed per 1,000 calls. |
| **Paid Plans** | Standard API pricing varies. Deep Research: ~$15 per research call. Opaque pricing. |
| **Clean Text Output** | ✅ Returns AI-summarized snippets. Can return clean text suitable for LLM ingestion. |
| **Niche Technical Quality** | Moderate. Uses multiple search sources. Less proven on highly technical/niche queries. |
| **Python SDK** | ⚠️ REST API. No dedicated Python SDK found. |
| **Latency** | Moderate to high. AI-augmented results add latency. |
| **Domain Filtering** | Limited documentation on domain filtering capabilities. |
| **Gotchas** | **Pricing is opaque and developer-unfriendly.** Company focus has shifted to enterprise B2B. Consumer/developer API appears deprioritized. Not recommended for new projects—uncertain long-term support for small developers. |

---

### 8. Exa AI (Bonus Recommendation)

| Attribute | Details |
|---|---|
| **Free Tier** | $10 in one-time free credits. At $5/1,000 searches, that's ~2,000 free searches. No expiration. No credit card required. |
| **Paid Plans** | $5/1,000 search requests. Content retrieval: $1/1,000 pages. Pay-as-you-go. |
| **Clean Text Output** | ✅ **Excellent.** Returns clean text, highlights (AI-retrieved snippets), or LLM summaries. Content extraction returns full webpage text—cleaned and formatted. Multiple output modes. |
| **Niche Technical Quality** | ✅ **Semantic search** capabilities. Uses neural search to find conceptually related content, not just keyword matching. Could surface relevant CAT engine field reports even with imprecise queries. However, index breadth for niche industrial forums is unproven. |
| **Python SDK** | ✅ Official `exa_py` SDK. Clean API design. |
| **Latency** | Low to medium depending on search type. Fast/auto modes are sub-second. |
| **Domain Filtering** | ✅ Supports `include_domains` and `exclude_domains` as native parameters. |
| **Gotchas** | One-time credits, not monthly. Neural/semantic search might over-generalize on very specific part numbers or error codes. Younger company—less track record than Brave or Google. |

---

### 9. DuckDuckGo (via `duckduckgo-search` Python Package)

| Attribute | Details |
|---|---|
| **Free Tier** | ✅ **Completely free.** No API key required. No rate limits (unofficial). |
| **Clean Text Output** | ⚠️ Returns title, link, and body snippet. Snippets are brief. No full-page extraction. |
| **Niche Technical Quality** | Moderate. DDG sources from Bing and its own crawler. Doesn't index as deeply as Google for niche technical content. |
| **Python SDK** | ✅ `pip install duckduckgo-search` (unofficial but well-maintained, `DDGS` class). |
| **Latency** | Variable. Generally 1–3 seconds. |
| **Domain Filtering** | ⚠️ Via `site:` operator in query string only. |
| **Gotchas** | **Unofficial/unsupported.** DDG has no official API for developers. This Python package scrapes DDG's HTML results. DDG can change their markup or block automated access at any time. No SLA, no guarantees. Rate limiting is informal—heavy use may get your IP blocked. **Not recommended as a primary solution** but works as a free fallback. |

---

### 10. SearXNG (Self-Hosted Meta-Search)

| Attribute | Details |
|---|---|
| **Free Tier** | ✅ **Completely free and open-source.** Self-hosted. |
| **Clean Text Output** | Returns JSON with title, URL, content snippet, engine source. Clean enough for LLM use. |
| **Niche Technical Quality** | ✅ Aggregates results from Google, Bing, Brave, DuckDuckGo, and 70+ other engines simultaneously. Potentially the broadest coverage. |
| **Python SDK** | REST API (JSON format). Simple `requests` calls. No dedicated SDK needed. |
| **Latency** | Depends entirely on your hosting and the upstream engines' response times. Adds overhead from aggregation. |
| **Domain Filtering** | ⚠️ Via query operators passed to upstream engines. |
| **Gotchas** | **Requires a server to run on.** Won't work directly on a ship without shore-side hosting or running it aboard (Docker container). Upstream engines may rate-limit or block your instance if over-used. Maintenance burden. **Not practical for shipboard deployment unless you have reliable shore-side infrastructure.** |

---

## Summary Comparison Table

| API | Free Tier | Clean LLM Text | Domain Filtering | Latency | Technical Quality | Python SDK | Best For |
|---|---|---|---|---|---|---|---|
| **Tavily** | 1,000 credits/mo | ✅ Best | ✅ Native params | ~1–3s | Good | ✅ Official | **LLM/RAG apps (your use case)** |
| **Brave** | 2,000 queries/mo | ⚠️ Snippets only | ⚠️ Query operators + Goggles | ✅ ~0.7s | Good | ❌ REST only | Speed-critical, privacy |
| **SerpAPI** | 100/month | ⚠️ Snippets | ⚠️ `site:` operator | ✅ ~0.7s | ✅ Best (Google) | ✅ Official | SEO pros (too expensive for you) |
| **Serper.dev** | 2,500 one-time | ⚠️ Snippets | ⚠️ `site:` operator | ✅ ~0.8s | ✅ Excellent (Google) | ❌ REST only | Budget Google results |
| **Google CSE** | 100/day (~3K/mo) | ⚠️ HTML snippets | ✅ Native config | ~1–3s | ✅ Google | ⚠️ General lib | Whole-web Google on free tier |
| **Bing API** | ❌ RETIRED | — | — | — | — | — | **Do not use** |
| **You.com** | $100 credits | ✅ AI summaries | ❓ Limited | Moderate | Moderate | ❌ REST only | Uncertain future |
| **Exa AI** | $10 one-time credits | ✅ Excellent | ✅ Native params | Low–Med | ✅ Semantic | ✅ Official | Semantic/conceptual search |
| **DuckDuckGo** | ✅ Unlimited free | ⚠️ Snippets | ⚠️ `site:` only | 1–3s | Moderate | ✅ Unofficial | Free fallback only |
| **SearXNG** | ✅ Free (self-host) | ⚠️ Snippets | ⚠️ Query operators | Variable | ✅ Broad | REST API | Self-hosters with infra |

---

## Recommendation: Tavily as Primary, Brave as Secondary

### Why Tavily Wins for Your Use Case

1. **Purpose-built for LLM/RAG pipelines.** The `content` field returns pre-cleaned, relevance-scored text snippets that can be injected directly into Claude's context window. No HTML parsing, no boilerplate stripping. This is the single biggest advantage—every other API returns search snippets that are shorter and less informative.

2. **Native `include_domains` filtering.** You can pass `include_domains=["caterpillar.com", "cat.com", "thedieselpage.com", "marineinsight.com"]` directly in the API call. No query string hacking with `site:` operators.

3. **Free tier covers your volume.** 1,000 credits/month with basic search (1 credit each) = 1,000 searches. You need 300–900/month. Even if you use advanced depth for some queries (2 credits), you're covered.

4. **Official Python SDK.** Clean integration: `pip install tavily-python`.

5. **Optional content extraction.** If a search result looks promising, use Tavily's `/extract` endpoint to pull the full clean text from that URL—useful for pulling complete service bulletins.

6. **`include_answer` option.** For quick checks, Tavily can return a pre-synthesized answer alongside the raw results. You could show this as a "quick summary" while Claude processes the full results.

### Why Brave as a Backup

- Fastest response time (~669ms)—critical for satellite internet
- Generous free tier (2,000/month)
- Independent index = different results that may catch things Tavily misses
- Simple REST integration as a fallback

### Recommended Architecture

```python
from tavily import TavilyClient
import requests

tavily = TavilyClient(api_key="tvly-YOUR_KEY")

def search_online(query: str, domains: list = None) -> str:
    """Search web for engine troubleshooting info, return clean text for Claude."""
    
    default_domains = [
        "caterpillar.com", "cat.com",
        "marineinsight.com", "marinediesels.info",
        "thedieselpage.com", "dieselhub.com",
        "barringtondieselclub.co.za",
        "seaboardmarine.com",
    ]
    
    try:
        # Primary: Tavily (clean LLM-ready text)
        response = tavily.search(
            query=f"Caterpillar marine diesel {query}",
            search_depth="basic",       # 1 credit
            max_results=5,
            include_domains=domains or default_domains,
            include_raw_content=False,   # Keep it fast
        )
        
        results = []
        for r in response["results"]:
            results.append(f"Source: {r['title']} ({r['url']})\n{r['content']}\n")
        
        return "\n---\n".join(results)
    
    except Exception:
        # Fallback: Brave Search API (fast, snippet-based)
        return _brave_fallback(query)


def _brave_fallback(query: str) -> str:
    """Fallback to Brave Search if Tavily is down."""
    headers = {
        "X-Subscription-Token": "YOUR_BRAVE_KEY",
        "Accept": "application/json",
    }
    params = {
        "q": f"Caterpillar marine diesel {query} site:caterpillar.com OR site:cat.com",
        "count": 5,
    }
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers=headers, params=params, timeout=15
    )
    data = resp.json()
    
    results = []
    for r in data.get("web", {}).get("results", []):
        results.append(f"Source: {r['title']} ({r['url']})\n{r.get('description', '')}\n")
    
    return "\n---\n".join(results)
```

### Ship Internet Optimization Tips

- **Cache aggressively.** Store search results in SQLite keyed by query hash with a TTL of 24–72 hours. Many engine issues are well-documented—results don't change daily.
- **Use Tavily `basic` or `fast` depth.** Avoid `advanced` (doubles credits AND latency).
- **Set short timeouts** (10–15 seconds) and fall back to Brave (faster) or cached results.
- **Pre-fetch common queries** when connectivity is good. Build a library of cached results for common 3516/C18/C32 issues.
- **Keep `max_results` low** (3–5). More results = more data over the wire and more tokens for Claude to process. On slow satellite links, every KB matters.

---

## Cost Projection (Monthly)

| Scenario | Tavily (Free) | Brave (Free) | Serper.dev |
|---|---|---|---|
| 10 searches/day (basic) | 300 credits ✅ | 300 queries ✅ | $0.30 |
| 20 searches/day (basic) | 600 credits ✅ | 600 queries ✅ | $0.60 |
| 30 searches/day (basic) | 900 credits ✅ | 900 queries ✅ | $0.90 |
| 20/day with some advanced | ~800 credits ✅ | N/A | $0.60 |

All three are effectively free for your volume. Tavily wins on output quality for LLM pipelines.

---

*Last updated: February 2026*
