# AWS Lambda Deployment Guide

This guide explains how to deploy the Warehouse Reliability Notification Service to AWS Lambda using AWS SAM.

## Prerequisites

- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.11 or later
- AWS account with appropriate permissions

## Installation

### Install AWS SAM CLI

**macOS:**
```bash
brew install aws-sam-cli
```

**Linux:**
```bash
pip install aws-sam-cli
```

**Windows:**
Download from: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

### Verify Installation
```bash
sam --version
aws --version
```

## Project Structure

```
warehouse-reliability-demo/
├── lambda/                          # Lambda function code
│   ├── lambda_handler.py           # Main handler
│   ├── notification_service.py     # Email/SMS logic
│   ├── database_service.py         # DynamoDB operations
│   └── requirements.txt            # Lambda dependencies
├── tests/
│   └── lambda/
│       └── test_lambda_handler.py  # Unit tests
├── template.yaml                    # SAM template
├── app.py                          # Original Flask app (kept for reference)
└── README.md
```

## Configuration

### Environment Variables

The SAM template uses parameters for configuration. You can set these during deployment or create a `samconfig.toml` file:

```toml
version = 0.1
[default]
[default.deploy]
[default.deploy.parameters]
stack_name = "warehouse-notification-service"
s3_bucket = "YOUR_S3_BUCKET_NAME"
s3_prefix = "warehouse-notification"
region = "us-east-1"
capabilities = "CAPABILITY_IAM"
parameter_overrides = "SenderEmail=alerts@your-domain.com TwilioAccountSid=YOUR_SID TwilioAuthToken=YOUR_TOKEN TwilioPhoneNumber=+1234567890"
```

### AWS SES Setup

Before deploying, ensure AWS SES is configured:

1. Verify sender email address in SES console
2. If in sandbox mode, verify recipient emails too
3. Request production access for unrestricted sending

```bash
aws ses verify-email-identity --email-address alerts@your-domain.com
```

## Deployment Steps

### 1. Build the Application

```bash
sam build
```

This command:
- Installs dependencies from `lambda/requirements.txt`
- Prepares Lambda deployment package
- Validates SAM template

### 2. Deploy to AWS

**First-time deployment (guided):**
```bash
sam deploy --guided
```

This will prompt you for:
- Stack name (e.g., `warehouse-notification-service`)
- AWS Region (e.g., `us-east-1`)
- Parameter values (SenderEmail, Twilio credentials)
- Confirmation before deployment

**Subsequent deployments:**
```bash
sam deploy
```

### 3. Get API Endpoint

After deployment, SAM outputs the API Gateway URL:

```
Outputs
-----------------------------------------------------------------
Key                 NotificationApiUrl
Description         API Gateway endpoint URL
Value               https://xxxxx.execute-api.us-east-1.amazonaws.com/prod
```

Save this URL for testing.

## Testing

### Local Testing with SAM

**Start local API:**
```bash
sam local start-api
```

This starts a local server at `http://127.0.0.1:3000`

**Test endpoints locally:**
```bash
# Health check
curl http://127.0.0.1:3000/health

# Send notification
curl -X POST http://127.0.0.1:3000/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "recipient": "test@example.com",
    "message": "Test alert",
    "system": "WMS",
    "severity": "critical"
  }'

# Get alerts
curl http://127.0.0.1:3000/alerts?limit=10
```

**Note:** Local testing uses your AWS credentials, so DynamoDB and SES calls will be real.

### Unit Tests

Run unit tests:
```bash
cd tests/lambda
pytest test_lambda_handler.py -v
```

### Testing Deployed API

Replace `YOUR_API_URL` with your actual API Gateway URL:

```bash
API_URL="https://xxxxx.execute-api.us-east-1.amazonaws.com/prod"

# Health check
curl $API_URL/health

# Send email notification
curl -X POST $API_URL/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "recipient": "ops-manager@warehouse.com",
    "message": "WMS database connection lost",
    "system": "WMS",
    "severity": "critical"
  }'

# Send SMS notification
curl -X POST $API_URL/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "sms",
    "recipient": "+12345678900",
    "message": "ERP system degraded",
    "system": "ERP",
    "severity": "warning"
  }'

# Get recent alerts
curl "$API_URL/alerts?limit=10"

# Filter by system
curl "$API_URL/alerts?system=WMS&severity=critical"
```

## Monitoring

### CloudWatch Logs

View Lambda logs:
```bash
sam logs -n NotificationFunction --stack-name warehouse-notification-service --tail
```

Or in AWS Console:
1. Go to CloudWatch → Log groups
2. Find `/aws/lambda/warehouse-notification-service-NotificationFunction-xxxxx`
3. View log streams

### CloudWatch Metrics

Monitor in AWS Console:
- Lambda invocations, errors, duration
- DynamoDB read/write capacity
- API Gateway requests, latency, errors

### Set Up Alarms

Create CloudWatch alarms for:
- Lambda errors > threshold
- Lambda duration approaching timeout
- DynamoDB throttling
- API Gateway 5xx errors

## Updating the Application

### Update Code

1. Modify code in `lambda/` directory
2. Run tests: `pytest tests/lambda/`
3. Build: `sam build`
4. Deploy: `sam deploy`

### Update Infrastructure

1. Modify `template.yaml`
2. Build: `sam build`
3. Deploy: `sam deploy`

