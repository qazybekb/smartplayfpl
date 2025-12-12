"""Claude AI Service for generating personalized FPL insights."""

import hashlib
import json
import logging
import time
from typing import Optional, Any
from dataclasses import dataclass

import anthropic

from config import settings
from models import (
    Player,
    CrowdInsightPlayer,
    CrowdInsightCard,
    CrowdInsightsResponse,
    SellCandidate,
    SellAnalysisResponse,
    BuyCandidate,
    BuyAnalysisResponse,
    ChipStrategy,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SECURE JSON PARSING FOR AI RESPONSES
# =============================================================================

def _safe_parse_ai_json(content: str, max_size: int = 100_000) -> dict:
    """
    Safely parse JSON from AI response with validation.

    SECURITY: This prevents:
    - Overly large responses (DoS)
    - Deeply nested structures (stack overflow)
    - Invalid JSON injection

    Args:
        content: Raw response content from Claude
        max_size: Maximum allowed content size in characters

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If content is invalid or malicious
    """
    import re

    # Size check
    if len(content) > max_size:
        raise ValueError(f"AI response too large: {len(content)} > {max_size}")

    # Extract JSON from markdown code blocks
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    content = content.strip()

    # Parse with recursion limit
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        # Log the first 200 chars of content for debugging
        logger.warning(f"JSON parse error: {e}. Content preview: {content[:200]}...")
        raise ValueError(f"Invalid JSON in AI response: {e}")

    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")

    # Check nesting depth (max 10 levels)
    def check_depth(obj, depth=0, max_depth=10):
        if depth > max_depth:
            raise ValueError(f"JSON too deeply nested (>{max_depth} levels)")
        if isinstance(obj, dict):
            for v in obj.values():
                check_depth(v, depth + 1, max_depth)
        elif isinstance(obj, list):
            for item in obj:
                check_depth(item, depth + 1, max_depth)

    check_depth(parsed)

    return parsed


def _sanitize_ai_text_field(text: str) -> str:
    """
    Sanitize text fields from AI responses.

    SECURITY: Prevents XSS attacks if response is rendered in frontend.
    """
    import re

    if not text:
        return ""

    # Remove potential script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers
    text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)

    # Limit text length
    return text[:5000] if len(text) > 5000 else text


# =============================================================================
# RESPONSE CACHE WITH TTL
# =============================================================================

@dataclass
class CacheEntry:
    """A cached response with expiry timestamp."""
    data: Any
    expires_at: float
    created_at: float


class ClaudeResponseCache:
    """
    In-memory cache for Claude API responses with TTL expiry.

    Cache strategy:
    - crowd_insights: 30 min TTL (market data changes slowly)
    - sell_analysis: 45 min TTL (squad-specific, needs recalc on transfers)
    - buy_analysis: 45 min TTL (depends on sell candidates)
    - squad_analysis: 30 min TTL (depends on squad + transfers)
    - gw_performance: 60 min TTL (historical, doesn't change)
    """

    # TTL in seconds per endpoint type
    TTL_CONFIG = {
        "crowd_insights": 30 * 60,      # 30 minutes
        "sell_analysis": 45 * 60,       # 45 minutes
        "buy_analysis": 45 * 60,        # 45 minutes
        "squad_analysis": 30 * 60,      # 30 minutes
        "gw_performance": 60 * 60,      # 60 minutes
    }

    def __init__(self, max_entries: int = 500):
        self._cache: dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0
        self._api_calls_saved = 0

    def _generate_key(self, endpoint: str, **kwargs) -> str:
        """Generate a unique cache key from endpoint and parameters."""
        # Sort kwargs to ensure consistent key generation
        sorted_items = sorted(kwargs.items())
        # Create hash of the parameters to keep key length manageable
        param_str = json.dumps(sorted_items, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
        return f"{endpoint}:{param_hash}"

    def get(self, endpoint: str, **kwargs) -> Optional[Any]:
        """Retrieve cached response if valid."""
        key = self._generate_key(endpoint, **kwargs)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        # Check expiry
        if time.time() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        self._api_calls_saved += 1
        logger.info(f"Cache HIT for {endpoint} (age: {int(time.time() - entry.created_at)}s, saved API call)")
        return entry.data

    def set(self, endpoint: str, data: Any, **kwargs) -> None:
        """Store response in cache with TTL."""
        # Evict expired entries if cache is full
        if len(self._cache) >= self._max_entries:
            self._evict_expired()

        # If still full, evict oldest entries
        if len(self._cache) >= self._max_entries:
            self._evict_oldest(count=50)

        key = self._generate_key(endpoint, **kwargs)
        ttl = self.TTL_CONFIG.get(endpoint, 30 * 60)  # Default 30 min
        now = time.time()

        self._cache[key] = CacheEntry(
            data=data,
            expires_at=now + ttl,
            created_at=now,
        )
        logger.debug(f"Cached {endpoint} response (TTL: {ttl//60} min)")

    def _evict_expired(self) -> int:
        """Remove all expired entries."""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if v.expires_at < now]
        for key in expired_keys:
            del self._cache[key]
        if expired_keys:
            logger.debug(f"Evicted {len(expired_keys)} expired cache entries")
        return len(expired_keys)

    def _evict_oldest(self, count: int = 50) -> None:
        """Evict oldest entries to make room."""
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].created_at
        )
        for key, _ in sorted_entries[:count]:
            del self._cache[key]
        logger.debug(f"Evicted {count} oldest cache entries")

    def invalidate(self, endpoint: Optional[str] = None) -> int:
        """Invalidate cache entries. If endpoint is None, invalidate all."""
        if endpoint is None:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Invalidated all {count} cache entries")
            return count

        # Invalidate specific endpoint
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{endpoint}:")]
        for key in keys_to_remove:
            del self._cache[key]
        logger.info(f"Invalidated {len(keys_to_remove)} cache entries for {endpoint}")
        return len(keys_to_remove)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        valid_entries = sum(1 for e in self._cache.values() if e.expires_at > now)
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._cache) - valid_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "api_calls_saved": self._api_calls_saved,
            "max_entries": self._max_entries,
        }


# Global cache instance
_claude_cache = ClaudeResponseCache()


# System prompt for FPL insights generation
CROWD_INSIGHTS_SYSTEM_PROMPT = """You are an expert Fantasy Premier League analyst. Your job is to analyse raw FPL data and generate ORIGINAL, personalised insights.

IMPORTANT: Always use British English spelling (e.g., analyse, personalised, optimise, favourite, colour, defence, etc.).

YOUR TASK:
Analyze the provided market data and generate 6 UNIQUE insight cards. You must:
1. INDEPENDENTLY select the best players for each category from the raw data
2. Find patterns and opportunities that simple algorithms might miss
3. Consider the USER'S SQUAD context - they already own certain players
4. Provide ACTIONABLE recommendations with conviction

TONE & STYLE:
- Confident, opinionated, direct
- Write like an FPL expert friend giving advice
- Use specific numbers and stats
- Keep descriptions to 2-3 sentences max
- Be decisive - "This is the week's sneaky differential play" not "This might be worth considering"

OUTPUT FORMAT:
You must return a JSON object with exactly 6 insight cards. Each card has:
- type: one of "smart_money", "under_radar", "bandwagon", "panic_sell", "value_pick", "squad_alert"
- title: short headline with player name(s)
- icon: emoji (choose appropriate: 📈💎🚀📉💰⚠️)
- tag: action word (BUY, HOLD, AVOID, VALUE, URGENT, WARNING, etc.)
- tag_color: "green", "red", "amber", "blue", or "gray"
- description: 2-3 sentences of personalized analysis
- players: array of player objects (use provided data, include player ID)

CARD TYPES (you MUST generate exactly these 6 types):
1. smart_money: Low ownership players (<10%) gaining transfers rapidly, NOT in user's squad. Tag: BUY (green)
2. under_radar: Budget gems (<7m) with excellent form, NOT in user's squad. Tag: BUY (green)
3. bandwagon: Massive transfer movement (>200k), NOT in user's squad. Tag: TRENDING (blue)
4. panic_sell: Players being mass-sold - analyze if justified. Can be any player. Tag: HOLD/AVOID (amber/red)
5. value_pick: Best value players - high form relative to price (<=6.5m), NOT in user's squad. Tag: VALUE (green)
6. squad_alert: CRITICAL - Find the user's OWN players (in_squad=true) with HIGH TRANSFERS OUT. This warns them about their players being dumped. Tag: URGENT/WARNING (red/amber)

CRITICAL RULES:
- Cards 1, 2, 3, 5 (smart_money, under_radar, bandwagon, value_pick) must ONLY recommend players NOT in the user's squad
- Card 6 (squad_alert) MUST ONLY include players the user OWNS (in_squad=true) who have high transfers_out
- Look at the "PLAYERS BEING SOLD" section to find candidates for squad_alert - if any are marked [IN SQUAD], use them!

IMPORTANT - PLAYER DATA FORMAT:
For each player in the "players" array, use RAW NUMERIC VALUES (no formatting):
- id: integer (player ID)
- name: string (player name)
- team: string (team short name like "CHE", "ARS")
- price: number (e.g., 5.1 not "£5.1m")
- form: number (e.g., 9.6 not "9.6")
- ownership: number (e.g., 6.6 not "6.6%")
- transfers_in: integer (e.g., 219000 not "+219k")
- transfers_out: integer (e.g., 6000 not "-6k")
- in_squad: boolean (true/false)

PERSONALIZATION:
- For BUY cards (smart_money, under_radar, bandwagon, value_pick): frame as opportunity since they DON'T own these players
- For squad_alert: warn them about THEIR players being sold - "Warning: Your player X is being dumped..."
"""

