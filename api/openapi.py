"""Serve an OpenAPI schema for GPT Action integrations."""
from __future__ import annotations

from typing import Any, Dict

from pydantic.schema import schema as generate_schema

from src.api_utils import BaseJsonHandler
from src.schemas import (
    AnalyzeNewsRequest,
    AnalyzeNewsResponse,
    CleanupRequest,
    CleanupResponse,
    HealthResponse,
    MarketFetchRequest,
    MarketFetchResponse,
    NewsFetchRequest,
    NewsFetchResponse,
    StorageListResponse,
)
from src.security import SIGNATURE_HEADER

SCHEMA_MODELS = [
    HealthResponse,
    MarketFetchRequest,
    MarketFetchResponse,
    NewsFetchRequest,
    NewsFetchResponse,
    AnalyzeNewsRequest,
    AnalyzeNewsResponse,
    StorageListResponse,
    CleanupRequest,
    CleanupResponse,
]

raw_schema = generate_schema(SCHEMA_MODELS, ref_prefix="#/components/schemas/")
components = raw_schema.get("definitions", {})

OPENAPI: Dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {
        "title": "AWS-WEBse Crypto Aggregator",
        "version": "1.0.0",
        "description": "Serverless API for crypto market snapshots, news aggregation, and clustering."
    },
    "servers": [
        {
            "url": "https://ty-ap.vercel.app",
            "description": "Production"
        }
    ],
    "paths": {
        "/api/health": {
            "get": {
                "summary": "Service health check",
                "responses": {
                    "200": {
                        "description": "Service OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/market_fetch": {
            "post": {
                "summary": "Fetch market data from multiple exchanges",
                "security": [{"HmacSignature": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MarketFetchRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Market snapshots",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MarketFetchResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/news_fetch": {
            "post": {
                "summary": "Fetch and normalize crypto news",
                "security": [{"HmacSignature": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NewsFetchRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "News items",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/NewsFetchResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/analyze_news": {
            "post": {
                "summary": "Cluster news events",
                "security": [{"HmacSignature": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AnalyzeNewsRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Clustered events",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AnalyzeNewsResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/store_list": {
            "get": {
                "summary": "List stored JSON keys for debugging",
                "parameters": [
                    {
                        "name": "prefix",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 100}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Key list",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/StorageListResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/admin_cleanup": {
            "post": {
                "summary": "Remove expired JSON objects",
                "security": [{"HmacSignature": []}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CleanupRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Cleanup results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CleanupResponse"}
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "securitySchemes": {
            "HmacSignature": {
                "type": "apiKey",
                "in": "header",
                "name": SIGNATURE_HEADER,
                "description": "HMAC SHA-256 of the raw JSON body using the shared secret"
            }
        },
        "schemas": components,
    }
}


class handler(BaseJsonHandler):
    def handle_get(self, context) -> Dict[str, Any]:  # type: ignore[override]
        return OPENAPI
