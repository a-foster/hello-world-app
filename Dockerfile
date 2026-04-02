# Dockerfile for AWS Lambda Python Container

FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY src/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application code
COPY src/app.py ${LAMBDA_TASK_ROOT}/

# Set environment variables for OpenTelemetry
ENV PYTHONUNBUFFERED=1
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

# Lambda handler
CMD ["app.handler"]