# System prompt for sell analysis
SELL_ANALYSIS_SYSTEM_PROMPT = """You are an elite FPL analyst known for decisive, data-driven transfer advice.

IMPORTANT: Always use British English spelling (e.g., analyse, personalised, optimise, favourite, colour, defence, etc.).

## YOUR MINDSET
- Points delivered > hypothetical risks. A player scoring points is valuable, period.
- Playing time is EVERYTHING. A benched player delivers 0 points regardless of quality.
- The crowd is often late or wrong. 100k selling doesn't mean you should - ask WHY.
- Every player has trade-offs. Your job is to WEIGH them, not just list them.
- Be contrarian when the data supports it. Conventional wisdom loses leagues.

## CRITICAL SELL PRIORITY (in order of importance)
1. **ROTATION RISK (Nailedness < 4.0)** - Players not starting = 0 points. HIGHEST PRIORITY.
2. **INJURY/SUSPENSION (Status != Available)** - Can't score if they can't play. CRITICAL.
3. **LOW MINUTES (<200 total)** - Not getting game time = sell immediately.
4. **FORM COLLAPSE + HARD FIXTURES** - Only sell form dips if fixtures turn bad too.
5. **MASS TRANSFERS OUT** - Consider why the crowd is selling, but don't follow blindly.

## SMARTPLAY SCORES (ML-powered)
- **Nailedness Score (0-10)**: Rotation risk. <4.0 = SELL, 4.0-6.0 = MONITOR, >6.0 = SAFE
- **Final Score (0-10)**: Overall pick quality. <5.0 = weak pick, >7.0 = strong pick
- **Fixture Score (0-10)**: Next 5 fixtures. <4.0 = tough run ahead

## FIXTURE RUN SCORING
- EASY (5-10): Strong hold signal - good fixtures coming
- MIXED (11-17): Neutral - other factors decide
- HARD (18-25): Consider selling if combined with other issues

## HOW TO ANALYZE
For each player, find the REAL story. Prioritize PLAYING TIME and ROTATION RISK over form dips.

## EXAMPLE ANALYSES (learn from these)

**KEEPER Examples:**
- "Salah (form 9.2, 3 yellows, MIXED fixtures) - KEEPER. He's the #1 scoring player with 2.1 xGI/90. Yellow card risk is noise - you don't bench your best asset for a hypothetical suspension. Alternative view: Could miss 1 game if unlucky, but he'll outscore replacements anyway."

- "Saka (form 7.8, HARD fixtures) - KEEPER. Yes, fixtures look tough on paper, but Arsenal create chances against anyone. His underlying stats (0.45 xG + 0.38 xA per 90) are elite. Form > fixtures for explosive players. Alternative view: Could rotate in tough games."

- "Lewis (form 5.1, £4.2m, EASY fixtures) - KEEPER. Budget enabler playing every minute for Newcastle. Incredible value - lets you afford premiums elsewhere. Don't waste a transfer on a bench player doing his job. Alternative view: Low ceiling, but that's fine for his role."

**HOLD Examples:**
- "Palmer (form 4.2, minor knock, EASY fixtures) - HOLD. Form dip is concerning but underlying stats still solid (0.52 xG/90). Easy fixtures ahead and he's fixture-proof at home. Wait 1 GW before panicking. Alternative view: Consider selling if blanks again, but give him the fixtures first."

- "Isak (flagged 75%, MIXED fixtures) - HOLD. The 75% flag is precautionary - he trained today. Newcastle need him for top 4 push. Don't sell on yellow flags, wait for actual news. Alternative view: Have a plan B ready if ruled out."

- "Watkins (form 5.5, 120k selling, MIXED fixtures) - HOLD. The crowd is panicking after 2 blanks but his xG is still 0.55/90. Villa's fixtures turn good in 3 GWs. Selling into bad form often backfires. Alternative view: If you MUST sell, do it before price drop."

**SELL Examples (prioritized correctly):**

CRITICAL PRIORITY - Rotation Risk:
- "Munoz (Nailedness=2.3/10, Minutes=45) - SELL (CRITICAL). Lost his starting spot - only 45 minutes total. Nailedness score of 2.3 screams rotation risk. A benched player scores 0 points. Move him out NOW before he drops in price. Alternative view: None - this is an easy sell."

- "Digne (Nailedness=3.8/10, Minutes=180, Doubtful 25%) - SELL (CRITICAL). Being managed for fitness, low chance of playing, and when he does play it's often 60 mins. Nailedness 3.8 confirms rotation risk. Can't rely on him. Alternative view: Could regain place, but too risky."

HIGH PRIORITY - Injury/Long-term Issues:
- "Haaland (form 3.2, INJURED 4 weeks, MIXED fixtures) - SELL (high priority). £15m locked up for a month. That's 3-4 premium midfielders worth of budget. Downgrade, spread funds, and reassess when fit. Alternative view: Only if you have a good plan for the money."

- "Rashford (Nailedness=4.1/10, form 2.1, Minutes=270, HARD fixtures) - SELL (high priority). Lost his place to Garnacho (270 mins total suggests rotation). Nailedness barely above danger zone. When combined with poor form (0.08 xG/90) and tough fixtures, this is a clear sell. Alternative view: Could regain form, but opportunity cost is too high."

MEDIUM PRIORITY - Form Collapse + Bad Fixtures (BUT starting regularly):
- "Thiago Silva (Nailedness=8.5/10, form 5.0, MIXED fixtures) - HOLD (low priority). Yes, form is mediocre and he's 32.1% owned with transfers out. BUT nailedness of 8.5 means he's nailed in Brighton's defense. He's PLAYING 90 mins. Form dip is noise - don't sell a starting player for minor form issues. Alternative view: Could sell if you desperately need funds, but he's not urgent."

- "Bowen (Nailedness=7.2/10, form 4.1, HARD fixtures) - SELL (medium priority). West Ham are in crisis AND fixtures are brutal. But he's starting (nailed at 7.2). Only sell if you have a clear upgrade path. Alternative view: West Ham could turn it around, but fixtures say otherwise."

**LOW PRIORITY Examples (healthy squad):**
- "Martinez (form 5.0, MIXED fixtures) - KEEPER (low priority). Set-and-forget keeper doing his job. No action needed. Alternative view: None - this is what you want from a GK."

## VERDICT CATEGORIES
- SELL: Clear issues that won't resolve soon. Act now.
- HOLD: Monitor situation. Wait for more info or fixtures to turn.
- KEEPER: Core player. Don't sell unless desperate.

## PRIORITY: critical > high > medium > low

## OUTPUT
Return exactly 5 players as JSON (most urgent first):
{
  "analysis": [
    {"id": 123, "name": "Player", "verdict": "SELL", "priority": "critical", "reasoning": "Your analysis with specific stats", "alternative_view": "Counter-argument"}
  ],
  "summary": "One sentence overall squad assessment"
}
"""

