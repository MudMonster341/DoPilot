"""
Rate limiting and token management for DoPilot.
Prevents API quota exhaustion and manages costs.
"""

import os
import time
from functools import wraps
from typing import Callable, Any
import streamlit as st


class RateLimiter:
    """Simple rate limiter for LLM API calls."""
    
    def __init__(self, max_calls_per_minute: int = 10):
        self.max_calls = max_calls_per_minute
        self.calls = []
        
    def can_proceed(self) -> bool:
        """Check if we can make another API call."""
        current_time = time.time()
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls if current_time - t < 60]
        
        if len(self.calls) >= self.max_calls:
            return False
        
        self.calls.append(current_time)
        return True
    
    def wait_time(self) -> float:
        """Get time to wait before next call is allowed."""
        if not self.calls:
            return 0.0
        
        current_time = time.time()
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls if current_time - t < 60]
        
        if len(self.calls) < self.max_calls:
            return 0.0
        
        # If at limit, wait until oldest call expires (60 seconds from oldest)
        oldest_call = min(self.calls)
        time_since_oldest = current_time - oldest_call
        
        # Add 2 second buffer to ensure we're past the 60 second window
        return max(0.0, (60 - time_since_oldest) + 2)


class TokenCounter:
    """Track token usage across requests."""
    
    def __init__(self):
        self.total_tokens = 0
        self.request_tokens = []
        
    def add_tokens(self, count: int):
        """Add tokens used in a request."""
        self.total_tokens += count
        self.request_tokens.append({
            'count': count,
            'timestamp': time.time()
        })
        
    def get_total(self) -> int:
        """Get total tokens used."""
        return self.total_tokens
    
    def get_session_tokens(self) -> int:
        """Get tokens used in current session (last hour)."""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        return sum(
            req['count'] 
            for req in self.request_tokens 
            if req['timestamp'] > hour_ago
        )


# Environment-driven configuration
def _get_int_env(name: str, default: int) -> int:
    """Safely parse integer environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


RATE_LIMIT_DISABLED = os.getenv("DISABLE_RATE_LIMITING", "false").lower() in {"1", "true", "yes", "on"}
GEMINI_MAX_CALLS = _get_int_env("GEMINI_MAX_CALLS_PER_MINUTE", 60)
GROQ_MAX_CALLS = _get_int_env("GROQ_MAX_CALLS_PER_MINUTE", 60)

# Global instances
gemini_limiter = RateLimiter(max_calls_per_minute=GEMINI_MAX_CALLS)
groq_limiter = RateLimiter(max_calls_per_minute=GROQ_MAX_CALLS)
token_counter = TokenCounter()


def rate_limit_check(model_provider: str = "gemini") -> tuple[bool, float]:
    """
    Check if we can proceed with an API call.
    Returns (can_proceed, wait_time)
    """
    if RATE_LIMIT_DISABLED:
        return True, 0.0

    limiter = gemini_limiter if model_provider == "gemini" else groq_limiter

    if not limiter.can_proceed():
        wait_time = limiter.wait_time()
        return False, wait_time

    return True, 0.0


def count_tokens_estimate(text: str) -> int:
    """
    Estimate token count for text.
    Rough estimate: 1 token ≈ 4 characters for English text.
    """
    return len(text) // 4


def enforce_character_limit(text: str, max_chars: int = 3000) -> str:
    """
    Enforce character limit to control token usage.
    """
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def with_rate_limit(model_provider: str = "gemini"):
    """
    Decorator to enforce rate limiting on LLM calls.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            can_proceed, wait_time = rate_limit_check(model_provider)
            
            if not can_proceed:
                if 'st' in globals():
                    st.warning(
                        f"Rate limit reached. Please wait {wait_time:.0f} seconds before the next request."
                    )
                time.sleep(wait_time + 1)
            
            result = func(*args, **kwargs)
            return result
        
        return wrapper
    return decorator


# Session state helpers for Streamlit
def init_rate_limiting_state():
    """Initialize rate limiting in Streamlit session state."""
    if 'api_call_count' not in st.session_state:
        st.session_state.api_call_count = 0
    if 'last_api_call' not in st.session_state:
        st.session_state.last_api_call = 0
    if 'total_tokens_used' not in st.session_state:
        st.session_state.total_tokens_used = 0


def check_session_limits() -> tuple[bool, str]:
    """
    Check if user has exceeded reasonable session limits.
    Returns (allowed, message)
    """
    if st.session_state.api_call_count > 50:
        return False, "Session limit reached (50 requests). Please refresh the page to continue."
    
    if st.session_state.total_tokens_used > 100000:
        return False, "Token limit reached for this session. Please refresh to continue."
    
    return True, ""


def get_rate_limit_status() -> dict[str, Any]:
    """
    Get current rate limiting status for display.
    Returns dictionary with rate limit information.
    """
    from typing import Any
    
    # Get current calls in the last minute for primary limiter (Gemini)
    current_time = time.time()
    gemini_calls_in_minute = len([t for t in gemini_limiter.calls if current_time - t < 60])
    
    max_calls_value: Any = "disabled" if RATE_LIMIT_DISABLED else gemini_limiter.max_calls
    
    return {
        'calls_this_minute': gemini_calls_in_minute if not RATE_LIMIT_DISABLED else 0,
        'max_calls_per_minute': max_calls_value,
        'total_tokens': st.session_state.get('total_tokens_used', 0),
        'total_calls': st.session_state.get('api_call_count', 0),
        'rate_limit_disabled': RATE_LIMIT_DISABLED
    }
