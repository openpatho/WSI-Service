from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import time, pickle, os

from wsi_service.api.root import add_routes_root
from wsi_service.api.v3 import add_routes_v3
from wsi_service.singletons import settings
from wsi_service.slide_manager import SlideManager




try:
    from wsi_service.utils.cloudwrappers.redis_openpatho import RedisLogger
except:
    from utils.cloudwrappers.redis_openpatho import RedisLogger


redislogger = RedisLogger() 

openapi_url = "/openapi.json"
if settings.disable_openapi:
    openapi_url = ""

slide_manager = SlideManager(
    settings.mapper_address,
    settings.data_dir,
    settings.inactive_histo_image_timeout_seconds,
    settings.image_handle_cache_size,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    slide_manager.close()

docsUrl = "/docs" if not settings.prod_mode else None 

app = FastAPI(
    title=settings.title,
    description=settings.description,
    version=settings.version,
    docs_url=docsUrl,
    redoc_url=None,
    openapi_url="/openapi.json" if not settings.disable_openapi else "",
    root_path=settings.root_path,
    lifespan=lifespan,
    debug=settings.debug
)

add_routes_root(app, settings)

app_v3 = FastAPI(openapi_url=openapi_url,
    docs_url=docsUrl,
    redoc_url=None,)

if settings.cors_allow_origins:
    for app_obj in [app, app_v3]:
        app_obj.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

add_routes_v3(app_v3, settings, slide_manager)

app.mount("/v3", app_v3)


def log_api_call(log_entry):
    #pass
    redislogger.add_health_log(log_entry)

def get_last_api_calls(service_name):
    #pass
    return redislogger.get_last_activity_time(service_name)
        
@app.middleware("http")
async def log_requests(request: Request, call_next):
    method = request.method
    path = request.url.path
    query_params = dict(request.query_params)
    timestamp = time.time()

    body = {}
    if method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            pass  # Handle cases where body is not JSON

    # Create the log entry
    log_entry = {
        "service name":"wsi_service",
        "method": method,
        "path": path,
        "query_params": query_params,
        "body": body
    }

    # Log the API call to the pickle file
    log_api_call(log_entry)

    # Proceed with the request
    response = await call_next(request)
    
    # Add 30 minute Cache-Control header
    response.headers["Cache-Control"] = "private, max-age=1800"
    
    return response

@app.get("/health")
async def health_check():
    # Retrieve the last 10 API calls from Redis
    try:
        last_calls = get_last_api_calls("wsi_service")
        return {"status": "healthy", "last_calls": last_calls}
    except:
        print("error in health log retrieval")
        return {"status": "healthy"}