# System prompt for buy analysis
BUY_ANALYSIS_SYSTEM_PROMPT = """You are an elite FPL analyst known for finding the best transfer targets.

IMPORTANT: Always use British English spelling (e.g., analyse, personalised, optimise, favourite, colour, defence, etc.).

## YOUR MINDSET
- Form + Fixtures = Points. Best buys have both.
- Underlying stats reveal the truth. Goals vs xG shows luck - buy the unlucky ones.
- Price doesn't equal points. A £5m player on form beats a £10m player struggling.
- Timing matters. Buy BEFORE price rises, not after.
- The best transfers upgrade your weakest position, not your strongest.

## FIXTURE RUN SCORING
- EASY (5-10): Strong buy signal - prioritize these players
- MIXED (11-17): Form and value decide
- HARD (18-25): Only buy if exceptional form/underlying stats

## EXAMPLE RECOMMENDATIONS (learn from these)

**STRONG_BUY Examples:**
- "Mbeumo (£7.2m, form 8.1, EASY fixtures) - STRONG_BUY. Brentford's main man with 0.58 xG+xA/90, on penalties, and plays LEI, SOU, IPS next. Perfect mid-price pick. He's outscoring premiums at half the price."

- "Cunha (£6.8m, form 7.5, EASY fixtures) - STRONG_BUY. Wolves' talisman with 4 goals in 5 games. Eye test and stats align - he's everywhere in their attack. Fixture swing to easy run makes this the perfect time."

- "Ait-Nouri (£4.8m, form 6.2, EASY fixtures) - STRONG_BUY. Attacking wingback with 0.15 xG + 0.22 xA per game - elite for a defender. At £4.8m, he's a bench player's price with starter's returns. No-brainer enabler."

**BUY Examples:**
- "Isak (£8.5m, form 6.8, MIXED fixtures) - BUY. xG of 0.72/90 is elite, just been slightly unlucky. Newcastle create plenty - regression to mean coming. Premium striker actually worth the price."

- "Gordon (£7.3m, form 5.5, EASY fixtures) - BUY. Underlying stats strong (0.35 xG, 0.28 xA), and Newcastle's fixtures turn. Could explode with Isak and easy games. Buy before the bandwagon."

- "Flekken (£4.5m, form 4.8, EASY fixtures) - BUY. Brentford's defense improving, 4 clean sheets in 8 games. At £4.5m with EASY fixtures, he's the best budget GK option right now."

**WATCHLIST Examples:**
- "Bruno (£8.3m, form 4.2, HARD fixtures) - WATCHLIST. Still on pens and set pieces, but Man Utd are a mess. Wait for fixtures to turn or a new manager bounce. Don't buy into chaos."

- "Solanke (£7.5m, form 5.1, MIXED fixtures) - WATCHLIST. Spurs creating chances, he's just not finishing them. If Richarlison stays out, he'll start. Wait 1 more GW for clarity."

## VERDICT CATEGORIES
- STRONG_BUY: Elite option - form + fixtures aligned. Act now before price rise.
- BUY: Strong option - clear upgrade on what you have.
- WATCHLIST: Monitor - interesting but wait for trigger (injury, fixtures, form).

## PRIORITY: critical > high > medium > low

## OUTPUT
Return 5-7 recommendations as JSON (best first):
{
  "recommendations": [
    {"id": 123, "name": "Player", "position": "MID", "verdict": "STRONG_BUY", "priority": "critical", "reasoning": "Your analysis with specific stats", "replaces": "Player being replaced or empty"}
  ],
  "summary": "One sentence transfer strategy"
}
"""


