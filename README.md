# Hello World Lambda Application

A containerized Python Lambda function with comprehensive OpenTelemetry instrumentation and AWS X-Ray integration.

## Features

- **Python 3.11** Lambda function running in Docker container
- **OpenTelemetry Instrumentation** with manual SDK for detailed tracing
- **AWS X-Ray Integration** for distributed tracing
- **API Gateway Integration** with two endpoints: `/health` and `/hello`
- **Structured Logging** with correlation IDs
- **Automated CI/CD** via GitHub Actions with OIDC
- **Smoke Testing** as part of deployment pipeline

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      GitHub Repository                          │
│                   (hello-world-app)                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ Push to main
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Actions                               │
│  1. Build Docker image with OTel dependencies                   │
│  2. Push to Amazon ECR                                          │
│  3. Update Lambda function code                                 │
│  4. Run smoke tests (health + hello endpoints)                  │
└────────────────────┬────────────────────────────────────────────┘
                     │ OIDC Authentication
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Lambda                               │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Container Image (from ECR)                         │       │
│  │  - Python 3.11                                      │       │
│  │  - OpenTelemetry SDK                                │       │
│  │  - AWS X-Ray Exporter                               │       │
│  │  - Boto3 Auto-instrumentation                       │       │
│  └─────────────────────────────────────────────────────┘       │
│                           │                                     │
│                           │ Sends traces                        │
│                           ▼                                     │
│                  ┌─────────────────┐                            │
│                  │   AWS X-Ray     │                            │
│                  │ Service Map +   │                            │
│                  │    Traces       │                            │
│                  └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
.
├── src/
│   ├── app.py              # Lambda handler with OTel instrumentation
│   └── requirements.txt    # Python dependencies
├── .github/workflows/
│   └── deploy.yml          # CI/CD pipeline
├── Dockerfile              # Multi-stage container build
├── .dockerignore           # Docker ignore patterns
└── README.md               # This file
```

## API Endpoints

### GET /health

Health check endpoint that returns service status and metadata.

**Request:**
```bash
curl https://your-api-gateway-url.amazonaws.com/prod/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-04-02T10:30:00.000000",
  "service": "hello-world-api",
  "version": "1.0.0",
  "environment": "dev"
}
```

### GET /hello

Hello world endpoint with optional name parameter.

**Request:**
```bash
# Without name parameter
curl https://your-api-gateway-url.amazonaws.com/prod/hello

# With name parameter
curl "https://your-api-gateway-url.amazonaws.com/prod/hello?name=Sano"
```

**Response:**
```json
{
  "message": "Hello, Sano!",
  "timestamp": "2024-04-02T10:30:00.000000",
  "requestId": "abc123-def456-ghi789",
  "path": "/hello"
}
```

## OpenTelemetry Instrumentation

The application includes comprehensive OpenTelemetry instrumentation:

### Automatic Instrumentation
- **AWS SDK (boto3/botocore)**: All AWS API calls are automatically traced
- **HTTP requests**: Request/response metadata captured

### Manual Instrumentation
- **Custom spans** for each handler function (`health_check`, `hello_endpoint`)
- **Span attributes** for request metadata (method, path, parameters)
- **Span events** for important operations (greeting generation, response sent)
- **Exception recording** for error tracking
- **Correlation IDs** for request tracking across services

### Trace Metadata

Each trace includes:
- Service name, version, and environment
- Lambda function name and version
- AWS account ID
- Request ID for correlation
- Cold start indicator
- HTTP method, path, and status code
- Custom business logic attributes

## Local Development

### Prerequisites

- Docker
- AWS CLI configured
- Python 3.11+ (for local testing without Docker)

### Build Docker Image Locally

```bash
# Build the image
docker build -t hello-world-lambda .

# Test locally using Lambda Runtime Interface Emulator
docker run -p 9000:8080 hello-world-lambda

# In another terminal, invoke the function
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{
    "httpMethod": "GET",
    "path": "/hello",
    "queryStringParameters": {"name": "Local"}
  }'
```

### Run Tests Locally (without Docker)

```bash
cd src

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Python directly (requires mock event/context)
python -c "
from app import handler
import json

class Context:
    request_id = 'local-test'
    invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'

event = {
    'httpMethod': 'GET',
    'path': '/hello',
    'queryStringParameters': {'name': 'Test'}
}

