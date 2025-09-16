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
caches.set_config(
    {
        "default": {
            "cache": "aiocache.SimpleMemoryCache",  # You can swap this with RedisCache for more advanced usage
            "ttl": 3000,  # Cache TTL in seconds
        }
    }
)

cache = caches.get("default")


class cognitoAuth(Default):
    def __init__(self, settings, logger, http_client=None):
        super().__init__(settings, logger, http_client)
        #print(f"getting cognito details from settings. settings.cloud has {len(settings.cloud.keys())} keys")
        #print(f"region is set to: type{type(settings.cloud.cognito_aws_region)}={settings.cloud.cognito_aws_region}")
        self.idp_url = settings.cloud.idp_url        
        self.client_id = settings.cloud.client_id        
        self.cognito_user_pool_id = settings.cloud.cognito_user_pool_id
        self.aws_region = settings.cloud.cognito_aws_region          
        self.jwks_url = settings.cloud.jwks_url
        
        

        self.prod_idp_url = settings.cloud.prod_idp_url        
        self.prod_client_id = settings.cloud.prod_client_id        
        self.prod_cognito_user_pool_id = settings.cloud.prod_cognito_user_pool_id        
        self.prod_aws_region = settings.cloud.prod_cognito_aws_region        
        self.prod_jwks_url = settings.cloud.prod_jwks_url
        
        self.debug = settings.debug
        self.hack_token = settings.hack_token

    @staticmethod
    def global_depends():
        # This function returns another function that FastAPI can use as a dependency
        async def dependency(authorization: str = Header(None)):
            # You can process the 'authorization' header here if needed
            return authorization

        return Depends(dependency)

    def _is_hack_token(self, token: str) -> bool:
        import hmac

        # Only allow if explicitly enabled AND a secret is set
        allow = (
            os.environ.get("OP_PROD_MODE", "false") == "false"
        )  # ie only allow if in dev mode
        secret = self.hack_token
        print(
            f"Testing Secret, len() {len(token)} against hack token - len(): {len(secret)}"
        )

        # constant-time compare to avoid accidental leaks via timing
        return bool(allow and secret and hmac.compare_digest(token, secret))

    async def allow_access_slide(
        self, auth_payload, slide_id, manager, plugin, slide=None, calling_function=None
    ):
        # Extract the token from the payload
        # print(f"Overall Debug mode set to: {self.debug}")
        if self.debug:
            print(
                f"In Cognito Allow Slide Access - calling function was: {calling_function}"
            )
        try:
            token = None

            tokens = auth_payload.strip("'").split(
                " "
            )  # split takes into account any "bearer= " style mess
        except:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if self.debug:
            print("Finding token")
        for testtoken in tokens:
            if len(testtoken) > 20:  # ignores anything too short in the token string
                token = testtoken

        if not token:
            print("no token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Token extracted, let's start testing it
        if self.debug:
            print("checking cache")
        # Check if token is cached
        cached_value = await cache.get(token)
        if cached_value is not None:
            if self.debug:
                print("Using cached auth/reject value")
            try:
                valid, systemName = cached_value
            except:
                print(
                    f"Something happend in expanding cached_value. Expecting tupe I guess... got: {type(cached_value)} {cached_value}"
                )
            if not valid:
                print("cache said it wasn't valid")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token (cached)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if self.debug:
                print("leaving cognito - cached valid/true token")
            return True, systemName
        if self.debug:
            print("not cached, validating")

        if self._is_hack_token(token):
            if self.debug:
                print("Using DEV HACK TOKEN — bypassing Cognito")
            await cache.set(token, (True, "dev"), ttl=3000)
            return True, "dev"

        if self.debug:
            print("Not a match with the `hack token` - continuing")

        # Token not cached and not hack-token, Validate it against AWS Cognito
        try:
            decoded_token, systemName = self.validate_cognito_token(token)
            if self.debug:
                print("decoded")
            valid_dev = decoded_token.get("client_id") == self.client_id
            valid_prod = decoded_token.get("client_id") == self.prod_client_id
            valid = valid_dev or valid_prod
            if self.debug:
                print(f"token is valid: {valid}, storing in cache")
            # Store in cache (cache both valid and invalid results)
            await cache.set(
                token, (valid, systemName), ttl=3000
            )  # cache result for 50 minutes

            if not valid:
                print("Not Valid against either prod or dev")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if self.debug:
                print("leaving cognito auth py - valid token")
            return True, systemName

        except (DecodeError, ExpiredSignatureError) as e:
            await cache.set(
                token, (False, "None") , ttl=3000
            )  # cache result for 50 minutes - it's definately invalid
            print("Either DecodeError, ExpiredSignatureError")
            print(f"Error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token provided",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except (BotoCoreError, ClientError) as e:
            # don't cache this, as it might be a connection error or similar
            print("Either BotoCoreError, ClientError")
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
            {"system": "prod", "url": self.prod_jwks_url},
            {"system": "dev", "url": self.jwks_url},
        ]

        for jwks_dict in jwks_list:
            try:
                response = requests.get(jwks_dict["url"])

                keys = response.json()["keys"]

                # Find the key that matches the kid in the JWT header
                key = next(k for k in keys if k["kid"] == kid)

                # Use the key to validate the token (you can use PyJWT or any other library here)
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                decoded_token = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    options={"verify_exp": True},
                )

                return decoded_token, jwks_dict["system"]
            except Exception as e:
                print(
                    f"did not validate against {jwks_dict['system']} (url={jwks_dict['url']}) result: {repr(e)}"
                )
                continue  # Try the next JWKS URL

        raise DecodeError(
            "Token could not be validated against any known Cognito JWKS URL."
        )