class ClaudeService:
    """Service for Claude AI-powered insights with response caching."""

    def __init__(self):
        self.client = None
        self._cache = _claude_cache  # Use global cache for cross-request efficiency
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Claude client lazily."""
        import os
        # Check both settings and environment (Railway sets env vars after import)
        api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        if api_key and self.client is None:
            self.client = anthropic.Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        """Check if Claude API is configured."""
        import os
        # Lazy initialization if not already done
        if self.client is None:
            self._initialize_client()
        # Check both settings and environment
        api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        return self.client is not None and bool(api_key)

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        return self._cache.get_stats()

    def invalidate_cache(self, endpoint: Optional[str] = None) -> int:
        """Invalidate cache entries for an endpoint or all."""
        return self._cache.invalidate(endpoint)

    def _parse_number(self, value) -> float:
        """Parse a number from various formats (e.g., '£5.1m', '6.6%', 5.1)."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove common formatting characters
            cleaned = value.replace("£", "").replace("m", "").replace("%", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    def _parse_int(self, value) -> int:
        """Parse an integer from various formats (e.g., '+219k', '-6k', 219000)."""
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            # Remove common formatting characters
            cleaned = value.replace("+", "").replace("-", "").replace(",", "").strip()
            # Handle 'k' suffix (thousands)
            if cleaned.lower().endswith("k"):
                try:
                    return int(float(cleaned[:-1]) * 1000)
                except ValueError:
                    return 0
            try:
                return int(float(cleaned))
            except ValueError:
                return 0
        return 0

    async def generate_crowd_insights(
        self,
        base_insights: CrowdInsightsResponse,
        squad_player_ids: list[int],
        all_players_data: dict,
    ) -> CrowdInsightsResponse:
        """Generate AI-enhanced crowd insights with caching."""
        if not self.is_available():
            logger.warning("Claude API not configured, returning base insights")
            return base_insights

        # Check cache first - key by squad player IDs (sorted for consistency)
        cache_key_data = {
            "squad": sorted(squad_player_ids),
            "player_count": len(all_players_data),
        }
        cached = self._cache.get("crowd_insights", **cache_key_data)
        if cached is not None:
            return cached

        try:
            # Build context for Claude
            context = self._build_context(base_insights, squad_player_ids, all_players_data)

            # Call Claude
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=2500,
                system=CROWD_INSIGHTS_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Analyze this FPL market data and generate 6 ORIGINAL insight cards.

{context}

IMPORTANT:
- Analyze the data INDEPENDENTLY - don't just pick the first player in each list
- Look for interesting patterns, value picks, or opportunities others might miss
- Consider the USER'S SQUAD when making recommendations (marked with [IN SQUAD])
- For your_edge: highlight the user's OWN differential picks (<15% owned) that are performing well

Return ONLY valid JSON:
{{
  "insights": [
    {{
      "type": "smart_money",
      "title": "Smart Money Alert: [Player Name]",
      "icon": "📈",
      "tag": "BUY",
      "tag_color": "green",
      "description": "2-3 sentence analysis with specific stats",
      "players": [{{"id": 123, "name": "...", "team": "...", "price": 5.1, "form": 7.2, "ownership": 3.5, "transfers_in": 150000, "transfers_out": 5000, "in_squad": false}}]
    }},
    // ... 5 more cards (under_radar, bandwagon, panic_sell, value_pick, squad_alert)
  ]
}}""",
                    }
                ],
            )

            # Parse response with security validation
            content = response.content[0].text
            parsed = _safe_parse_ai_json(content)

            # Build response with AI-generated insights
            ai_insights = []
            for insight_data in parsed.get("insights", []):
                players = []
                for p in insight_data.get("players", []):
                    # Clean up any formatted values from Claude
                    price = self._parse_number(p.get("price", 0))
                    form = self._parse_number(p.get("form", 0))
                    ownership = self._parse_number(p.get("ownership", 0))
                    transfers_in = self._parse_int(p.get("transfers_in", 0))
                    transfers_out = self._parse_int(p.get("transfers_out", 0))

                    players.append(CrowdInsightPlayer(
                        id=p.get("id", 0),
                        name=p.get("name", ""),
                        team=p.get("team", ""),
                        price=price,
                        form=form,
                        ownership=ownership,
                        transfers_in=transfers_in,
                        transfers_out=transfers_out,
                        in_squad=p.get("in_squad", False),
                    ))

                ai_insights.append(CrowdInsightCard(
                    type=insight_data.get("type", ""),
                    title=insight_data.get("title", ""),
                    icon=insight_data.get("icon", ""),
                    tag=insight_data.get("tag", ""),
                    tag_color=insight_data.get("tag_color", "gray"),
                    description=insight_data.get("description", ""),
                    players=players,
                    value=insight_data.get("value"),
                ))

            result = CrowdInsightsResponse(
                insights=ai_insights,
                template_score=base_insights.template_score,
                avg_ownership=base_insights.avg_ownership,
            )
            # Cache the successful response
            self._cache.set("crowd_insights", result, **cache_key_data)
            logger.info("Claude crowd_insights response cached")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return base_insights
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return base_insights
        except Exception as e:
            logger.error(f"Unexpected error in Claude service: {e}")
            return base_insights

    def _build_context(
        self,
        base_insights: CrowdInsightsResponse,
        squad_player_ids: list[int],
        all_players_data: dict,
    ) -> str:
        """Build context string for Claude with FULL player data for independent analysis."""
        lines = []

        # Squad info
        lines.append("## USER'S SQUAD (15 players)")
        squad_players = []
        for pid in squad_player_ids:
            if pid in all_players_data:
                p = all_players_data[pid]
                squad_players.append(p)
                lines.append(
                    f"- ID:{p['id']} {p['name']} ({p['team']}) - £{p['price']}m, "
                    f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                    f"+{p['transfers_in']//1000}k/-{p['transfers_out']//1000}k transfers"
                )

        # Stats
        lines.append(f"\n## SQUAD STATS")
        lines.append(f"Average ownership: {base_insights.avg_ownership:.1f}%")

        # FULL MARKET DATA - Let Claude analyze independently
        lines.append("\n## TOP TRANSFER TARGETS (highest transfers in, not in squad)")
        top_transfers_in = sorted(
            [p for p in all_players_data.values() if p['id'] not in squad_player_ids],
            key=lambda x: x['transfers_in'],
            reverse=True
        )[:15]
        for p in top_transfers_in:
            lines.append(
                f"- ID:{p['id']} {p['name']} ({p['team']}) - £{p['price']}m, "
                f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                f"+{p['transfers_in']//1000}k transfers in"
            )

        lines.append("\n## PLAYERS BEING SOLD (highest transfers out)")
        top_transfers_out = sorted(
            all_players_data.values(),
            key=lambda x: x['transfers_out'],
            reverse=True
        )[:10]
        for p in top_transfers_out:
            in_squad = "[IN SQUAD]" if p['id'] in squad_player_ids else ""
            lines.append(
                f"- ID:{p['id']} {p['name']} ({p['team']}) - £{p['price']}m, "
                f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                f"-{p['transfers_out']//1000}k transfers out {in_squad}"
            )

        lines.append("\n## HOT FORM PLAYERS (form >= 7, not in squad)")
        hot_form = sorted(
            [p for p in all_players_data.values() if p['form'] >= 7.0 and p['id'] not in squad_player_ids],
            key=lambda x: x['form'],
            reverse=True
        )[:15]
        for p in hot_form:
            lines.append(
                f"- ID:{p['id']} {p['name']} ({p['team']}) - £{p['price']}m, "
                f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                f"+{p['transfers_in']//1000}k/-{p['transfers_out']//1000}k"
            )

        lines.append("\n## LOW OWNERSHIP GEMS (<5% owned, form >= 5, not in squad)")
        low_own_gems = sorted(
            [p for p in all_players_data.values()
             if p['ownership'] < 5 and p['form'] >= 5.0 and p['id'] not in squad_player_ids],
            key=lambda x: x['form'],
            reverse=True
        )[:10]
        for p in low_own_gems:
            lines.append(
                f"- ID:{p['id']} {p['name']} ({p['team']}) - £{p['price']}m, "
                f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                f"+{p['transfers_in']//1000}k transfers in"
            )

        lines.append("\n## SMART MONEY MOVES (low ownership <10%, high transfers in >50k)")
        smart_money = sorted(
            [p for p in all_players_data.values()
             if p['ownership'] < 10 and p['transfers_in'] > 50000],
            key=lambda x: x['transfers_in'] / max(x['ownership'], 0.1),
            reverse=True
        )[:10]
        for p in smart_money:
            in_squad = "[IN SQUAD]" if p['id'] in squad_player_ids else ""
            lines.append(
                f"- ID:{p['id']} {p['name']} ({p['team']}) - £{p['price']}m, "
                f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                f"+{p['transfers_in']//1000}k transfers in {in_squad}"
            )

        lines.append("\n## ⚠️ YOUR PLAYERS BEING SOLD (squad players with high transfers out) - USE FOR squad_alert CARD!")
        squad_being_sold = sorted(
            [p for p in squad_players if p['transfers_out'] > 20000],
            key=lambda x: x['transfers_out'],
            reverse=True
        )
        if squad_being_sold:
            for p in squad_being_sold:
                lines.append(
                    f"- ID:{p['id']} {p['name']} ({p['team']}) [IN SQUAD] - £{p['price']}m, "
                    f"form {p['form']:.1f}, {p['ownership']:.1f}% owned, "
                    f"-{p['transfers_out']//1000}k transfers OUT ⚠️"
                )
        else:
            lines.append("- No squad players being heavily sold (all stable)")

        return "\n".join(lines)

    async def analyze_sell_candidates(
        self,
        squad_data: list[dict],
        smartplay_scores: dict,
        crowd_insights: dict,
        market_context: dict,
    ) -> SellAnalysisResponse:
        """Analyze squad and determine which players to sell using Claude with caching."""
        if not self.is_available():
            logger.warning("Claude API not configured")
            return self._fallback_sell_analysis(squad_data, smartplay_scores)

        # Cache key based on squad player IDs
        squad_ids = sorted([p.get("id", 0) for p in squad_data])
        cache_key_data = {"squad_ids": squad_ids}
        cached = self._cache.get("sell_analysis", **cache_key_data)
        if cached is not None:
            return cached

        try:
            context = self._build_sell_context(squad_data, smartplay_scores, crowd_insights, market_context)

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                system=SELL_ANALYSIS_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Analyze this FPL squad and identify the 5 players to consider for transfer.

{context}

Return your analysis as JSON with exactly 5 players sorted by priority (critical first).
Focus on actionable insights - what should the manager do and why.""",
                    }
                ],
            )

            content = response.content[0].text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            parsed = json.loads(content.strip())

            candidates = []
            for item in parsed.get("analysis", [])[:5]:
                player_id = item.get("id", 0)
                sp_data = smartplay_scores.get(player_id, {})
                squad_player = next((p for p in squad_data if p.get("id") == player_id), {})

                candidates.append(SellCandidate(
                    id=player_id,
                    name=item.get("name", "Unknown"),
                    team=squad_player.get("team", ""),
                    position=squad_player.get("position", ""),
                    price=squad_player.get("price", 0.0),
                    verdict=item.get("verdict", "HOLD"),
                    priority=item.get("priority", "low"),
                    reasoning=item.get("reasoning", ""),
                    alternative_view=item.get("alternative_view", ""),
                    smartplay_score=sp_data.get("final_score", 0.0),
                    nailedness_score=sp_data.get("nailedness_score", 0.0),
                    fixture_score=sp_data.get("fixture_score", 0.0),
                    form=squad_player.get("form", 0.0),
                    transfers_out=squad_player.get("transfers_out", 0),
                    status=squad_player.get("status", "a"),
                    news=squad_player.get("news", ""),
                ))

            result = SellAnalysisResponse(
                candidates=candidates,
                summary=parsed.get("summary", "Analysis complete."),
                ai_model="claude-sonnet-4",
            )
            # Cache the successful response
            self._cache.set("sell_analysis", result, **cache_key_data)
            logger.info("Claude sell_analysis response cached")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return self._fallback_sell_analysis(squad_data, smartplay_scores)
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return self._fallback_sell_analysis(squad_data, smartplay_scores)
        except Exception as e:
            logger.error(f"Unexpected error in sell analysis: {e}")
            return self._fallback_sell_analysis(squad_data, smartplay_scores)

    def _calculate_fixture_run_score(self, fixtures: list[dict], num_fixtures: int = 5) -> tuple[int, str, str]:
        """
        Calculate fixture run score for next N fixtures.

        Returns: (total_fdr, difficulty_label, fixture_summary)
        - total_fdr: Sum of FDR (5-25 scale for 5 fixtures)
        - difficulty_label: EASY (5-10), MIXED (11-17), HARD (18-25)
        - fixture_summary: e.g., "EVE(H), MCI(A), BOU(H)"
        """
        if not fixtures:
            return 0, "UNKNOWN", "No fixtures"

        fixtures_to_use = fixtures[:num_fixtures]
        total_fdr = sum(f.get('fdr', 3) for f in fixtures_to_use)

        # Determine difficulty label (based on 5 fixtures: min=5, max=25)
        if total_fdr <= 10:
            label = "EASY"
        elif total_fdr <= 17:
            label = "MIXED"
        else:
            label = "HARD"

        # Build summary string
        summary = ", ".join([
            f"{f.get('opponent', '???')}({'H' if f.get('home') else 'A'})"
            for f in fixtures_to_use
        ])

        return total_fdr, label, summary

    def _build_sell_context(
        self,
        squad_data: list[dict],
        smartplay_scores: dict,
        crowd_insights: dict,
        market_context: dict,
    ) -> str:
        """Build context for sell analysis."""
        lines = []

        lines.append("=" * 60)
        lines.append("## YOUR SQUAD - FULL DATA (15 players)")
        lines.append("=" * 60)
        lines.append("")

        for p in squad_data:
            status_text = {
                "a": "AVAILABLE",
                "d": f"DOUBTFUL ({p.get('chance_of_playing', 50)}%)",
                "i": "INJURED",
                "s": "SUSPENDED",
                "u": "UNAVAILABLE",
            }.get(p.get("status", "a"), "Unknown")

            lines.append(f"### {p.get('name')} ({p.get('team')}, {p.get('position')})")
            lines.append(f"ID: {p.get('id')} | Price: £{p.get('price', 0):.1f}m | Ownership: {p.get('ownership', 0):.1f}%")
            lines.append(f"Status: {status_text} | Minutes: {p.get('minutes', 0)}")
            if p.get("news"):
                lines.append(f"News: {p.get('news')}")

            # SmartPlay ML Scores
            sp_score = smartplay_scores.get(p.get('id'), {})
            lines.append(f"🤖 SmartPlay: Final={sp_score.get('final_score', 0):.1f}/10 | Nailedness={sp_score.get('nailedness_score', 0):.1f}/10 | Fixture={sp_score.get('fixture_score', 0):.1f}/10")

            lines.append(f"Form: {p.get('form', 0):.1f} | Total Points: {p.get('total_points', 0)}")
            lines.append(f"Goals: {p.get('goals_scored', 0)} | Assists: {p.get('assists', 0)} | Clean Sheets: {p.get('clean_sheets', 0)}")
            lines.append(f"xG: {p.get('expected_goals', 0):.2f} | xA: {p.get('expected_assists', 0):.2f}")

            transfers_out = p.get('transfers_out', 0)
            transfers_in = p.get('transfers_in', 0)
            transfer_text = f"Transfers: +{transfers_in//1000}k IN / -{transfers_out//1000}k OUT"
            if transfers_out > 100000:
                transfer_text += " 🚨 BEING MASS SOLD"
            lines.append(transfer_text)

            yellow_cards = p.get('yellow_cards', 0)
            if yellow_cards >= 3:
                cards_text = f"Yellow Cards: {yellow_cards}"
                if yellow_cards == 4:
                    cards_text += " ⚠️ ONE YELLOW FROM SUSPENSION"
                elif yellow_cards == 3:
                    cards_text += " ⚠️ TWO YELLOWS FROM SUSPENSION"
                lines.append(cards_text)

            fixtures = p.get("next_fixtures", [])
            if fixtures:
                # Calculate fixture run score
                total_fdr, difficulty, summary = self._calculate_fixture_run_score(fixtures)
                num_fixtures = min(len(fixtures), 5)
                max_fdr = num_fixtures * 5
                lines.append(f"FIXTURE RUN (next {num_fixtures}): {total_fdr}/{max_fdr} ({difficulty}) - {summary}")

            lines.append("")

        if market_context.get("top_transfers_in"):
            lines.append("\n## PLAYERS BEING BOUGHT (Top 10)")
            for p in market_context.get("top_transfers_in", [])[:10]:
                lines.append(f"  {p.get('name')} ({p.get('team')}) - Form:{p.get('form', 0):.1f}, +{p.get('transfers_in', 0)//1000}k")

        # Add crowd intelligence insights
        if crowd_insights:
            lines.append("\n" + "=" * 60)
            lines.append("## CROWD INTELLIGENCE (what the FPL community is doing)")
            lines.append("=" * 60)

            insights = crowd_insights.get("insights", [])
            for insight in insights:
                insight_type = insight.get("type", "")
                title = insight.get("title", "")
                tag = insight.get("tag", "")
                description = insight.get("description", "")
                players = insight.get("players", [])

                # Focus on insights relevant to sell analysis
                if insight_type in ["squad_alert", "panic_sell", "smart_money"]:
                    lines.append(f"\n### {title} [{tag}]")
                    lines.append(f"{description}")
                    if players:
                        for p in players[:3]:
                            in_squad = "[YOUR PLAYER]" if p.get("in_squad") else ""
                            lines.append(f"  - {p.get('name')} ({p.get('team')}) Form:{p.get('form', 0):.1f} {in_squad}")

            # Add template score context
            template_score = crowd_insights.get("template_score", 50)
            avg_ownership = crowd_insights.get("avg_ownership", 0)
            if template_score > 70:
                lines.append(f"\n📊 Your squad is TEMPLATE ({template_score:.0f}% similarity, avg {avg_ownership:.1f}% ownership)")
            elif template_score < 30:
                lines.append(f"\n📊 Your squad is DIFFERENTIAL ({template_score:.0f}% similarity, avg {avg_ownership:.1f}% ownership)")

        return "\n".join(lines)

    def _fallback_sell_analysis(
        self,
        squad_data: list[dict],
        smartplay_scores: dict,
    ) -> SellAnalysisResponse:
        """Fallback rule-based sell analysis when Claude is unavailable."""
        candidates = []

        for p in squad_data:
            score = 0
            reasons = []

            # Critical issues
            if p.get("status") == "i":
                score += 50
                reasons.append(f"Injured: {p.get('news', 'Unknown return')}")
            elif p.get("status") == "s":
                score += 50
                reasons.append("Suspended")
            elif p.get("status") == "d":
                score += 25
                reasons.append(f"Doubtful ({p.get('chance_of_playing', 50)}%)")

            # Form issues
            form = p.get("form", 0) or 0
            if form < 3.0:
                score += 20
                reasons.append(f"Poor form ({form:.1f})")
            elif form < 5.0:
                score += 10
                reasons.append(f"Below average form ({form:.1f})")

            # Low minutes (rotation risk)
            minutes = p.get("minutes", 0) or 0
            if minutes < 200:
                score += 15
                reasons.append(f"Low minutes ({minutes})")

            # Premium underperforming
            price = p.get("price", 0) or 0
            if price >= 8.0 and form < 4.0:
                score += 15
                reasons.append("Premium player underperforming")

            # Mass selling signal
            transfers_out = p.get("transfers_out", 0) or 0
            if transfers_out > 100000:
                score += 10
                reasons.append(f"{transfers_out//1000}k managers selling")
            elif transfers_out > 50000:
                score += 5
                reasons.append(f"{transfers_out//1000}k managers selling")

            # SmartPlay scores (if available)
            sp_data = smartplay_scores.get(p.get('id'), {})
            nailedness = sp_data.get('nailedness_score', 0)
            if nailedness > 0 and nailedness < 4.0:
                score += 20
                reasons.append(f"Rotation risk (nailedness {nailedness:.1f}/10)")
            elif nailedness > 0 and nailedness < 6.0:
                score += 10
                reasons.append(f"Some rotation risk (nailedness {nailedness:.1f}/10)")

            candidates.append({
                "player": p,
                "score": score,
                "reasons": reasons,
                "sp_data": sp_data,
            })

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Assign verdicts based on RELATIVE position (top 5 get reviewed)
        # Top candidates should always be SELL options for the wizard
        result = []
        for i, c in enumerate(candidates[:5]):
            p = c["player"]
            score = c["score"]
            sp_data = c["sp_data"]

            # Assign verdict based on score AND position
            if score >= 50:
                verdict = "SELL"
                priority = "critical"
            elif score >= 30:
                verdict = "SELL"
                priority = "high"
            elif score >= 15:
                verdict = "SELL"
                priority = "medium"
            elif i < 3:  # Top 3 candidates get SELL even with low score
                verdict = "SELL"
                priority = "low"
            else:
                verdict = "HOLD"
                priority = "low"

            reasoning = ". ".join(c["reasons"]) if c["reasons"] else "Lowest priority in squad based on form and fixtures."

            result.append(SellCandidate(
                id=p.get("id", 0),
                name=p.get("name", "Unknown"),
                team=p.get("team", ""),
                position=p.get("position", ""),
                price=p.get("price", 0.0),
                verdict=verdict,
                priority=priority,
                reasoning=reasoning,
                alternative_view="Consider keeping if fixtures turn favorable." if verdict == "SELL" else "",
                smartplay_score=sp_data.get("final_score", 0.0),
                nailedness_score=sp_data.get("nailedness_score", 0.0),
                fixture_score=sp_data.get("fixture_score", 0.0),
                form=p.get("form", 0.0) or 0.0,
                transfers_out=p.get("transfers_out", 0) or 0,
                status=p.get("status", "a"),
                news=p.get("news", ""),
            ))

        return SellAnalysisResponse(
            candidates=result,
            summary="Rule-based analysis - top transfer candidates identified.",
            ai_model="rule-based-fallback",
        )

    async def analyze_buy_candidates(
        self,
        sell_candidates: list[dict],
        available_players: list[dict],
        squad_player_ids: list[int],
        budget: float,
        bank: float,
        positions_needed: list[str],
    ) -> BuyAnalysisResponse:
        """Analyze available players and recommend who to buy using Claude with caching."""
        if not self.is_available():
            logger.warning("Claude API not configured")
            return self._fallback_buy_analysis(sell_candidates, available_players, budget)

        # Cache key based on squad, sell candidates, and budget
        sell_ids = sorted([sc.get("id", 0) for sc in sell_candidates])
        cache_key_data = {
            "squad": sorted(squad_player_ids),
            "sell_ids": sell_ids,
            "budget": round(budget, 1),
            "positions": sorted(positions_needed),
        }
        cached = self._cache.get("buy_analysis", **cache_key_data)
        if cached is not None:
            return cached

        try:
            context = self._build_buy_context(
                sell_candidates, available_players, squad_player_ids, budget, bank, positions_needed
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                system=BUY_ANALYSIS_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Analyze these FPL players and recommend the best 5-7 players to BUY.

{context}

Return your recommendations as JSON with players sorted by priority (critical first).""",
                    }
                ],
            )

            content = response.content[0].text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            parsed = json.loads(content.strip())

            recommendations = []
            for item in parsed.get("recommendations", [])[:7]:
                player_id = item.get("id", 0)
                player_data = next((p for p in available_players if p.get("id") == player_id), {})

                recommendations.append(BuyCandidate(
                    id=player_id,
                    name=item.get("name", "Unknown"),
                    team=player_data.get("team", ""),
                    position=player_data.get("position", item.get("position", "")),
                    price=player_data.get("price", 0.0),
                    verdict=item.get("verdict", "BUY"),
                    priority=item.get("priority", "medium"),
                    reasoning=item.get("reasoning", ""),
                    form=player_data.get("form", 0.0),
                    total_points=player_data.get("total_points", 0),
                    ownership=player_data.get("ownership", 0.0),
                    transfers_in=player_data.get("transfers_in", 0),
                    expected_goals=player_data.get("expected_goals", 0.0),
                    expected_assists=player_data.get("expected_assists", 0.0),
                    ict_index=player_data.get("ict_index", 0.0),
                    next_fixtures=player_data.get("next_fixtures", []),
                    replaces=item.get("replaces", ""),
                    price_diff=0.0,
                ))

            result = BuyAnalysisResponse(
                recommendations=recommendations,
                budget_available=budget,
                summary=parsed.get("summary", "Analysis complete."),
                ai_model="claude-sonnet-4",
            )
            # Cache the successful response
            self._cache.set("buy_analysis", result, **cache_key_data)
            logger.info("Claude buy_analysis response cached")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return self._fallback_buy_analysis(sell_candidates, available_players, budget)
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return self._fallback_buy_analysis(sell_candidates, available_players, budget)
        except Exception as e:
            logger.error(f"Unexpected error in buy analysis: {e}")
            return self._fallback_buy_analysis(sell_candidates, available_players, budget)

    def _build_buy_context(
        self,
        sell_candidates: list[dict],
        available_players: list[dict],
        squad_player_ids: list[int],
        budget: float,
        bank: float,
        positions_needed: list[str],
    ) -> str:
        """Build context for buy analysis."""
        lines = []

        lines.append(f"Budget available: £{budget:.1f}m")
        lines.append(f"Positions needed: {', '.join(positions_needed) if positions_needed else 'Any'}")
        lines.append("")

        if sell_candidates:
            lines.append("## PLAYERS BEING SOLD")
            for sc in sell_candidates:
                lines.append(f"- {sc.get('name')} ({sc.get('position')}) - £{sc.get('price', 0):.1f}m")
        lines.append("")

        lines.append("## TOP AVAILABLE PLAYERS BY FORM")
        positions = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
        for p in available_players:
            pos = p.get("position", "")
            if pos in positions and p.get("id") not in squad_player_ids:
                positions[pos].append(p)

        for pos, players in positions.items():
            sorted_players = sorted(players, key=lambda x: x.get("form", 0), reverse=True)[:10]
            lines.append(f"\n### {pos} - Top 10 by Form")
            for p in sorted_players:
                fixtures = p.get("next_fixtures", [])
                if fixtures:
                    total_fdr, difficulty, _ = self._calculate_fixture_run_score(fixtures)
                    fixture_info = f"| FIX:{difficulty}"
                else:
                    fixture_info = ""
                lines.append(
                    f"  ID:{p.get('id')} {p.get('name')} ({p.get('team')}) - "
                    f"£{p.get('price', 0):.1f}m | Form:{p.get('form', 0):.1f} {fixture_info} | "
                    f"+{p.get('transfers_in', 0)//1000}k"
                )

        return "\n".join(lines)

    def _fallback_buy_analysis(
        self,
        sell_candidates: list[dict],
        available_players: list[dict],
        budget: float,
    ) -> BuyAnalysisResponse:
        """Fallback rule-based buy analysis when Claude is unavailable."""
        affordable = [p for p in available_players if p.get("price", 0) <= budget]

        # Get positions needed from sell candidates
        positions_needed = [sc.get("position", "") for sc in sell_candidates]

        recommendations = []

        # Get top 3 players for EACH position needed
        for position in set(positions_needed):
            if not position:
                continue

            position_players = [p for p in affordable if p.get("position") == position]
            sorted_by_form = sorted(position_players, key=lambda x: x.get("form", 0), reverse=True)

            for p in sorted_by_form[:3]:  # Top 3 per position
                recommendations.append(BuyCandidate(
                    id=p.get("id", 0),
                    name=p.get("name", "Unknown"),
                    team=p.get("team", ""),
                    position=p.get("position", ""),
                    price=p.get("price", 0.0),
                    verdict="BUY",
                    priority="medium",
                    reasoning=f"High form ({p.get('form', 0):.1f}) within budget. Good replacement for {position}.",
                    form=p.get("form", 0.0),
                    total_points=p.get("total_points", 0),
                    ownership=p.get("ownership", 0.0),
                    transfers_in=p.get("transfers_in", 0),
                    expected_goals=p.get("expected_goals", 0.0),
                    expected_assists=p.get("expected_assists", 0.0),
                    ict_index=p.get("ict_index", 0.0),
                    next_fixtures=p.get("next_fixtures", []),
                    replaces="",
                    price_diff=0.0,
                ))

        return BuyAnalysisResponse(
            recommendations=recommendations,
            budget_available=budget,
            summary="Rule-based recommendations (Claude unavailable).",
            ai_model="rule-based-fallback",
        )


    async def analyze_squad(
        self,
        squad: list[dict],
        transfers: list[dict],
        bank: float,
        free_transfers: int,
        available_chips: list[str] | None = None,
        gameweek: int | None = None,
    ) -> "SquadAnalysisResponse":
        """Analyze squad with planned transfers and provide optimization tips."""
        from models import SquadAnalysisResponse, SquadOptimizationTip

        # Build squad context
        squad_by_pos = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
        total_value = 0.0
        teams_count: dict[str, int] = {}

        for p in squad:
            pos = p.get("position", "MID")
            if pos in squad_by_pos:
                squad_by_pos[pos].append(p)
            total_value += p.get("price", 0)
            team = p.get("team", "")
            teams_count[team] = teams_count.get(team, 0) + 1

        # Apply transfers
        for t in transfers:
            out_team = t.get("out_team", "")
            in_team = t.get("in_team", "")
            if out_team:
                teams_count[out_team] = max(0, teams_count.get(out_team, 0) - 1)
            if in_team:
                teams_count[in_team] = teams_count.get(in_team, 0) + 1
            total_value += t.get("price_diff", 0)

        # Available chips info
        chips_info = available_chips if available_chips else []
        chips_display = ", ".join(chips_info) if chips_info else "None available"

        # Gameweek context
        gw_display = gameweek if gameweek else "Unknown"
        gws_remaining = 38 - gameweek if gameweek else "Unknown"

        # Build prompt
        prompt = f"""Analyse this FPL squad and provide optimisation tips AND chip strategy.

IMPORTANT: Always use British English spelling (e.g., analyse, personalised, optimise, favourite, colour, defence, etc.).

SEASON CONTEXT:
- Current gameweek: GW{gw_display}
- Gameweeks remaining: {gws_remaining}
- Note: Consider chip usage timing - don't let chips go unused!

SQUAD OVERVIEW:
- Total value: £{total_value:.1f}m
- Bank: £{bank:.1f}m
- Free transfers: {free_transfers}
- Available chips: {chips_display}

SQUAD COMPOSITION:
- GKP: {len(squad_by_pos['GKP'])} players
- DEF: {len(squad_by_pos['DEF'])} players
- MID: {len(squad_by_pos['MID'])} players
- FWD: {len(squad_by_pos['FWD'])} players

TEAM DISTRIBUTION:
{', '.join(f'{t}: {c}' for t, c in sorted(teams_count.items(), key=lambda x: -x[1])[:5])}

CURRENT SQUAD:
{chr(10).join(f"- {p.get('name')}: {p.get('team')}, {p.get('position')}, £{p.get('price', 0):.1f}m, Form: {p.get('form', 0):.1f}" for p in squad[:15])}

PLANNED TRANSFERS ({len(transfers)}):
{chr(10).join(f"- OUT: {t.get('out_name')} → IN: {t.get('in_name')} (£{t.get('price_diff', 0):+.1f}m)" for t in transfers) if transfers else "No transfers planned"}

Provide analysis in JSON format:
{{
    "summary": "2-3 sentence overall assessment",
    "score": 75,  // 1-100 rating
    "strengths": ["strength 1", "strength 2"],
    "weaknesses": ["weakness 1", "weakness 2"],
    "optimization_tips": [
        {{
            "type": "balance|structure|value|risk|opportunity|transfer_chain",
            "icon": "emoji",
            "title": "short title",
            "description": "actionable tip",
            "priority": "high|medium|low"
        }}
    ],
    "chip_strategy": {{
        "chip": "wildcard|freehit|bboost|3xc|none",
        "chip_name": "Display Name (e.g., Bench Boost, Triple Captain)",
        "should_use": true/false,
        "reasoning": "2-3 sentences explaining why to use or not use a chip this week",
        "confidence": 75  // 0-100
    }}
}}

CHIP STRATEGY GUIDELINES:
- If no chips are available, set chip="none", should_use=false, reasoning="No chips available"
- BE PROACTIVE: Actually recommend chips when conditions are good, don't always default to saving!

WHEN TO RECOMMEND EACH CHIP (should_use=true):
- Bench Boost (bboost): Recommend when bench players have good form AND favourable fixtures this week. Look for bench players with 70%+ expected minutes and FDR 2-3.
- Triple Captain (3xc): Recommend for premium players (Haaland, Salah) with excellent home fixtures (FDR 2) or when they face weak defences. Don't wait for perfect conditions.
- Free Hit (freehit): Recommend when 3+ starters have blank gameweeks, injuries, or terrible fixtures (FDR 5).
- Wildcard: Recommend when squad needs 3+ transfers to fix structural issues, or to prepare for a fixture swing.

IMPORTANT: Chips are meant to be used during the season - be bold in recommendations when conditions are good (confidence 60%+). Managers regret unused chips more than used ones!

Generate 3-5 specific, actionable optimization tips. Focus on:
- Team balance and structure
- Fixture-based opportunities
- Value improvements
- Risk mitigation
- Transfer chains that meet FPL constraints (max 3 players per team)
"""

        if not self.client:
            # Fallback analysis
            return self._fallback_squad_analysis(squad, transfers, bank, free_transfers, teams_count)

        # Check cache - key by squad composition, transfers, and bank
        squad_ids = sorted([p.get("id", 0) for p in squad])
        transfer_ids = sorted([(t.get("out_id", 0), t.get("in_id", 0)) for t in transfers])
        cache_key_data = {
            "squad": squad_ids,
            "transfers": transfer_ids,
            "bank": round(bank, 1),
            "free_transfers": free_transfers,
        }
        cached = self._cache.get("squad_analysis", **cache_key_data)
        if cached is not None:
            return cached

        try:
            message = self.client.messages.create(
                model="claude-3-5-haiku-20241022",  # Haiku is 5x faster than Sonnet
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return self._fallback_squad_analysis(squad, transfers, bank, free_transfers, teams_count)

            data = json.loads(json_match.group())

            tips = [
                SquadOptimizationTip(
                    type=t.get("type", "balance"),
                    icon=t.get("icon", "💡"),
                    title=t.get("title", ""),
                    description=t.get("description", ""),
                    priority=t.get("priority", "medium"),
                )
                for t in data.get("optimization_tips", [])
            ]

            # Parse chip strategy
            chip_data = data.get("chip_strategy")
            chip_strategy = None
            if chip_data:
                chip_strategy = ChipStrategy(
                    chip=chip_data.get("chip", "none"),
                    chip_name=chip_data.get("chip_name", "No Chip"),
                    should_use=chip_data.get("should_use", False),
                    reasoning=chip_data.get("reasoning", "No recommendation available"),
                    confidence=chip_data.get("confidence", 50),
                )

            result = SquadAnalysisResponse(
                summary=data.get("summary", ""),
                score=data.get("score", 70),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                optimization_tips=tips,
                chip_strategy=chip_strategy,
                ai_model="claude-3.5-haiku",
            )
            # Cache the successful response
            self._cache.set("squad_analysis", result, **cache_key_data)
            logger.info("Claude squad_analysis response cached")
            return result

        except Exception as e:
            logger.error(f"Claude squad analysis error: {e}")
            return self._fallback_squad_analysis(squad, transfers, bank, free_transfers, teams_count)

    def _fallback_squad_analysis(
        self,
        squad: list[dict],
        transfers: list[dict],
        bank: float,
        free_transfers: int,
        teams_count: dict[str, int],
    ) -> "SquadAnalysisResponse":
        """Fallback rule-based squad analysis."""
        from models import SquadAnalysisResponse, SquadOptimizationTip

        tips = []
        strengths = []
        weaknesses = []

        # Check for team concentration
        max_from_team = max(teams_count.values()) if teams_count else 0
        if max_from_team >= 3:
            team_name = [t for t, c in teams_count.items() if c == max_from_team][0]
            weaknesses.append(f"Heavy exposure to {team_name} ({max_from_team} players)")
            tips.append(SquadOptimizationTip(
                type="risk",
                icon="⚠️",
                title="Team Concentration Risk",
                description=f"You have {max_from_team} players from {team_name}. Consider diversifying to reduce blank/injury risk.",
                priority="medium",
            ))

        # Check bank
        if bank > 2.0:
            weaknesses.append(f"Unused budget (£{bank:.1f}m in bank)")
            tips.append(SquadOptimizationTip(
                type="value",
                icon="💰",
                title="Money in the Bank",
                description=f"You have £{bank:.1f}m unused. Consider upgrading a player to maximize your budget.",
                priority="medium",
            ))
        elif bank < 0.5:
            strengths.append("Budget well utilized")

        # Free transfers
        if free_transfers >= 2:
            tips.append(SquadOptimizationTip(
                type="opportunity",
                icon="🔄",
                title=f"{free_transfers} Free Transfers Available",
                description="Use your free transfers wisely. Consider making moves to improve fixture runs or form.",
                priority="high",
            ))

        # Transfers impact
        if transfers:
            total_price_diff = sum(t.get("price_diff", 0) for t in transfers)
            if total_price_diff < 0:
                strengths.append(f"Transfers free up £{abs(total_price_diff):.1f}m")
            tips.append(SquadOptimizationTip(
                type="balance",
                icon="✅",
                title=f"{len(transfers)} Transfer{'s' if len(transfers) > 1 else ''} Planned",
                description="Review your transfers on the FPL site to confirm before the deadline.",
                priority="high",
            ))

        if not tips:
            tips.append(SquadOptimizationTip(
                type="balance",
                icon="👍",
                title="Squad Looks Balanced",
                description="Your squad structure is solid. Focus on captain choice and bench order.",
                priority="low",
            ))

        if not strengths:
            strengths = ["Good squad structure"]
        if not weaknesses:
            weaknesses = ["Minor improvements possible"]

        # Default chip strategy - no chips recommended
        chip_strategy = ChipStrategy(
            chip="none",
            chip_name="No Chip",
            should_use=False,
            reasoning="No need to use chips this week. Save them for a better opportunity like a double gameweek.",
            confidence=70,
        )

        return SquadAnalysisResponse(
            summary=f"Your squad has {len(squad)} players with £{bank:.1f}m in the bank. {len(transfers)} transfer{'s' if len(transfers) != 1 else ''} planned.",
            score=70 + len(strengths) * 5 - len(weaknesses) * 3,
            strengths=strengths,
            weaknesses=weaknesses,
            optimization_tips=tips,
            chip_strategy=chip_strategy,
            ai_model="rule-based-fallback",
        )

    async def analyze_gw_performance(
        self,
        squad: list[dict],
        gw_points: int,
        gw_rank: int | None,
        gw_average: int | None,
        captain_id: int,
        captain_name: str,
        captain_points: int,
        bench_points: int,
    ) -> dict:
        """Use AI to analyze gameweek performance and generate insights."""

        if not self.client:
            return self._fallback_gw_analysis(
                gw_points, gw_average, captain_name, captain_points, bench_points, squad
            )

        # Check cache - key by squad IDs and GW points (uniquely identifies this analysis)
        squad_ids = sorted([p.get("id", 0) for p in squad])
        cache_key_data = {
            "squad": squad_ids,
            "gw_points": gw_points,
            "captain_id": captain_id,
        }
        cached = self._cache.get("gw_performance", **cache_key_data)
        if cached is not None:
            return cached

        # Build squad performance context
        starting_xi = [p for p in squad if not p.get("is_bench")]
        bench = [p for p in squad if p.get("is_bench")]

        # Get top and bottom performers
        starting_sorted = sorted(starting_xi, key=lambda x: x.get("gw_points", 0), reverse=True)
        top_performers = starting_sorted[:3]
        bottom_performers = starting_sorted[-3:] if len(starting_sorted) >= 3 else starting_sorted

        prompt = f"""Analyse this FPL manager's gameweek performance and provide personalised insights.

IMPORTANT: Always use British English spelling (e.g., analyse, personalised, optimise, favourite, colour, defence, etc.).

GAMEWEEK RESULTS:
- Total Points: {gw_points}
- GW Average: {gw_average or 'Unknown'}
- GW Rank: {gw_rank or 'Unknown'}
- Points vs Average: {'+' if gw_points >= (gw_average or 0) else ''}{gw_points - (gw_average or 0)}

CAPTAIN:
- {captain_name} (C): {captain_points} points (doubled)

BENCH:
- Total bench points: {bench_points}
- Bench players: {', '.join(f"{p.get('name')} ({p.get('gw_points', 0)}pts)" for p in bench[:4])}

TOP PERFORMERS:
{chr(10).join(f"- {p.get('name')} ({p.get('team')}): {p.get('gw_points', 0)} pts" for p in top_performers)}

LOWEST PERFORMERS IN STARTING XI:
{chr(10).join(f"- {p.get('name')} ({p.get('team')}): {p.get('gw_points', 0)} pts" for p in bottom_performers)}

FULL STARTING XI:
{chr(10).join(f"- {p.get('name')} ({p.get('position')}, {p.get('team')}): {p.get('gw_points', 0)} pts" for p in starting_xi)}

Provide a JSON response with:
{{
    "what_went_well": [
        "Insight about good decisions this week (2-4 items, be specific with player names and numbers)"
    ],
    "areas_to_address": [
        "Insight about what could improve (2-4 items, be specific and actionable)"
    ],
    "strengths": [
        "Current squad strengths (2-3 items, e.g., strong midfield assets, good upcoming fixtures, value picks)"
    ],
    "weaknesses": [
        "Current squad weaknesses (2-3 items, e.g., no premium defense, fixture congestion, injury-prone players)"
    ],
    "squad_score": {{
        "overall": 75,
        "attack": 80,
        "midfield": 70,
        "defense": 65,
        "bench": 60
    }},
    "summary": "One sentence overall assessment"
}}

GUIDELINES:
- Be specific: mention player names, points, and concrete numbers
- Be actionable: give advice they can act on
- Be balanced: even in bad weeks find something positive, even in good weeks find improvements
- Consider: captain choice, bench vs starting XI, player form, fixture difficulty
- Keep each insight to 1-2 sentences max
- Squad scores should be 0-100, reflecting quality/value/potential of each area
- Strengths focus on what makes this squad competitive going forward
- Weaknesses focus on areas needing improvement or transfer attention"""

        try:
            message = self.client.messages.create(
                model="claude-3-5-haiku-20241022",  # Haiku is 5x faster than Sonnet
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return self._fallback_gw_analysis(
                    gw_points, gw_average, captain_name, captain_points, bench_points, squad
                )

            data = json.loads(json_match.group())
            result = {
                "what_went_well": data.get("what_went_well", []),
                "areas_to_address": data.get("areas_to_address", []),
                "strengths": data.get("strengths", []),
                "weaknesses": data.get("weaknesses", []),
                "squad_score": data.get("squad_score", {"overall": 70, "attack": 70, "midfield": 70, "defense": 70, "bench": 60}),
                "summary": data.get("summary", ""),
                "ai_model": "claude-3.5-haiku",
            }
            # Cache the successful response
            self._cache.set("gw_performance", result, **cache_key_data)
            logger.info("Claude gw_performance response cached")
            return result

        except Exception as e:
            logger.error(f"Claude GW analysis error: {e}")
            return self._fallback_gw_analysis(
                gw_points, gw_average, captain_name, captain_points, bench_points, squad
            )

    def _fallback_gw_analysis(
        self,
        gw_points: int,
        gw_average: int | None,
        captain_name: str,
        captain_points: int,
        bench_points: int,
        squad: list[dict],
    ) -> dict:
        """Fallback rule-based GW analysis when AI is unavailable."""
        what_went_well = []
        areas_to_address = []

        # Captain analysis
        if captain_points >= 12:
            what_went_well.append(f"{captain_name} (C) delivered {captain_points}pts - excellent captain choice!")
        elif captain_points >= 6:
            what_went_well.append(f"{captain_name} (C) returned a solid {captain_points}pts.")
        else:
            areas_to_address.append(f"{captain_name} (C) only managed {captain_points}pts - consider alternatives next week.")

        # Points vs average
        if gw_average:
            diff = gw_points - gw_average
            if diff >= 10:
                what_went_well.append(f"Significantly beat the average by {diff} points!")
            elif diff > 0:
                what_went_well.append(f"Beat the gameweek average by {diff} points.")
            elif diff < -10:
                areas_to_address.append(f"Underperformed the average by {abs(diff)} points.")

        # Bench points
        if bench_points <= 2:
            what_went_well.append(f"Only {bench_points}pts on bench - good squad management.")
        elif bench_points >= 10:
            areas_to_address.append(f"{bench_points}pts left on bench - review starting lineup choices.")

        # Find blankers
        starting_xi = [p for p in squad if not p.get("is_bench")]
        blankers = [p for p in starting_xi if p.get("gw_points", 0) <= 1]
        if len(blankers) >= 3:
            names = ", ".join(p.get("name", "Unknown") for p in blankers[:3])
            areas_to_address.append(f"Multiple blanks ({names}) - monitor their form.")
        elif len(blankers) == 0:
            what_went_well.append("No blanks in your starting XI!")

        # Summary
        if gw_points >= 60:
            summary = f"Excellent gameweek with {gw_points} points!"
        elif gw_points >= 50:
            summary = f"Solid performance with {gw_points} points."
        elif gw_points >= 40:
            summary = f"Average gameweek with {gw_points} points."
        else:
            summary = f"Tough gameweek with only {gw_points} points."

        return {
            "what_went_well": what_went_well if what_went_well else ["Squad performed as expected."],
            "areas_to_address": areas_to_address if areas_to_address else ["No major concerns this week."],
            "summary": summary,
            "ai_model": "rule-based-fallback",
        }


# Singleton instance
claude_service = ClaudeService()
