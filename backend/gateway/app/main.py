import os
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user_service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product_service:8002")
SENSOR_SERVICE_URL = os.getenv("SENSOR_SERVICE_URL", "http://sensor_service:8003")
ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL", "http://analytics_consumer:8004")

http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await http_client.aclose()

app = FastAPI(
    title="OmniMesh Event-Driven API Gateway",
    version="2.0.0",
    description="Central Entrypoint & Routing Gateway for Event-Driven Microservices (MQTT & TimescaleDB)",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/api/health")
async def gateway_health():
    """Aggregated health check across all microservices and infrastructure."""
    health_report = {
        "gateway": "online",
        "services": {}
    }

    endpoints = {
        "user_service": USER_SERVICE_URL,
        "product_service": PRODUCT_SERVICE_URL,
        "sensor_service": SENSOR_SERVICE_URL,
        "analytics_consumer": ANALYTICS_SERVICE_URL
    }

    for name, base_url in endpoints.items():
        try:
            r = await http_client.get(f"{base_url}/health")
            health_report["services"][name] = r.json() if r.status_code == 200 else {"status": "degraded"}
        except Exception as e:
            health_report["services"][name] = {"status": "offline", "error": str(e)}

    return health_report

async def proxy_request(service_base: str, path: str, request: Request):
    target_url = f"{service_base}/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    body = await request.body()

    try:
        req = http_client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=dict(request.query_params),
            content=body
        )
        resp = await http_client.send(req)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, 
            detail=f"Downstream service unavailable: {service_base}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gateway proxy error: {str(exc)}"
        )

# Microservice Route Proxying
@app.api_route("/api/users{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_user_service(path: str, request: Request):
    return await proxy_request(USER_SERVICE_URL, f"users{path}", request)

@app.api_route("/api/products{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_product_service(path: str, request: Request):
    return await proxy_request(PRODUCT_SERVICE_URL, f"products{path}", request)

@app.api_route("/api/sensors{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_sensor_service(path: str, request: Request):
    return await proxy_request(SENSOR_SERVICE_URL, f"sensors{path}", request)

@app.api_route("/api/events{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_analytics_service(path: str, request: Request):
    return await proxy_request(ANALYTICS_SERVICE_URL, f"events{path}", request)

@app.api_route("/api/ac{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def route_ac_service(path: str, request: Request):
    return await proxy_request(SENSOR_SERVICE_URL, f"ac{path}", request)

