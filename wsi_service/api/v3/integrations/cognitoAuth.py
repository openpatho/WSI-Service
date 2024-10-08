import os
import time
import boto3
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

        self.cognito_client = boto3.client('cognito-idp', region_name=self.aws_region)

    async def allow_access_slide(self, auth_payload, slide_id, manager, plugin, slide=None , calling_function=None):
        # Extract the token from the payload
        token = auth_payload.get("token")
        if not token:
            raise PermissionError("No token provided")

        try:
            # Validate the token against AWS Cognito
            decoded_token = self.validate_cognito_token(token)
            if decoded_token.get("client_id") != self.client_id:
                raise PermissionError("Invalid client ID")

            # Optionally, check custom claims or other parts of the token
            return True

        except (DecodeError, ExpiredSignatureError) as e:
            raise PermissionError(f"Invalid token: {str(e)}")
        except (BotoCoreError, ClientError) as e:
            raise PermissionError(f"Error validating token with Cognito: {str(e)}")

    def validate_cognito_token(self, token):
        # Decode the JWT token without verification to extract the header and kid
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]

        # Fetch the public keys from Cognito's JWK endpoint
        jwks_url = f"https://cognito-idp.{self.aws_region}.amazonaws.com/{self.cognito_user_pool_id}/.well-known/jwks.json"
        response = requests.get(jwks_url)
        keys = response.json()["keys"]
    
        # Find the key that matches the kid in the JWT header
        key = next(k for k in keys if k["kid"] == kid)
    
        # Use the key to validate the token (you can use PyJWT or any other library here)
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)

        # Verify and decode the token
        decoded_token = jwt.decode(token, key=key, algorithms=["RS256"])

        return decoded_token
