# backend/services/self_healing_service.py
"""
Self-Healing Service for SmartPlayFPL

Uses Claude AI to automatically detect, diagnose, and fix issues.

Key Features:
- Automatic error detection and monitoring
- Claude AI-powered diagnosis
- Safe automated healing actions
- Comprehensive logging and audit trail
"""

import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

import anthropic
from config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES AND ENUMS
# =============================================================================

class ErrorSeverity(str, Enum):
    LOW = "low"           # Minor issue, can wait
    MEDIUM = "medium"     # Should be addressed soon
    HIGH = "high"         # Needs immediate attention
    CRITICAL = "critical" # System is down


class HealingActionType(str, Enum):
    # Safe actions (auto-execute)
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"
    CACHE_CLEAR = "cache_clear"
    KG_RELOAD = "kg_reload"
    ML_PREDICTOR_RELOAD = "ml_predictor_reload"
    FPL_SERVICE_REFRESH = "fpl_service_refresh"
    DB_CONNECTION_REFRESH = "db_connection_refresh"
    FALLBACK_TO_CACHE = "fallback_to_cache"
    RATE_LIMIT_BACKOFF = "rate_limit_backoff"

    # Requires human approval
    SERVICE_RESTART = "service_restart"
    CONFIG_CHANGE = "config_change"
    DATA_CORRECTION = "data_correction"


@dataclass
class DetectedError:
    """Represents a detected error in the system."""
    error_id: str
    timestamp: datetime
    error_type: str
    error_message: str
    stack_trace: Optional[str]
    component: str  # e.g., "fpl_api", "knowledge_graph", "ml_predictor"
    severity: ErrorSeverity
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_action: Optional[str] = None


@dataclass
class HealingAction:
    """Represents a healing action taken by the system."""
    action_id: str
    timestamp: datetime
    action_type: HealingActionType
    error_id: str
    description: str
    auto_executed: bool
    success: bool
    result_message: str
    ai_reasoning: Optional[str] = None


@dataclass
class DiagnosisResult:
    """Result of Claude AI diagnosis."""
    root_cause: str
    recommended_actions: List[Dict[str, Any]]
    severity: ErrorSeverity
    explanation: str
    confidence: float  # 0.0 to 1.0


# =============================================================================
# SELF-HEALING SERVICE
# =============================================================================

