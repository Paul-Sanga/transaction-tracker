import os
import json
from rich import print
from pathlib import Path
from jwcrypto import jwk, jwe
from dotenv import load_dotenv

load_dotenv()
secret_key = os.getenv("KEY")
auth_file = os.getenv("AUTH_FILE")

class AuthenticationError(Exception):
    pass

def generate_token(user_id, email):

    key = jwk.JWK(
        kty="oct",
        k=secret_key
    )

    payload = {
        "user_id": user_id,
        "email": email
    }

    protected_header = {
        "alg": "dir",
        "enc": "A256GCM"
    }

    token = jwe.JWE(
        plaintext=json.dumps(payload).encode("utf-8"),
        protected=protected_header
    )

    token.add_recipient(key)
    file_path = Path(auth_file)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(auth_file, "w", encoding="utf-8") as file:
        file.write(token.serialize(compact=True))

def verify_token(token):
    try:
        key = jwk.JWK(
            kty="oct",
            k=secret_key
        )
    
        encrypted_token = jwe.JWE()
        encrypted_token.deserialize(token, key=key)

        payload = json.loads(
            encrypted_token.payload.decode("utf-8")
        )


        return payload["user_id"], payload["email"]
    except Exception as e:
        print(e)
        return None

def get_payload():
    file_path = Path(auth_file)

    if not file_path.is_file():
        raise AuthenticationError("Please login first")

    with file_path.open('r', encoding="utf-8") as file:
        token = file.read().strip()

    payload = verify_token(token)

    if payload is None:
        raise AuthenticationError("Invalid or expired session")
    return payload