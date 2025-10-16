"""
Test script for rate limiter functionality
Run this to verify rate limiting is working correctly
"""

import time
from agent.rate_limiter import RateLimiter, TokenCounter, rate_limit_check, count_tokens_estimate

def test_rate_limiter():
    print("=" * 50)
    print("Testing Rate Limiter")
    print("=" * 50)
    
    # Test 1: Basic rate limiting
    print("\n1. Testing basic rate limiting (10 calls/min for Gemini)...")
    limiter = RateLimiter(max_calls_per_minute=10)
    
    for i in range(12):
        can_proceed = limiter.can_proceed()
        wait_time_val = limiter.wait_time()
        print(f"Call {i+1}: can_proceed={can_proceed}, wait_time={wait_time_val:.2f}s")
        
        if not can_proceed:
            print(f"   → Rate limit hit! Need to wait {wait_time_val:.0f} seconds")
            break
    
    # Test 2: Token counting
    print("\n2. Testing token counting...")
    counter = TokenCounter()
    
    test_texts = [
        "Short text",
        "This is a medium length text with more words",
        "This is a much longer text that should have significantly more tokens when counted using our estimation method"
    ]
    
    for text in test_texts:
        tokens = count_tokens_estimate(text)
        counter.add_tokens(tokens)
        print(f"Text ({len(text)} chars): ~{tokens} tokens")
    
    print(f"\nTotal tokens counted: {counter.get_total()}")
    
    # Test 3: Wait time calculation
    print("\n3. Testing wait time calculation...")
    limiter = RateLimiter(max_calls_per_minute=5)
    
    # Make 5 requests
    for i in range(5):
        limiter.can_proceed()  # This records the request
        time.sleep(0.1)  # Small delay
    
    # Try 6th request
    can_proceed = limiter.can_proceed()
    wait_time_val = limiter.wait_time()
    print(f"After 5 requests: can_proceed={can_proceed}, wait_time={wait_time_val:.2f}s")
    
    # Test 4: Rate limit reset after waiting
    print("\n4. Testing rate limit reset...")
    print(f"Waiting {wait_time_val + 1:.0f} seconds for rate limit to reset...")
    time.sleep(wait_time_val + 1)
    
    can_proceed = limiter.can_proceed()
    wait_time_val = limiter.wait_time()
    print(f"After waiting: can_proceed={can_proceed}, wait_time={wait_time_val:.2f}s")
    
    # Test 5: Character limit enforcement
    print("\n5. Testing character limit enforcement...")
    from agent.rate_limiter import enforce_character_limit
    
    long_text = "A" * 5000
    limited_text = enforce_character_limit(long_text, max_chars=3000)
    print(f"Original length: {len(long_text)} chars")
    print(f"Limited length: {len(limited_text)} chars")
    print(f"Enforced correctly: {len(limited_text) == 3000}")
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)

if __name__ == "__main__":
    test_rate_limiter()