result = handler(event, Context())
print(json.dumps(result, indent=2))
"
```

## Deployment

### Prerequisites

The infrastructure must be deployed first using the Terraform repository. After infrastructure deployment, configure GitHub repository settings.

### GitHub Configuration

1. **Repository Variables** (Settings > Secrets and variables > Actions > Variables):
   - `AWS_REGION`: AWS region (e.g., `us-east-1`)
   - `AWS_GITHUB_ROLE_ARN`: IAM role ARN from Terraform output (`github_oidc_role_arn_app`)
   - `ECR_REPOSITORY_NAME`: ECR repository name from Terraform output
   - `LAMBDA_FUNCTION_NAME`: Lambda function name from Terraform output
   - `API_GATEWAY_ENDPOINT`: API Gateway endpoint URL from Terraform output

2. **Get Values from Infrastructure**:
   ```bash
   cd ../tf-infra-serverless-rest-api
   terraform output
   ```

### Deployment Process

1. **Push to main branch**:
   ```bash
   git add .
   git commit -m "feat: update Lambda function"
   git push origin main
   ```

2. **GitHub Actions automatically**:
   - Authenticates with AWS using OIDC
   - Builds Docker image
   - Pushes image to ECR (with commit SHA and `latest` tags)
   - Updates Lambda function code
   - Waits for update to complete
   - Runs smoke tests on `/health` and `/hello` endpoints
   - Reports results in GitHub Actions summary

3. **Monitor deployment**:
   - Check GitHub Actions workflow run
   - View deployment summary in Actions tab
   - Access AWS X-Ray console to view traces

### Manual Deployment

If needed, you can deploy manually:

```bash
# Set variables
export AWS_REGION=us-east-1
export ECR_REPOSITORY=your-ecr-repo-url
export LAMBDA_FUNCTION_NAME=hello-world-api

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REPOSITORY

# Build and push
docker build -t $ECR_REPOSITORY:latest .
docker push $ECR_REPOSITORY:latest

# Update Lambda
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION_NAME \
  --image-uri $ECR_REPOSITORY:latest \
  --region $AWS_REGION
```

## Observability

### Viewing Traces in AWS X-Ray

1. Open AWS Console
2. Navigate to X-Ray service
3. View Service Map to see request flow
4. Click on traces to see detailed spans
5. Filter by annotations and metadata

**Example trace structure:**
```
lambda_handler (ROOT)
  ├─ hello_endpoint
  │   └─ generate_greeting
  └─ [boto3 calls if any]
```

### CloudWatch Logs

View Lambda logs:
```bash
aws logs tail /aws/lambda/hello-world-api --follow
```

### CloudWatch Metrics

Key metrics to monitor:
- **Invocations**: Number of function calls
- **Duration**: Execution time
- **Errors**: Failed invocations
- **Throttles**: Rate limit hits
- **ConcurrentExecutions**: Concurrent invocations

### Alarms

The infrastructure includes CloudWatch alarms for:
- Lambda errors (threshold: 5 errors in 1 minute)
- Lambda throttles (threshold: 10 throttles in 1 minute)
- Lambda duration (threshold: 5 seconds average over 2 periods)
- API Gateway 4XX errors
- API Gateway 5XX errors
- API Gateway latency

## Troubleshooting

### Deployment fails with "No such image"

Ensure you've pushed an initial image to ECR before deploying infrastructure, or update Lambda function code after infrastructure is created.

```bash
# Quick fix: push current code
cd hello-world-app
export ECR_URL=$(cd ../tf-infra-serverless-rest-api && terraform output -raw ecr_repository_url)
docker build -t $ECR_URL:latest .
docker push $ECR_URL:latest
```

### Smoke tests fail

Check:
1. API Gateway endpoint is correctly configured in GitHub variables
2. Lambda function is updated successfully
3. API Gateway stage is deployed

### Traces not appearing in X-Ray

Verify:
1. Lambda execution role has X-Ray permissions
2. X-Ray tracing is enabled on Lambda function
3. OTEL environment variables are set correctly
4. Check CloudWatch logs for OTel errors

### GitHub Actions authentication fails

Verify:
1. OIDC provider is created in AWS
2. IAM role trust policy includes correct GitHub repository
3. `AWS_GITHUB_ROLE_ARN` variable is set correctly

## Interview Discussion Points

### Observability Strategy
- **Why OpenTelemetry?** Vendor-neutral, future-proof, standardized instrumentation
- **Manual vs Auto-instrumentation**: Manual gives more control over span details
- **Sampling strategy**: In production, use adaptive sampling to control costs
- **Trace context propagation**: AWS X-Ray propagator for AWS service integration

### Container vs Zip Deployment
- **Containers**: Better dependency management, consistent environments, larger size limits
- **Zip**: Faster cold starts, simpler for small functions
- **Choice**: Container chosen for complex dependencies (OTel) and interview demonstration

### CI/CD Best Practices
- **OIDC over access keys**: Short-lived credentials, better security posture
- **Smoke tests**: Catch deployment issues before they reach production
- **Image tagging**: Use commit SHA for traceability, `latest` for convenience
- **Rollback strategy**: Could use Lambda aliases and weighted traffic shifting

### Production Enhancements
- **Blue-Green Deployments**: Use Lambda aliases and versions
- **Canary Releases**: Gradually shift traffic to new version
- **Integration Tests**: More comprehensive test suite beyond smoke tests
- **Performance Testing**: Load testing to determine concurrency limits
- **Error Budgets**: SLOs and alerting based on error rates

### Cost Optimization
- **Image size**: Multi-stage build reduces image size
- **X-Ray sampling**: Sample 10% of requests to reduce costs
- **Lambda memory**: Right-size memory based on performance data
- **Reserved concurrency**: Set limits to prevent runaway costs

## Resources

- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [AWS Distro for OpenTelemetry](https://aws-otel.github.io/)
- [AWS X-Ray Developer Guide](https://docs.aws.amazon.com/xray/latest/devguide/)

## License

This is interview preparation code. Use freely for learning and demonstration purposes.
# Test OIDC
