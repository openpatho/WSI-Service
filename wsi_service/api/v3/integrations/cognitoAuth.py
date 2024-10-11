import os
import time
import jwt  # Alternatively, you can use from jose import jwt
from wsi_service.api.v3.integrations.default import Default
from botocore.exceptions import BotoCoreError, ClientError
from jwt import DecodeError, ExpiredSignatureError

class cognitoAuth(Default):
    def __init__(self, settings, logger, http_client=None):
        super().__init__(settings, logger, http_client)
        self.idp_url = settings.idp_url
        self.client_id = settings.client_id
        self.cognito_user_pool_id = settings.cognito_user_pool_id  # Add this to settings
        self.aws_region = settings.aws_region  # Add this to settings
        self.jwks_url = settings.jwks_url


    async def allow_access_slide(self, auth_payload, slide_id, manager, plugin, slide=None , calling_function=None):
        # Extract the token from the payload
        token = None
        tokens = auth_payload.strip("'").split(" ") # split takes into account any "bearer= " style mess
        for testtoken in tokens:
            if len(testtoken) > 20: # ignores anything too short in the token string
                token = testtoken
        if not token:
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="No token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )

        try:
            # Validate the token against AWS Cognito
            decoded_token = self.validate_cognito_token(token)
            if decoded_token.get("client_id") != self.client_id:
                raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )

            # Optionally, check custom claims or other parts of the token
            return True

        except (DecodeError, ExpiredSignatureError) as e:
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
        except (BotoCoreError, ClientError) as e:
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )

    def validate_cognito_token(token):
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]
    
       
        response = requests.get(self.jwks_url)
        keys = response.json()["keys"]
    
        # Find the key that matches the kid in the JWT header
        key = next(k for k in keys if k["kid"] == kid)
    
        # Use the key to validate the token (you can use PyJWT or any other library here)
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        decoded_token = jwt.decode(token, public_key, algorithms=["RS256"],options={"verify_exp": False})
    
        return decoded_token
