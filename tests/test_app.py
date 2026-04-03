"""
Tests for the Lambda handler
"""
import json
from unittest.mock import Mock
import pytest
from src.app import handler, create_response, handle_health_check, handle_hello


class TestCreateResponse:
    """Tests for create_response helper function"""

    def test_create_response_basic(self):
        """Test basic response creation"""
        response = create_response(200, {"message": "test"})

        assert response["statusCode"] == 200
        assert "Content-Type" in response["headers"]
        assert response["headers"]["Content-Type"] == "application/json"
        assert json.loads(response["body"]) == {"message": "test"}

    def test_create_response_with_custom_headers(self):
        """Test response with custom headers"""
        custom_headers = {"X-Custom-Header": "value"}
        response = create_response(200, {"data": "test"}, custom_headers)

        assert response["headers"]["X-Custom-Header"] == "value"
        assert "Content-Type" in response["headers"]


class TestHealthCheck:
    """Tests for health check endpoint"""

    def test_health_check_returns_200(self):
        """Test health check returns 200 status"""
        event = {"path": "/health", "httpMethod": "GET"}
        context = Mock(aws_request_id="test-request-id")

        response = handle_health_check(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "healthy"
        assert "timestamp" in body
        assert body["service"] == "hello-world-api"


class TestHelloEndpoint:
    """Tests for hello endpoint"""

    def test_hello_default_name(self):
        """Test hello endpoint with default name"""
        event = {"path": "/hello", "httpMethod": "GET"}
        context = Mock(aws_request_id="test-request-id", invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test")

        response = handle_hello(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Hello, World!"

    def test_hello_with_custom_name(self):
        """Test hello endpoint with custom name parameter"""
        event = {
            "path": "/hello",
            "httpMethod": "GET",
            "queryStringParameters": {"name": "Claude"}
        }
        context = Mock(aws_request_id="test-request-id", invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test")

        response = handle_hello(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Hello, Claude!"


class TestMainHandler:
    """Tests for main Lambda handler"""

    def test_handler_health_route(self):
        """Test handler routes to health check"""
        event = {"path": "/health", "httpMethod": "GET"}
        context = Mock(
            aws_request_id="test-request-id",
            invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test"
        )

        response = handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "healthy"

    def test_handler_hello_route(self):
        """Test handler routes to hello endpoint"""
        event = {"path": "/hello", "httpMethod": "GET"}
        context = Mock(
            aws_request_id="test-request-id",
            invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test"
        )

        response = handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "message" in body

    def test_handler_unknown_route(self):
        """Test handler returns 404 for unknown routes"""
        event = {"path": "/unknown", "httpMethod": "GET"}
        context = Mock(
            aws_request_id="test-request-id",
            invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test"
        )

        response = handler(event, context)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error"] == "Not Found"

    def test_handler_exception_handling(self):
        """Test handler catches and handles exceptions"""
        # Pass a malformed event that will cause an error during processing
        event = {"path": "/hello", "httpMethod": "GET"}
        context = Mock(
            aws_request_id="test-request-id",
            invoked_function_arn="invalid-arn"  # This will cause an error
        )

        response = handler(event, context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"