class SelfHealingService:
    """
    AI-powered self-healing service for SmartPlayFPL.

    Monitors for errors, diagnoses root causes using Claude AI,
    and automatically applies safe fixes.
    """

    # Safe actions that can be auto-executed without human approval
    SAFE_ACTIONS = {
        HealingActionType.CIRCUIT_BREAKER_RESET,
        HealingActionType.CACHE_CLEAR,
        HealingActionType.KG_RELOAD,
        HealingActionType.ML_PREDICTOR_RELOAD,
        HealingActionType.FPL_SERVICE_REFRESH,
        HealingActionType.DB_CONNECTION_REFRESH,
        HealingActionType.FALLBACK_TO_CACHE,
        HealingActionType.RATE_LIMIT_BACKOFF,
    }

    # Maximum errors to keep in memory
    MAX_ERROR_HISTORY = 100

    # Cooldown between same action type (seconds)
    ACTION_COOLDOWN = 300  # 5 minutes

    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None
        self._error_history: deque = deque(maxlen=self.MAX_ERROR_HISTORY)
        self._action_history: deque = deque(maxlen=self.MAX_ERROR_HISTORY)
        self._action_cooldowns: Dict[str, datetime] = {}
        self._fpl_service = None
        self._kg_service = None
        self._ml_predictor = None
        self._error_counter = 0
        self._action_counter = 0

    def set_services(self, fpl_service=None, kg_service=None, ml_predictor=None):
        """Set service references for healing actions."""
        self._fpl_service = fpl_service
        self._kg_service = kg_service
        self._ml_predictor = ml_predictor

    def _get_client(self) -> anthropic.Anthropic:
        """Get or create Anthropic client for self-healing."""
        if self._client is None:
            # Use dedicated self-healing API key, fallback to main key
            api_key = settings.SELF_HEALING_API_KEY or settings.ANTHROPIC_API_KEY
            if not api_key:
                raise ValueError("No API key configured for self-healing (SELF_HEALING_API_KEY or ANTHROPIC_API_KEY)")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def _generate_error_id(self) -> str:
        """Generate unique error ID."""
        self._error_counter += 1
        return f"ERR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._error_counter:04d}"

    def _generate_action_id(self) -> str:
        """Generate unique action ID."""
        self._action_counter += 1
        return f"ACT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._action_counter:04d}"

    # =========================================================================
    # ERROR DETECTION
    # =========================================================================

    def detect_error(
        self,
        error_type: str,
        error_message: str,
        component: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> DetectedError:
        """
        Detect and log an error in the system.

        This should be called from exception handlers throughout the codebase.
        """
        # Auto-determine severity if not provided
        if severity is None:
            severity = self._classify_severity(error_type, error_message, component)

        error = DetectedError(
            error_id=self._generate_error_id(),
            timestamp=datetime.utcnow(),
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            component=component,
            severity=severity,
            context=context or {},
        )

        self._error_history.append(error)

        logger.warning(
            f"[SelfHealing] Error detected: {error.error_id} - "
            f"{error.component}/{error.error_type}: {error.error_message[:100]}"
        )

        return error

    def _classify_severity(
        self,
        error_type: str,
        error_message: str,
        component: str
    ) -> ErrorSeverity:
        """Automatically classify error severity."""
        error_lower = error_message.lower()
        error_type_lower = error_type.lower()

        # Critical patterns
        critical_patterns = [
            "database connection failed",
            "out of memory",
            "disk full",
            "authentication failed",
            "ssl certificate",
        ]
        if any(p in error_lower for p in critical_patterns):
            return ErrorSeverity.CRITICAL

        # High severity patterns
        high_patterns = [
            "timeout",
            "connection refused",
            "rate limit exceeded",
            "500",
            "internal server error",
        ]
        if any(p in error_lower for p in high_patterns):
            return ErrorSeverity.HIGH

        # Medium severity patterns
        medium_patterns = [
            "not found",
            "404",
            "validation",
            "parse error",
            "invalid",
        ]
        if any(p in error_lower for p in medium_patterns):
            return ErrorSeverity.MEDIUM

        # Default to LOW
        return ErrorSeverity.LOW

    # =========================================================================
    # CLAUDE AI DIAGNOSIS
    # =========================================================================

    async def diagnose_error(self, error: DetectedError) -> DiagnosisResult:
        """
        Use Claude AI to diagnose an error and recommend healing actions.
        """
        client = self._get_client()

        # Build context about the system state
        system_context = self._build_system_context()

        prompt = f"""You are an AI DevOps engineer for SmartPlayFPL, a Fantasy Premier League analytics platform.

An error has been detected that needs diagnosis and healing.

## Error Details
- **Error ID**: {error.error_id}
- **Component**: {error.component}
- **Type**: {error.error_type}
- **Message**: {error.error_message}
- **Severity**: {error.severity.value}
- **Timestamp**: {error.timestamp.isoformat()}

## Stack Trace
```
{error.stack_trace or 'No stack trace available'}
```

## Additional Context
```json
{json.dumps(error.context, indent=2, default=str)}
```

## System Architecture
{system_context}

## Available Healing Actions (SAFE - can auto-execute)
1. circuit_breaker_reset - Reset a tripped circuit breaker
2. cache_clear - Clear cached data
3. kg_reload - Reload the Knowledge Graph
4. ml_predictor_reload - Reload ML prediction models
5. fpl_service_refresh - Refresh FPL API connection
6. db_connection_refresh - Refresh database connections
7. fallback_to_cache - Use cached data instead of live
8. rate_limit_backoff - Apply exponential backoff

## Your Task
Analyze this error and provide a diagnosis in the following JSON format:

```json
{{
    "root_cause": "Brief description of the root cause",
    "severity": "low|medium|high|critical",
    "confidence": 0.85,
    "explanation": "Detailed explanation of what went wrong and why",
    "recommended_actions": [
        {{
            "action_type": "one of the safe action types above",
            "priority": 1,
            "reason": "Why this action should help"
        }}
    ]
}}
```

Only recommend safe actions from the list above. If the issue requires human intervention, set confidence lower and explain what manual steps are needed in the explanation.
"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Parse JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())

            return DiagnosisResult(
                root_cause=result.get("root_cause", "Unknown"),
                recommended_actions=result.get("recommended_actions", []),
                severity=ErrorSeverity(result.get("severity", error.severity.value)),
                explanation=result.get("explanation", "No explanation provided"),
                confidence=result.get("confidence", 0.5),
            )

        except Exception as e:
            logger.error(f"[SelfHealing] AI diagnosis failed: {e}")
            # Return fallback diagnosis
            return DiagnosisResult(
                root_cause="AI diagnosis failed",
                recommended_actions=[],
                severity=error.severity,
                explanation=f"Could not diagnose: {str(e)}",
                confidence=0.0,
            )

    def _build_system_context(self) -> str:
        """Build context about current system state."""
        context_parts = [
            "SmartPlayFPL Backend Components:",
            "- FastAPI backend on Railway",
            "- FPL API integration (external dependency)",
            "- RDF Knowledge Graph with SPARQL",
            "- ML Predictor with LightGBM/XGBoost ensemble",
            "- SQLite database for caching",
            "- Circuit breakers for resilience",
        ]

        # Add current error count
        recent_errors = [e for e in self._error_history
                       if e.timestamp > datetime.utcnow() - timedelta(hours=1)]
        context_parts.append(f"\nRecent errors (1h): {len(recent_errors)}")

        return "\n".join(context_parts)

    # =========================================================================
    # HEALING ACTIONS
    # =========================================================================

    async def execute_healing(
        self,
        error: DetectedError,
        diagnosis: DiagnosisResult,
        auto_execute: bool = True
    ) -> List[HealingAction]:
        """
        Execute recommended healing actions.

        Args:
            error: The detected error
            diagnosis: AI diagnosis result
            auto_execute: If True, execute safe actions automatically

        Returns:
            List of healing actions taken
        """
        actions_taken = []

        for action_rec in diagnosis.recommended_actions:
            action_type_str = action_rec.get("action_type", "")

            try:
                action_type = HealingActionType(action_type_str)
            except ValueError:
                logger.warning(f"[SelfHealing] Unknown action type: {action_type_str}")
                continue

            # Check if action is safe for auto-execution
            is_safe = action_type in self.SAFE_ACTIONS

            # Check cooldown
            if self._is_on_cooldown(action_type):
                logger.info(f"[SelfHealing] Action {action_type.value} on cooldown, skipping")
                continue

            # Create action record
            action = HealingAction(
                action_id=self._generate_action_id(),
                timestamp=datetime.utcnow(),
                action_type=action_type,
                error_id=error.error_id,
                description=action_rec.get("reason", ""),
                auto_executed=auto_execute and is_safe,
                success=False,
                result_message="",
                ai_reasoning=diagnosis.explanation,
            )

            # Execute if safe and auto-execute enabled
            if auto_execute and is_safe:
                try:
                    result = await self._execute_action(action_type, error.context)
                    action.success = result["success"]
                    action.result_message = result["message"]

                    if action.success:
                        error.resolved = True
                        error.resolution_action = action_type.value

                    # Set cooldown
                    self._set_cooldown(action_type)

                except Exception as e:
                    action.result_message = f"Execution failed: {str(e)}"
                    logger.error(f"[SelfHealing] Action execution failed: {e}")
            else:
                action.result_message = "Requires human approval" if not is_safe else "Auto-execute disabled"

            self._action_history.append(action)
            actions_taken.append(action)

            logger.info(
                f"[SelfHealing] Action {action.action_id}: {action_type.value} - "
                f"Success={action.success}, Auto={action.auto_executed}"
            )

        return actions_taken

    async def _execute_action(
        self,
        action_type: HealingActionType,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a specific healing action."""

        if action_type == HealingActionType.CIRCUIT_BREAKER_RESET:
            return await self._action_reset_circuit_breakers()

        elif action_type == HealingActionType.CACHE_CLEAR:
            return await self._action_clear_cache()

        elif action_type == HealingActionType.KG_RELOAD:
            return await self._action_reload_kg()

        elif action_type == HealingActionType.ML_PREDICTOR_RELOAD:
            return await self._action_reload_ml_predictor()

        elif action_type == HealingActionType.FPL_SERVICE_REFRESH:
            return await self._action_refresh_fpl_service()

        elif action_type == HealingActionType.DB_CONNECTION_REFRESH:
            return await self._action_refresh_db_connections()

        elif action_type == HealingActionType.FALLBACK_TO_CACHE:
            return await self._action_enable_fallback()

        elif action_type == HealingActionType.RATE_LIMIT_BACKOFF:
            return await self._action_rate_limit_backoff()

        else:
            return {"success": False, "message": f"Unknown action: {action_type}"}

    # =========================================================================
    # SPECIFIC HEALING ACTIONS
    # =========================================================================

    async def _action_reset_circuit_breakers(self) -> Dict[str, Any]:
        """Reset all circuit breakers."""
        try:
            if self._fpl_service and hasattr(self._fpl_service, '_circuit_breakers'):
                for name, cb in self._fpl_service._circuit_breakers.items():
                    cb.reset()
                return {"success": True, "message": "All circuit breakers reset"}
            return {"success": True, "message": "No circuit breakers found"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_clear_cache(self) -> Dict[str, Any]:
        """Clear cached data."""
        try:
            if self._fpl_service:
                if hasattr(self._fpl_service, '_cache'):
                    self._fpl_service._cache.clear()
                if hasattr(self._fpl_service, 'clear_cache'):
                    self._fpl_service.clear_cache()
            return {"success": True, "message": "Cache cleared"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_reload_kg(self) -> Dict[str, Any]:
        """Reload Knowledge Graph."""
        try:
            if self._kg_service:
                # Re-initialize KG
                if hasattr(self._kg_service, 'initialize'):
                    await self._kg_service.initialize()
                return {"success": True, "message": "Knowledge Graph reloaded"}
            return {"success": False, "message": "KG service not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_reload_ml_predictor(self) -> Dict[str, Any]:
        """Reload ML predictor models."""
        try:
            if self._ml_predictor:
                if hasattr(self._ml_predictor, 'reload_models'):
                    self._ml_predictor.reload_models()
                elif hasattr(self._ml_predictor, 'initialize'):
                    await self._ml_predictor.initialize()
                return {"success": True, "message": "ML predictor reloaded"}
            return {"success": False, "message": "ML predictor not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_refresh_fpl_service(self) -> Dict[str, Any]:
        """Refresh FPL service connections."""
        try:
            if self._fpl_service:
                if hasattr(self._fpl_service, 'refresh'):
                    self._fpl_service.refresh()
                # Clear any cached data
                if hasattr(self._fpl_service, '_cache'):
                    self._fpl_service._cache.clear()
                return {"success": True, "message": "FPL service refreshed"}
            return {"success": False, "message": "FPL service not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_refresh_db_connections(self) -> Dict[str, Any]:
        """Refresh database connections."""
        try:
            from database import engine
            engine.dispose()
            return {"success": True, "message": "Database connections refreshed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_enable_fallback(self) -> Dict[str, Any]:
        """Enable fallback to cached data."""
        try:
            # Set a flag to use cached data
            if self._fpl_service:
                self._fpl_service._use_fallback = True
            return {"success": True, "message": "Fallback mode enabled"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _action_rate_limit_backoff(self) -> Dict[str, Any]:
        """Apply rate limit backoff."""
        try:
            if self._fpl_service:
                # Increase delay between requests
                current_delay = getattr(self._fpl_service, '_request_delay', 1.0)
                self._fpl_service._request_delay = min(current_delay * 2, 30.0)
                return {"success": True, "message": f"Request delay increased to {self._fpl_service._request_delay}s"}
            return {"success": True, "message": "Backoff applied"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # =========================================================================
    # COOLDOWN MANAGEMENT
    # =========================================================================

    def _is_on_cooldown(self, action_type: HealingActionType) -> bool:
        """Check if an action type is on cooldown."""
        key = action_type.value
        if key not in self._action_cooldowns:
            return False
        return datetime.utcnow() < self._action_cooldowns[key]

    def _set_cooldown(self, action_type: HealingActionType):
        """Set cooldown for an action type."""
        self._action_cooldowns[action_type.value] = (
            datetime.utcnow() + timedelta(seconds=self.ACTION_COOLDOWN)
        )

    # =========================================================================
    # MAIN HEALING FLOW
    # =========================================================================

    async def heal(
        self,
        error_type: str,
        error_message: str,
        component: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict] = None,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """
        Main entry point for self-healing.

        Detects error, diagnoses with AI, and executes healing actions.

        Args:
            error_type: Type/class of error
            error_message: Error message
            component: Which component had the error
            stack_trace: Optional stack trace
            context: Optional additional context
            auto_execute: Whether to auto-execute safe actions

        Returns:
            Healing result with diagnosis and actions taken
        """
        # Step 1: Detect and log the error
        error = self.detect_error(
            error_type=error_type,
            error_message=error_message,
            component=component,
            stack_trace=stack_trace,
            context=context,
        )

        # Step 2: Get AI diagnosis
        diagnosis = await self.diagnose_error(error)

        # Step 3: Execute healing actions
        actions = await self.execute_healing(error, diagnosis, auto_execute)

        return {
            "error_id": error.error_id,
            "severity": error.severity.value,
            "resolved": error.resolved,
            "diagnosis": {
                "root_cause": diagnosis.root_cause,
                "explanation": diagnosis.explanation,
                "confidence": diagnosis.confidence,
            },
            "actions_taken": [
                {
                    "action_id": a.action_id,
                    "action_type": a.action_type.value,
                    "success": a.success,
                    "auto_executed": a.auto_executed,
                    "result": a.result_message,
                }
                for a in actions
            ],
        }

    # =========================================================================
    # HEALTH CHECK
    # =========================================================================

    async def run_health_check(self) -> Dict[str, Any]:
        """
        Run a comprehensive health check and auto-heal any issues found.
        """
        issues_found = []
        actions_taken = []

        # Check 1: FPL API connectivity
        try:
            if self._fpl_service:
                # Try a simple API call
                gw = self._fpl_service.get_current_gameweek()
                if not gw:
                    issues_found.append("FPL API not responding")
        except Exception as e:
            issues_found.append(f"FPL API error: {str(e)}")
            result = await self.heal(
                error_type="ConnectionError",
                error_message=str(e),
                component="fpl_api",
            )
            actions_taken.extend(result.get("actions_taken", []))

        # Check 2: Knowledge Graph
        try:
            if self._kg_service:
                stats = self._kg_service.get_stats() if hasattr(self._kg_service, 'get_stats') else None
                if not stats or stats.get("total_triples", 0) == 0:
                    issues_found.append("Knowledge Graph empty or unavailable")
        except Exception as e:
            issues_found.append(f"KG error: {str(e)}")
            result = await self.heal(
                error_type="KGError",
                error_message=str(e),
                component="knowledge_graph",
            )
            actions_taken.extend(result.get("actions_taken", []))

        # Check 3: ML Predictor
        try:
            if self._ml_predictor:
                status = self._ml_predictor.get_status() if hasattr(self._ml_predictor, 'get_status') else None
                if not status or not status.get("initialized"):
                    issues_found.append("ML Predictor not initialized")
        except Exception as e:
            issues_found.append(f"ML error: {str(e)}")
            result = await self.heal(
                error_type="MLError",
                error_message=str(e),
                component="ml_predictor",
            )
            actions_taken.extend(result.get("actions_taken", []))

        # Check 4: Database
        try:
            from database import SessionLocal
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
        except Exception as e:
            issues_found.append(f"Database error: {str(e)}")
            result = await self.heal(
                error_type="DatabaseError",
                error_message=str(e),
                component="database",
            )
            actions_taken.extend(result.get("actions_taken", []))

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "healthy": len(issues_found) == 0,
            "issues_found": issues_found,
            "actions_taken": actions_taken,
            "recent_errors": len([e for e in self._error_history
                                 if e.timestamp > datetime.utcnow() - timedelta(hours=1)]),
            "recent_healings": len([a for a in self._action_history
                                   if a.timestamp > datetime.utcnow() - timedelta(hours=1)]),
        }

    # =========================================================================
    # HISTORY AND REPORTING
    # =========================================================================

    def get_error_history(self, limit: int = 20) -> List[Dict]:
        """Get recent error history."""
        errors = list(self._error_history)[-limit:]
        return [
            {
                "error_id": e.error_id,
                "timestamp": e.timestamp.isoformat(),
                "component": e.component,
                "error_type": e.error_type,
                "message": e.error_message[:200],
                "severity": e.severity.value,
                "resolved": e.resolved,
                "resolution_action": e.resolution_action,
            }
            for e in reversed(errors)
        ]

    def get_action_history(self, limit: int = 20) -> List[Dict]:
        """Get recent healing action history."""
        actions = list(self._action_history)[-limit:]
        return [
            {
                "action_id": a.action_id,
                "timestamp": a.timestamp.isoformat(),
                "action_type": a.action_type.value,
                "error_id": a.error_id,
                "success": a.success,
                "auto_executed": a.auto_executed,
                "result": a.result_message,
            }
            for a in reversed(actions)
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get self-healing statistics."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        errors_hour = [e for e in self._error_history if e.timestamp > hour_ago]
        errors_day = [e for e in self._error_history if e.timestamp > day_ago]
        actions_hour = [a for a in self._action_history if a.timestamp > hour_ago]
        actions_day = [a for a in self._action_history if a.timestamp > day_ago]

        return {
            "errors_last_hour": len(errors_hour),
            "errors_last_day": len(errors_day),
            "errors_resolved_hour": len([e for e in errors_hour if e.resolved]),
            "actions_last_hour": len(actions_hour),
            "actions_last_day": len(actions_day),
            "actions_successful_hour": len([a for a in actions_hour if a.success]),
            "auto_heal_rate": (
                len([a for a in actions_day if a.success and a.auto_executed]) /
                max(len(actions_day), 1) * 100
            ),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_self_healing_service: Optional[SelfHealingService] = None


def get_self_healing_service() -> SelfHealingService:
    """Get or create the singleton SelfHealingService instance."""
    global _self_healing_service
    if _self_healing_service is None:
        _self_healing_service = SelfHealingService()
    return _self_healing_service
