# Cost Analysis (February 2026 Pricing)

## Current Pricing Per 1M Tokens

| Provider | Model | Input | Output | Context Window |
|----------|-------|-------|--------|----------------|
| **OpenAI** | GPT-4o-mini | $0.15 | $0.60 | 128K |
| **OpenAI** | GPT-4o | $2.50 | $10.00 | 128K |
| **Anthropic** | Claude Haiku 4.5 | $1.00 | $5.00 | 200K |
| **Anthropic** | Claude Sonnet 4.5 | $3.00 | $15.00 | 200K |
| **Anthropic** | Claude Opus 4.5 | $5.00 | $25.00 | 200K |
| **Google** | Gemini 2.0 Flash | $0.10 | $0.40 | 1M |
| **Google** | Gemini 2.5 Flash | $0.30 | $2.50 | 1M |
| **Google** | Gemini 2.5 Pro | $1.25 | $10.00 | 1M |

## Monthly Cost Estimate at 100 queries/day

**Assumptions:** 5K input tokens + 500 output tokens per query × 100 queries/day × 30 days = 15M input tokens + 1.5M output tokens/month

| Model | Monthly Cost | Cost/Query |
|-------|--------------|------------|
| **Gemini 2.0 Flash** | **$2.10** | **$0.0007** ⭐ Best Value |
| GPT-4o-mini | $3.15 | $0.0011 |
| Gemini 2.5 Flash | $8.25 | $0.0028 |
| Claude Haiku 4.5 | $22.50 | $0.0075 |
| Gemini 2.5 Pro | $33.75 | $0.0113 |
| GPT-4o | $52.50 | $0.0175 |
| Claude Sonnet 4.5 | $67.50 | $0.0225 |
| Claude Opus 4.5 | $112.50 | $0.0375 |

---

## Cost Breakdown Details

### Budget Tier (Under $5/month)
- **Gemini 2.0 Flash**: $2.10/month - Lowest cost, massive 1M context window
- **GPT-4o-mini**: $3.15/month - Best quality-to-cost ratio for technical content

### Mid Tier ($5-$40/month)
- **Gemini 2.5 Flash**: $8.25/month - Enhanced quality, still cost-effective
- **Claude Haiku 4.5**: $22.50/month - Fast responses, good for simple queries
- **Gemini 2.5 Pro**: $33.75/month - Strong reasoning, large context

### Premium Tier ($40+/month)
- **GPT-4o**: $52.50/month - Excellent technical accuracy, proven reliability
- **Claude Sonnet 4.5**: $67.50/month - Best for complex multi-turn conversations
- **Claude Opus 4.5**: $112.50/month - Highest quality reasoning and analysis

---

## Cost Optimization Strategies

### 1. Prompt Caching (Claude only)
- Cache repeated RAG context to reduce input token costs by up to 90%
- Ideal for marine engineering manuals that are referenced repeatedly
- Example: Cache 50K tokens of manual context, only pay for new query tokens

### 2. Hybrid Model Routing
```
Simple queries → Gemini 2.0 Flash ($0.0007/query)
Complex troubleshooting → GPT-4o-mini ($0.0011/query)
Critical diagnostics → Claude Sonnet 4.5 ($0.0225/query)
```
**Estimated hybrid cost**: $5-15/month depending on query distribution

### 3. Context Window Optimization
- Use smaller, focused context chunks instead of full manual sections
- Target 3-5K tokens of retrieved content vs. 8K to reduce costs by 40-60%
- Gemini's 1M context window provides headroom without penalties

---

## Annual Cost Projections

**At 100 queries/day sustained usage:**

| Model | Annual Cost |
|-------|-------------|
| Gemini 2.0 Flash | $25.20 |
| GPT-4o-mini | $37.80 |
| Gemini 2.5 Flash | $99.00 |
| Claude Haiku 4.5 | $270.00 |
| Gemini 2.5 Pro | $405.00 |
| GPT-4o | $630.00 |
| Claude Sonnet 4.5 | $810.00 |
| Claude Opus 4.5 | $1,350.00 |

**Scaling scenarios:**
- **50 queries/day**: Divide annual costs by 2
- **200 queries/day**: Multiply annual costs by 2
- **Variable usage**: Budget models (Gemini Flash, GPT-4o-mini) provide the best flexibility

---

*Generated: February 2, 2026*  
*Use case: Marine engineering RAG-based troubleshooting assistant*  
*Calculation basis: 5K input + 500 output tokens per query*