"""FPL News Parser Service.

Parses the FPL API `news` field to extract structured injury/suspension data.
This enables:
- Injury type classification
- Risk assessment (recurrence rates)
- New Smart Tags (InjuryProne, HighRecurrenceRisk, RecentlyReturned)
- RDF triple generation for InjuryEvent entities
"""

import re
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class InjuryType(Enum):
    """Classification of injury types from FPL news."""
    HAMSTRING = "hamstring"
    KNEE = "knee"
    ANKLE = "ankle"
    CALF = "calf"
    GROIN = "groin"
    MUSCLE = "muscle"
    BACK = "back"
    HIP = "hip"
    THIGH = "thigh"
    FOOT = "foot"
    SHOULDER = "shoulder"
    HEAD = "head"
    ILLNESS = "illness"
    KNOCK = "knock"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Injury/absence severity classification."""
    FIT = "fit"
    MINOR = "minor"        # 75%+ chance
    DOUBTFUL = "doubtful"  # 25-74% chance
    MAJOR = "major"        # 1-24% chance
    OUT = "out"            # 0% / "Out" / "Ruled out"
    SUSPENDED = "suspended"


@dataclass
class ParsedNews:
    """Structured representation of parsed FPL news."""
    injury_type: Optional[InjuryType]
    severity: Severity
    chance_of_playing: Optional[int]
    expected_return: Optional[str]
    expected_return_gameweek: Optional[int]
    is_suspension: bool
    suspension_matches: Optional[int]
    is_illness: bool
    raw_text: str
    recurrence_risk: Optional[str]  # "high", "medium", "low"
    risk_reason: Optional[str]


class FPLNewsParser:
    """Parser for FPL API news field.
    
    Extracts structured data from semi-structured news text like:
    - "Hamstring injury - 75% chance of playing"
    - "Knock - Expected to be fit"
    - "Suspended for one match"
    """
    
    # Mapping of keywords to injury types
    INJURY_KEYWORDS: Dict[str, InjuryType] = {
        "hamstring": InjuryType.HAMSTRING,
        "knee": InjuryType.KNEE,
        "ankle": InjuryType.ANKLE,
        "calf": InjuryType.CALF,
        "groin": InjuryType.GROIN,
        "muscle": InjuryType.MUSCLE,
        "muscular": InjuryType.MUSCLE,
        "back": InjuryType.BACK,
        "hip": InjuryType.HIP,
        "thigh": InjuryType.THIGH,
        "quad": InjuryType.THIGH,
        "quadricep": InjuryType.THIGH,
        "foot": InjuryType.FOOT,
        "toe": InjuryType.FOOT,
        "metatarsal": InjuryType.FOOT,
        "shoulder": InjuryType.SHOULDER,
        "head": InjuryType.HEAD,
        "concussion": InjuryType.HEAD,
        "illness": InjuryType.ILLNESS,
        "ill": InjuryType.ILLNESS,
        "sick": InjuryType.ILLNESS,
        "virus": InjuryType.ILLNESS,
        "flu": InjuryType.ILLNESS,
        "covid": InjuryType.ILLNESS,
        "knock": InjuryType.KNOCK,
        "bruise": InjuryType.KNOCK,
        "minor": InjuryType.KNOCK,
    }
    
    # Medical data: injuries with high recurrence rates
    # Based on sports medicine research
    HIGH_RECURRENCE_INJURIES: Dict[InjuryType, Dict[str, Any]] = {
        InjuryType.HAMSTRING: {
            "recurrence_rate": "30%",
            "typical_recovery": "2-6 weeks",
            "risk_window": "2 months after return",
            "warning": "High risk of reinjury within 2 months of return. Hamstring strains are the most common recurrent injury in football.",
        },
        InjuryType.CALF: {
            "recurrence_rate": "25%",
            "typical_recovery": "2-4 weeks",
            "risk_window": "6 weeks after return",
            "warning": "Often returns as tightness. Monitor minutes carefully, especially in congested fixtures.",
        },
        InjuryType.GROIN: {
            "recurrence_rate": "20%",
            "typical_recovery": "3-8 weeks",
            "risk_window": "3 months after return",
            "warning": "Can become chronic if rushed back. Adductor injuries are notoriously difficult to fully heal.",
        },
        InjuryType.THIGH: {
            "recurrence_rate": "22%",
            "typical_recovery": "2-5 weeks",
            "risk_window": "6 weeks after return",
            "warning": "Quadricep injuries often occur from overexertion. Watch for fixture congestion.",
        },
    }
    
    MEDIUM_RECURRENCE_INJURIES: Dict[InjuryType, Dict[str, Any]] = {
        InjuryType.ANKLE: {
            "recurrence_rate": "15%",
            "typical_recovery": "2-6 weeks",
            "warning": "Ankle sprains can lead to chronic instability if not fully healed.",
        },
        InjuryType.KNEE: {
            "recurrence_rate": "12%",
            "typical_recovery": "Varies widely",
            "warning": "Knee injuries vary greatly. Minor = 2 weeks, ACL = 6-9 months.",
        },
    }
    
    def parse(self, news: str, status: str = "a", chance_api: Optional[int] = None) -> ParsedNews:
        """Parse FPL news text into structured data.
        
        Args:
            news: The raw news text from FPL API
            status: Player status code (a=available, d=doubtful, i=injured, s=suspended, u=unavailable)
            chance_api: chance_of_playing_next_round from API (can override parsed value)
            
        Returns:
            ParsedNews dataclass with extracted information
        """
        # Handle empty/fit case
        if not news or news.strip() == "":
            return ParsedNews(
                injury_type=None,
                severity=Severity.FIT,
                chance_of_playing=100,
                expected_return=None,
                expected_return_gameweek=None,
                is_suspension=False,
                suspension_matches=None,
                is_illness=False,
                raw_text=news or "",
                recurrence_risk=None,
                risk_reason=None,
            )
        
        news_lower = news.lower()
        
        # Check for suspension
        is_suspension = "suspend" in news_lower or "red card" in news_lower or "ban" in news_lower
        suspension_matches = None
        if is_suspension:
            # Try to extract number of matches
            match = re.search(r'(\d+)\s*match', news_lower)
            if match:
                suspension_matches = int(match.group(1))
            else:
                # Look for word numbers
                if "one" in news_lower:
                    suspension_matches = 1
                elif "two" in news_lower:
                    suspension_matches = 2
                elif "three" in news_lower:
                    suspension_matches = 3
                else:
                    suspension_matches = 1  # Default assumption
        
        # Extract injury type
        injury_type = self._extract_injury_type(news_lower)
        is_illness = injury_type == InjuryType.ILLNESS
        
        # Extract chance percentage from text
        chance_match = re.search(r'(\d+)%', news)
        chance_text = int(chance_match.group(1)) if chance_match else None
        
        # Use API value if available, otherwise use parsed value
        chance = chance_api if chance_api is not None else chance_text
        
        # Determine severity
        severity = self._determine_severity(news_lower, status, chance, is_suspension)
        
        # If we determined OUT but have no chance, set to 0
        if severity == Severity.OUT and chance is None:
            chance = 0
        
        # Extract expected return date
        expected_return = self._extract_expected_return(news)
        
        # Calculate recurrence risk
        recurrence_risk, risk_reason = self._assess_recurrence_risk(injury_type)
        
        return ParsedNews(
            injury_type=injury_type if injury_type != InjuryType.UNKNOWN else None,
            severity=severity,
            chance_of_playing=chance,
            expected_return=expected_return,
            expected_return_gameweek=None,  # Would need current GW context
            is_suspension=is_suspension,
            suspension_matches=suspension_matches,
            is_illness=is_illness,
            raw_text=news,
            recurrence_risk=recurrence_risk,
            risk_reason=risk_reason,
        )
    
    def _extract_injury_type(self, news_lower: str) -> InjuryType:
        """Extract injury type from news text."""
        for keyword, itype in self.INJURY_KEYWORDS.items():
            if keyword in news_lower:
                return itype
        return InjuryType.UNKNOWN
    
    def _determine_severity(
        self, 
        news_lower: str, 
        status: str, 
        chance: Optional[int],
        is_suspension: bool
    ) -> Severity:
        """Determine injury severity from available signals."""
        
        if is_suspension:
            return Severity.SUSPENDED
        
        # Check for explicit "out" indicators
        out_phrases = ["ruled out", "out for", "sidelined", "not available", "will miss", "set to miss"]
        if any(phrase in news_lower for phrase in out_phrases):
            return Severity.OUT
        
        # Check for "out" at word boundary (not "doubt" etc)
        if re.search(r'\bout\b', news_lower):
            return Severity.OUT
        
        # Use chance percentage if available
        if chance is not None:
            if chance >= 75:
                return Severity.MINOR
            elif chance >= 50:
                return Severity.DOUBTFUL
            elif chance >= 25:
                return Severity.DOUBTFUL
            else:
                return Severity.MAJOR if chance > 0 else Severity.OUT
        
        # Fall back to status code
        status_map = {
            "a": Severity.FIT,
            "d": Severity.DOUBTFUL,
            "i": Severity.OUT,
            "s": Severity.SUSPENDED,
            "u": Severity.OUT,
        }
        return status_map.get(status, Severity.DOUBTFUL)
    
    def _extract_expected_return(self, news: str) -> Optional[str]:
        """Extract expected return date from news text."""
        
        # Pattern: "Expected back 22 Dec"
        match = re.search(r'[Ee]xpected (?:back|to return) (\d{1,2} \w+)', news)
        if match:
            return match.group(1)
        
        # Pattern: "back in X weeks"
        match = re.search(r'back in (\d+) weeks?', news.lower())
        if match:
            return f"{match.group(1)} weeks"
        
        # Pattern: "X weeks away"
        match = re.search(r'(\d+) weeks? away', news.lower())
        if match:
            return f"{match.group(1)} weeks"
        
        # Pattern: "return date: 22 Dec"
        match = re.search(r'return(?:ing)?(?: date)?[:\s]+(\d{1,2} \w+)', news, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def _assess_recurrence_risk(self, injury_type: Optional[InjuryType]) -> tuple[Optional[str], Optional[str]]:
        """Assess recurrence risk based on injury type.
        
        Returns:
            Tuple of (risk_level, risk_reason)
        """
        if injury_type is None or injury_type == InjuryType.UNKNOWN:
            return None, None
        
        if injury_type in self.HIGH_RECURRENCE_INJURIES:
            info = self.HIGH_RECURRENCE_INJURIES[injury_type]
            return "high", info["warning"]
        
        if injury_type in self.MEDIUM_RECURRENCE_INJURIES:
            info = self.MEDIUM_RECURRENCE_INJURIES[injury_type]
            return "medium", info["warning"]
        
        if injury_type == InjuryType.KNOCK:
            return "low", "Minor knock - typically resolves quickly with minimal risk."
        
        if injury_type == InjuryType.ILLNESS:
            return "low", "Illness - full recovery expected once symptoms clear."
        
        return "medium", "Monitor recovery progress."
    
    def get_injury_info(self, injury_type: InjuryType) -> Optional[Dict[str, Any]]:
        """Get detailed medical information for an injury type."""
        if injury_type in self.HIGH_RECURRENCE_INJURIES:
            return {**self.HIGH_RECURRENCE_INJURIES[injury_type], "risk_level": "high"}
        if injury_type in self.MEDIUM_RECURRENCE_INJURIES:
            return {**self.MEDIUM_RECURRENCE_INJURIES[injury_type], "risk_level": "medium"}
        return None


# Singleton instance
_parser_instance: Optional[FPLNewsParser] = None

def get_news_parser() -> FPLNewsParser:
    """Get singleton news parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = FPLNewsParser()
    return _parser_instance

