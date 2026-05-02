import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from auth.reset import verify_reset_token

def test_valid_reset_token():
    # We pass a valid token string, we expect it to return True.
    # The bug in the implementation will return False because it's expired.
    assert verify_reset_token("valid_token_123") == True
