import os
import time
import jwt  # Alternatively, you can use from jose import jwt
import requests
from fastapi import Header, Depends
from fastapi import HTTPException, status

from wsi_service.api.v3.integrations.default import Default
from botocore.exceptions import BotoCoreError, ClientError
from jwt import DecodeError, ExpiredSignatureError

from aiocache import caches

# Configure cache in memory
caches.set_config({
    'default': {
        'cache': "aiocache.SimpleMemoryCache",  # You can swap this with RedisCache for more advanced usage
        'ttl': 3000,  # Cache TTL in seconds
    }
})

cache = caches.get('default')

class cognitoAuth(Default):
    def __init__(self, settings, logger, http_client=None):
        super().__init__(settings, logger, http_client)
        self.idp_url = settings.idp_url
        self.client_id = settings.client_id
        self.cognito_user_pool_id = settings.cognito_user_pool_id  # Add this to settings
        self.aws_region = settings.aws_region  # Add this to settings
        self.jwks_url = settings.jwks_url
        
        self.prod_idp_url = settings.prod_idp_url
        self.prod_client_id = settings.prod_client_id
        self.prod_cognito_user_pool_id = settings.prod_cognito_user_pool_id  # Add this to settings
        self.prod_aws_region = settings.prod_aws_region  # Add this to settings
        self.prod_jwks_url = settings.prod_jwks_url


    @staticmethod
    def global_depends():
        # This function returns another function that FastAPI can use as a dependency
        async def dependency(authorization: str = Header(None)):
            # You can process the 'authorization' header here if needed
            return authorization
        return Depends(dependency)
        
    async def allow_access_slide(self, auth_payload, slide_id, manager, plugin, slide=None , calling_function=None):
        # Extract the token from the payload
        print("In Cognito Allow Slide Access")
        try:
            token = None
        
            tokens = auth_payload.strip("'").split(" ") # split takes into account any "bearer= " style mess
        except:
           
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="No token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
        
        for testtoken in tokens:
            if len(testtoken) > 20: # ignores anything too short in the token string
                token = testtoken
        if not token:
            
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="No token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
        # Token extracted, let's start testing it

        # Check if token is cached
        (valid, systemName) = await cache.get(token)
        if valid is not None:
            if not valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token (cached)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            print("leaving cognito - cached valid/true token")
            return True, systemName
    
        # Token not cached, Validate it against AWS Cognito
        try:
            decoded_token, systemName = self.validate_cognito_token(token)
            valid_dev = decoded_token.get("client_id") == self.client_id
            valid_prod = decoded_token.get("client_id") == self.prod_client_id
            valid = valid_dev or valid_prod
            # Store in cache (cache both valid and invalid results)
            await cache.set(token, (valid, systemName) , ttl=3000)  # cache result for 50 minutes
    
            if not valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            print("leaving cognito auth py - valid token")
            return True, systemName


        except (DecodeError, ExpiredSignatureError) as e:
            await cache.set(token, False, ttl=3000)  # cache result for 50 minutes - it's definately invalid
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
        except (BotoCoreError, ClientError) as e:
            # don't cache this, as it might be a connection error or similar
            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token provided",
                                headers={"WWW-Authenticate": "Bearer"},
                            )

      
    def validate_cognito_token(self, token):
        # amended to validate against a list of different jwks servers
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]

        jwks_list = [
                     {"system":"prod","url":self.prod_jwks_url},
                     {"system":"dev","url":self.jwks_url}
                    ]
    
        for jwks_dict in jwks_list:
            try:
                response = requests.get(jwks_dict["url"])
                keys = response.json()["keys"]
            
                # Find the key that matches the kid in the JWT header
                key = next(k for k in keys if k["kid"] == kid)
            
                # Use the key to validate the token (you can use PyJWT or any other library here)
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                decoded_token = jwt.decode(token, public_key, algorithms=["RS256"],options={"verify_exp": True})
            
                return decoded_token, jwks_dict["system"]
            except Exception as e:
                continue  # Try the next JWKS URL
        
        raise DecodeError("Token could not be validated against any known Cognito JWKS URL.")