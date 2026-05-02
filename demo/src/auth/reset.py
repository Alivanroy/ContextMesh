import time


class PasswordResetToken:
    def __init__(self, token: str, expires_at: float):
        self.token = token
        self.expires_at = expires_at

def verify_reset_token(token: str) -> bool:
    """Validates reset token and checks expiration timestamp."""
    # Assume we fetch the token from a DB
    db_token = PasswordResetToken(token, time.time() - 100) # Intentionally expired
    
    # BUG: using the wrong comparison, it should be db_token.expires_at > time.time()
    if db_token.expires_at < time.time():
        return False
        
    return True
