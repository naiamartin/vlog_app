from pwdlib import PasswordHash

# Reuse the same password hashing configuration across endpoints.
password_hash = PasswordHash.recommended()

