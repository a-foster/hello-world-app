"""
Lambda Handler with OpenTelemetry Instrumentation

This module implements a simple Hello World API with comprehensive observability
using OpenTelemetry for distributed tracing and AWS X-Ray integration.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

# AWS X-Ray integration
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.aws import AwsXRayPropagator

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# OpenTelemetry Configuration
# ============================================================================

def configure_tracing():
    """
    Configure OpenTelemetry with AWS X-Ray integration
    """
    # Set up AWS X-Ray propagator for distributed tracing
    set_global_textmap(AwsXRayPropagator())

    # Create resource with service information
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: os.getenv('OTEL_SERVICE_NAME', 'hello-world-api'),
        ResourceAttributes.SERVICE_VERSION: os.getenv('SERVICE_VERSION', '1.0.0'),
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv('ENVIRONMENT', 'dev'),
        "faas.name": os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown'),
        "faas.version": os.getenv('AWS_LAMBDA_FUNCTION_VERSION', 'unknown'),
    })

    # Create tracer provider with AWS X-Ray ID generator
    tracer_provider = TracerProvider(
        resource=resource,
        id_generator=AwsXRayIdGenerator()
    )

    # Configure OTLP exporter for AWS X-Ray
    # In Lambda, we use the ADOT Collector sidecar or AWS Distro for OpenTelemetry
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4318/v1/traces'),
        headers={}
    )

    # Add batch span processor for efficient export
    tracer_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)

    # Auto-instrument AWS SDK (boto3/botocore) calls
    BotocoreInstrumentor().instrument()

    logger.info("OpenTelemetry tracing configured with AWS X-Ray integration")

# Configure tracing on module load
configure_tracing()

# Get tracer for creating custom spans
tracer = trace.get_tracer(__name__)

# ============================================================================
# Lambda Handler Functions
# ============================================================================

def create_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Create a standardized API Gateway response

    Args:
        status_code: HTTP status code
        body: Response body as dictionary
        headers: Optional additional headers

    Returns:
        API Gateway response dictionary
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }

    if headers:
        default_headers.update(headers)

    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body)
    }

@tracer.start_as_current_span("health_check")
def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle /health endpoint requests

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Health check response
    """
    span = trace.get_current_span()

    # Add custom attributes to the span
    span.set_attribute("http.route", "/health")
    span.set_attribute("custom.handler", "health_check")

    logger.info("Health check requested")

    response_body = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": os.getenv('OTEL_SERVICE_NAME', 'hello-world-api'),
        "version": os.getenv('SERVICE_VERSION', '1.0.0'),
        "environment": os.getenv('ENVIRONMENT', 'dev')
    }

    span.set_attribute("health.status", "healthy")

    return create_response(200, response_body)

@tracer.start_as_current_span("hello_endpoint")
def handle_hello(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle /hello endpoint requests

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Hello world response
    """
    span = trace.get_current_span()

    # Add custom attributes to the span
    span.set_attribute("http.route", "/hello")
    span.set_attribute("custom.handler", "hello")

    # Extract query parameters if present
    query_params = event.get('queryStringParameters') or {}
    name = query_params.get('name', 'World')

    # Add query parameter to span for traceability
    span.set_attribute("request.name_parameter", name)

    logger.info(f"Hello endpoint requested with name: {name}")

    # Create a child span for "business logic"
    with tracer.start_as_current_span("generate_greeting") as greeting_span:
        greeting_span.set_attribute("greeting.recipient", name)

        # Simulate some business logic
        greeting = f"Hello, {name}!"

        greeting_span.set_attribute("greeting.message", greeting)
        greeting_span.add_event("Greeting generated", {
            "recipient": name,
            "length": len(greeting)
        })

    response_body = {
        "message": greeting,
        "timestamp": datetime.utcnow().isoformat(),
        "requestId": context.aws_request_id,
        "path": event.get('path', '/hello')
    }

    span.set_attribute("response.message_length", len(greeting))

    return create_response(200, response_body)

@tracer.start_as_current_span("lambda_handler")
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - routes requests to appropriate handlers

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    span = trace.get_current_span()

    # Add Lambda context information to span
    span.set_attribute("faas.execution", context.aws_request_id)
    span.set_attribute("faas.coldstart", bool(os.getenv('AWS_LAMBDA_INITIALIZATION_TYPE') == 'on-demand'))
    span.set_attribute("cloud.account.id", context.invoked_function_arn.split(':')[4])

    # Extract request information
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')

    span.set_attribute("http.method", http_method)
    span.set_attribute("http.target", path)

    # Add correlation ID for request tracking
    request_id = context.aws_request_id
    span.set_attribute("request.id", request_id)

    logger.info(
        "Request received",
        extra={
            "request_id": request_id,
            "method": http_method,
            "path": path
        }
    )

    try:
        # Route based on path
        if path.endswith('/health'):
            response = handle_health_check(event, context)
        elif path.endswith('/hello'):
            response = handle_hello(event, context)
        else:
            logger.warning(f"Unknown path requested: {path}")
            span.set_attribute("http.status_code", 404)
            response = create_response(404, {
                "error": "Not Found",
                "message": f"Path {path} not found",
                "requestId": request_id
            })

        # Add response status to span
        span.set_attribute("http.status_code", response['statusCode'])

        # Add span event for successful response
        span.add_event("Response sent", {
            "status_code": response['statusCode']
        })

        logger.info(f"Request completed successfully: {response['statusCode']}")

        return response

    except Exception as e:
        # Log and trace errors
        logger.error(f"Error processing request: {str(e)}", exc_info=True)

        # Record exception in span
        span.record_exception(e)
        span.set_attribute("http.status_code", 500)
        span.set_attribute("error", True)

        return create_response(500, {
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "requestId": request_id
        })
