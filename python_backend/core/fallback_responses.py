"""
Fallback Responses - Sensible default responses when agents fail or are unavailable

Provides graceful degradation strategies for different failure modes:
- Agent timeout: Return canned response with recovery suggestions
- Service unavailable: Return helpful fallback with retry instructions
- Database error: Return cached response if available
- Invalid input: Return specific error guidance
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class FallbackResponse:
    """Generator for sensible fallback responses"""
    
    @staticmethod
    def timeout_fallback(
        _message_context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return fallback response when chat processing times out (>30s)
        
        Provides:
        - Acknowledgement of user message
        - Explanation of timeout
        - Suggestions for recovery
        - Session ID for support
        """
        return {
            "message": (
                "I understand your question, but the analysis is taking longer than expected. "
                "This might mean we're processing a large dataset or the system is under load. "
                "Your request has been queued and you can check back in a moment, "
                "or contact support with session ID: {}".format(session_id or "unknown")
            ),
            "agent_responses": [],
            "suggested_actions": [
                "Try a simpler question with fewer parameters",
                "Check workflow status to understand current progress",
                "Contact support if issue persists",
                "Try again in 30 seconds"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "agent_timeout",
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def unavailable_fallback(
        service_name: str = "AI Agent",
        _message_context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return fallback response when service is temporarily unavailable
        
        Provides:
        - Clear message about service status
        - Expected recovery time
        - Alternative actions user can take
        """
        return {
            "message": (
                f"The {service_name} is temporarily unavailable or unreachable. "
                "This is usually temporary. The system will try to recover automatically. "
                "In the meantime, you can continue exploring the UI or check workflow status."
            ),
            "agent_responses": [],
            "suggested_actions": [
                "Check workflow status independently",
                "Review previous quality reports",
                "Try again in 1-2 minutes",
                "Contact support if issue persists"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "service_unavailable",
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def invalid_input_fallback(
        error_message: str,
        _message_context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return helpful error message for invalid input
        
        Provides:
        - Clear error explanation
        - Examples of valid input
        - Next steps
        """
        return {
            "message": (
                f"I couldn't process your request: {error_message}. "
                "Please check that your input is properly formatted and try again. "
                "You can ask me about workflow status, data quality, or validation rules."
            ),
            "agent_responses": [],
            "suggested_actions": [
                "Check your input format",
                "Try a simpler question",
                "Ask about workflow status",
                "Ask about data quality rules"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "invalid_input",
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def rate_limited_fallback(
        retry_after_seconds: int = 30,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return fallback when rate limited
        
        Provides:
        - Clear rate limit message
        - When to retry
        - Alternative actions
        """
        return {
            "message": (
                f"The system is currently handling many requests. "
                f"Please wait about {retry_after_seconds} seconds before trying again. "
                "In the meantime, you can review data quality reports or explore workflow status."
            ),
            "agent_responses": [],
            "suggested_actions": [
                f"Try again in {retry_after_seconds} seconds",
                "Check workflow status",
                "Review quality reports",
                "Explore validation rules"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "rate_limited",
            "_retry_after": retry_after_seconds,
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def database_error_fallback(
        _message_context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return fallback when database operations fail
        
        Provides:
        - Non-technical explanation
        - UI-accessible actions
        - Recovery suggestion
        """
        return {
            "message": (
                "A database operation failed temporarily. "
                "The system is attempting to recover. "
                "You can continue using the UI or check workflow status independently."
            ),
            "agent_responses": [],
            "suggested_actions": [
                "Check workflow status",
                "Review recent reports",
                "Try again in a moment",
                "Contact support if persists"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "database_error",
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def generic_error_fallback(
        error_message: str = "An unexpected error occurred",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generic fallback for any unclassified error
        
        Provides:
        - Acknowledgement
        - Session info for support
        - Next steps
        """
        return {
            "message": (
                f"{error_message} "
                "The system has logged this issue and will attempt recovery. "
                f"Your session ID is {session_id or 'unknown'} - include this if contacting support."
            ),
            "agent_responses": [],
            "suggested_actions": [
                "Try again",
                "Check workflow status",
                "Refresh the page",
                "Contact support with session ID"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "generic_error",
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def workflow_context_fallback(
        workflow_id: str,
        message_context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fallback response that includes limited workflow context
        
        Used when agent fails but we can still provide useful info from DB
        """
        return {
            "message": (
                f"I couldn't fully analyze your question, but I can see that "
                f"workflow {workflow_id} is currently active. "
                "You can review the workflow status in the dashboard or try asking about "
                "the current data quality metrics."
            ),
            "agent_responses": [],
            "suggested_actions": [
                "Check workflow status",
                "Review quality metrics",
                "Ask about current stage",
                "Try a different question"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "workflow_id": workflow_id,
            "_fallback": True,
            "_fallback_reason": "agent_failed_with_context",
            "_recovered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def circuit_breaker_fallback(
        service_name: str = "AI Service",
        estimated_recovery_minutes: int = 1,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fallback when circuit breaker is open (service in trouble)
        
        Provides:
        - Clear explanation
        - Estimated recovery time
        - What user can do
        """
        return {
            "message": (
                f"The {service_name} is experiencing difficulties and has been temporarily disabled "
                f"to prevent further issues. We estimate it will recover in about {estimated_recovery_minutes} minute(s). "
                "You can continue using the dashboard to explore data or check workflow status."
            ),
            "agent_responses": [],
            "suggested_actions": [
                f"Check back in {estimated_recovery_minutes} minute(s)",
                "Explore data in dashboard",
                "Check workflow status",
                "Review recent reports"
            ],
            "requires_followup": True,
            "session_id": session_id,
            "_fallback": True,
            "_fallback_reason": "circuit_breaker_open",
            "_estimated_recovery_minutes": estimated_recovery_minutes,
            "_recovered_at": datetime.utcnow().isoformat()
        }


def get_fallback_by_error_type(
    error_type: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Get appropriate fallback response based on error type
    
    Args:
        error_type: Type of error (timeout, unavailable, invalid_input, etc.)
        **kwargs: Additional context (error_message, service_name, session_id, etc.)
        
    Returns:
        Fallback response dictionary
    """
    fallback_map: Dict[str, Callable[..., Dict[str, Any]]] = {
        "agent_timeout": FallbackResponse.timeout_fallback,
        "service_unavailable": FallbackResponse.unavailable_fallback,
        "invalid_input": FallbackResponse.invalid_input_fallback,
        "rate_limited": FallbackResponse.rate_limited_fallback,
        "database_error": FallbackResponse.database_error_fallback,
        "circuit_breaker_open": FallbackResponse.circuit_breaker_fallback,
        "agent_failed_with_context": FallbackResponse.workflow_context_fallback,
        "generic_error": FallbackResponse.generic_error_fallback,
    }
    
    handler: Callable[..., Dict[str, Any]] = fallback_map.get(error_type, FallbackResponse.generic_error_fallback)
    try:
        return handler(**kwargs)
    except TypeError:
        # Fallback handler might not accept all kwargs
        logger.warning("Error type handler %s received unexpected kwargs", error_type)
        return FallbackResponse.generic_error_fallback(
            error_message="An error occurred while generating fallback response",
            session_id=kwargs.get("session_id")
        )