SAM will show a changeset before applying updates.

## Rollback

If deployment fails or issues occur:

```bash
aws cloudformation delete-stack --stack-name warehouse-notification-service
```

Then redeploy the previous version.

## Cost Optimization

### Current Configuration
- Lambda: 512MB, 30s timeout
- DynamoDB: On-demand pricing
- API Gateway: HTTP API (cheaper than REST API)

### Estimated Monthly Costs (1000 notifications/day)
- Lambda: ~$0.25
- DynamoDB: ~$0.40
- API Gateway: ~$0.03
- SES: ~$0.10
- CloudWatch: ~$0.50
- **Total: ~$1.28/month**

### Optimization Tips
1. Use Lambda ARM (Graviton2) for 20% savings
2. Adjust Lambda memory based on actual usage
3. Use DynamoDB reserved capacity for predictable workloads
4. Set CloudWatch Logs retention policy (e.g., 7 days)

## Troubleshooting

### Build Fails

**Error:** `Build Failed Error: PythonPipBuilder:ResolveDependencies`

**Solution:** Ensure Python 3.11 is installed and active:
```bash
python3 --version
pip3 install -r lambda/requirements.txt
```

### Deployment Fails - S3 Bucket

**Error:** `S3 Bucket does not exist`

**Solution:** Create S3 bucket for SAM artifacts:
```bash
aws s3 mb s3://your-sam-deployment-bucket --region us-east-1
```

Then update `samconfig.toml` with bucket name.

### Lambda Timeout

**Error:** Task timed out after 30.00 seconds

**Solution:** Increase timeout in `template.yaml`:
```yaml
Globals:
  Function:
    Timeout: 60
```

### DynamoDB Access Denied

**Error:** `User is not authorized to perform: dynamodb:PutItem`

**Solution:** Verify IAM role has DynamoDB permissions. Check `template.yaml` policies.

### SES Email Not Sending

**Error:** `Email address is not verified`

**Solution:** 
1. Verify sender email in SES console
2. If in sandbox, verify recipient emails
3. Request production access

### CORS Issues

**Error:** `No 'Access-Control-Allow-Origin' header`

**Solution:** CORS is configured in `template.yaml`. Verify:
```yaml
CorsConfiguration:
  AllowOrigins:
    - '*'
```

## Cleanup

To delete all AWS resources:

```bash
sam delete --stack-name warehouse-notification-service
```

This removes:
- Lambda function
- API Gateway
- DynamoDB table (and all data)
- IAM roles
- CloudWatch logs

**Warning:** This is irreversible. Export DynamoDB data first if needed.

## Migration from Flask

### Differences from Original Flask App

| Feature | Flask (Original) | Lambda (New) |
|---------|-----------------|--------------|
| Database | SQLite | DynamoDB |
| Server | Flask dev server | API Gateway + Lambda |
| Scaling | Manual | Automatic |
| Cost | Fixed (server) | Pay-per-use |
| Deployment | Manual | SAM automated |
| Monitoring | Custom | CloudWatch built-in |

### Data Migration

If you have existing SQLite data to migrate:

1. Export SQLite data:
```python
import sqlite3
import json

conn = sqlite3.connect('alerts.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM alerts')
rows = cursor.fetchall()

with open('alerts_export.json', 'w') as f:
    json.dump(rows, f)
```

2. Import to DynamoDB:
```python
import boto3
import json
import uuid

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('warehouse-alerts')

with open('alerts_export.json', 'r') as f:
    alerts = json.load(f)

for alert in alerts:
    table.put_item(Item={
        'id': str(uuid.uuid4()),
        'timestamp': alert[1],
        'channel': alert[2],
        'recipient': alert[3],
        'message': alert[4],
        'system': alert[5],
        'severity': alert[6],
        'status': alert[7],
        'error_message': alert[8] if len(alert) > 8 else None
    })
```

## Security Best Practices

1. **Use Secrets Manager** for sensitive credentials:
```bash
aws secretsmanager create-secret \
  --name warehouse-notification/twilio \
  --secret-string '{"account_sid":"xxx","auth_token":"yyy"}'
```

2. **Enable API Gateway authentication:**
   - Add API keys
   - Use AWS IAM authorization
   - Implement Cognito user pools

3. **Restrict IAM permissions:**
   - Use least privilege principle
   - Separate dev/prod environments
   - Enable CloudTrail logging

4. **Enable DynamoDB encryption:**
   - Already enabled by default
   - Use customer-managed KMS keys for additional control

5. **Set up VPC** (if needed):
   - Place Lambda in VPC for private resources
   - Use VPC endpoints for AWS services

## Support

For issues or questions:
- Check CloudWatch Logs for errors
- Review SAM documentation: https://docs.aws.amazon.com/serverless-application-model/
- AWS Lambda docs: https://docs.aws.amazon.com/lambda/
- DynamoDB docs: https://docs.aws.amazon.com/dynamodb/

## Next Steps

After successful deployment:

1. ✅ Test all endpoints thoroughly
2. ✅ Set up CloudWatch alarms
3. ✅ Configure API authentication
4. ✅ Update client applications with new API URL
5. ✅ Monitor costs and performance
6. ✅ Document any custom configurations
7. ✅ Set up CI/CD pipeline (optional)
