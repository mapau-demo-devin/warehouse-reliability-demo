# Warehouse Reliability Notification Service

A web notification service designed for large consumer goods companies (like PepsiCo) to notify warehouse staff when critical supply chain systems experience downtime.

## Deployment Options

This service supports two deployment modes:

1. **AWS Lambda (Recommended)** - Serverless deployment with automatic scaling
   - See [LAMBDA_DEPLOYMENT.md](LAMBDA_DEPLOYMENT.md) for complete deployment guide
   - Uses DynamoDB for alert storage
   - Deployed via AWS SAM
   - Pay-per-use pricing (~$1-2/month for typical usage)

2. **On-Premise Flask** - Traditional server deployment
   - See instructions below for local/on-premise setup
   - Uses SQLite for alert storage
   - Requires server maintenance

## Overview

This service provides real-time notifications to warehouse operations teams when backend systems like the Warehouse Management System (WMS), ERP, or Inventory Service go down. It helps reduce downtime and improve issue response time by immediately alerting the right people through email or SMS.

## Features

- **REST API**: Simple POST endpoint for sending notifications
- **Multi-channel Support**: Send alerts via Email (AWS SES) or SMS (Twilio)
- **System Monitoring**: Track alerts for WMS, ERP, and InventoryService
- **Severity Levels**: Categorize alerts as critical, warning, or info
- **Alert Logging**: Store all alert metadata (SQLite for Flask, DynamoDB for Lambda)
- **Error Handling**: Comprehensive logging and error handling
- **Serverless Ready**: Full AWS Lambda implementation available

## On-Premise Flask Deployment

### Requirements

- Python 3.8+
- pip (Python package manager)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd warehouse-reliability-demo
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables (optional):

Create a `.env` file in the project root:
```bash
# AWS SES Configuration (optional - defaults to mock mode)
AWS_SES_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
SES_SENDER_EMAIL=alerts@your-company.com

# Twilio Configuration (optional - defaults to mock mode)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Server Configuration
PORT=5000
```

**Note**: If AWS or Twilio credentials are not provided, the service will run in mock mode and log notifications to the console instead of actually sending them.

### Running the Service

Start the Flask server:
```bash
python app.py
```

The service will be available at `http://localhost:5000`

## API Endpoints

### POST /notify

Send a notification to warehouse staff.

**Request Body**:
```json
{
  "channel": "email",
  "recipient": "ops-manager@warehouse.com",
  "message": "WMS database connection lost. Immediate attention required.",
  "system": "WMS",
  "severity": "critical"
}
```

**Parameters**:
- `channel` (string, required): Notification channel - `"email"` or `"sms"`
- `recipient` (string, required): Email address or phone number (E.164 format for SMS, e.g., +12345678900)
- `message` (string, required): Alert message text
- `system` (string, required): System name - `"WMS"`, `"ERP"`, or `"InventoryService"`
- `severity` (string, required): Alert severity - `"critical"`, `"warning"`, or `"info"`

**Success Response** (200 OK):
```json
{
  "status": "success",
  "message": "Email sent (mocked)",
  "channel": "email",
  "recipient": "ops-manager@warehouse.com",
  "system": "WMS",
  "severity": "critical",
  "timestamp": "2025-10-24T10:30:45.123456"
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": "Missing required fields: channel, recipient"
}
```

**Error Response** (500 Internal Server Error):
```json
{
  "status": "error",
  "message": "Failed to send notification",
  "channel": "email",
  "recipient": "ops-manager@warehouse.com"
}
```

### GET /health

Check service health status.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "Warehouse Reliability Notification Service",
  "timestamp": "2025-10-24T10:30:45.123456"
}
```

### GET /alerts

Retrieve alert history from the database.

**Query Parameters**:
- `limit` (integer, optional): Maximum number of alerts to return (default: 100)
- `system` (string, optional): Filter by system name (WMS, ERP, InventoryService)
- `severity` (string, optional): Filter by severity level (critical, warning, info)

**Response** (200 OK):
```json
{
  "count": 2,
  "alerts": [
    {
      "id": 1,
      "timestamp": "2025-10-24T10:30:45.123456",
      "channel": "email",
      "recipient": "ops-manager@warehouse.com",
      "message": "WMS database connection lost",
      "system": "WMS",
      "severity": "critical",
      "status": "sent",
      "error_message": null
    }
  ]
}
```

## Usage Examples

### Using curl

**Send a critical email alert**:
```bash
curl -X POST http://localhost:5000/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "recipient": "ops-manager@warehouse.com",
    "message": "WMS database connection lost. Immediate attention required.",
    "system": "WMS",
    "severity": "critical"
  }'
```

**Send a warning SMS alert**:
```bash
curl -X POST http://localhost:5000/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "sms",
    "recipient": "+12345678900",
    "message": "ERP system response time degraded. Please investigate.",
    "system": "ERP",
    "severity": "warning"
  }'
```

**Send an info email alert**:
```bash
curl -X POST http://localhost:5000/notify \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "recipient": "inventory-team@warehouse.com",
    "message": "Inventory sync completed successfully.",
    "system": "InventoryService",
    "severity": "info"
  }'
```

**Check service health**:
```bash
curl http://localhost:5000/health
```

**Get recent alerts**:
```bash
curl http://localhost:5000/alerts?limit=10
```

**Get critical alerts for WMS**:
```bash
curl "http://localhost:5000/alerts?system=WMS&severity=critical&limit=50"
```

### Using Postman

1. Create a new POST request to `http://localhost:5000/notify`
2. Set Headers: `Content-Type: application/json`
3. Set Body (raw JSON):
```json
{
  "channel": "email",
  "recipient": "ops-manager@warehouse.com",
  "message": "WMS database connection lost. Immediate attention required.",
  "system": "WMS",
  "severity": "critical"
}
```
4. Click Send

### Python Example

```python
import requests

def send_alert(channel, recipient, message, system, severity):
    url = "http://localhost:5000/notify"
    payload = {
        "channel": channel,
        "recipient": recipient,
        "message": message,
        "system": system,
        "severity": severity
    }
    
    response = requests.post(url, json=payload)
    return response.json()

result = send_alert(
    channel="email",
    recipient="ops-manager@warehouse.com",
    message="WMS database connection lost",
    system="WMS",
    severity="critical"
)
print(result)
```

## Database

The service uses SQLite to store alert metadata. The database file (`alerts.db`) is created automatically on first run.

**Schema**:
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    message TEXT NOT NULL,
    system TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT
);
```

## Testing

Run the test suite:
```bash
pytest test_app.py -v
```

## Architecture

This service supports two deployment architectures:

**On-Premise (Flask)**:
- Flask web server
- SQLite database
- Direct AWS SES and Twilio API calls
- Manual scaling and maintenance

**Serverless (AWS Lambda)**:
- AWS Lambda function
- API Gateway for REST endpoint
- DynamoDB for alert storage
- Automatic scaling and high availability
- See [LAMBDA_DEPLOYMENT.md](LAMBDA_DEPLOYMENT.md) for deployment instructions

## Use Case

**Scenario**: A large consumer goods company operates multiple warehouses with critical backend systems:
- **WMS (Warehouse Management System)**: Manages inventory, picking, packing, shipping
- **ERP (Enterprise Resource Planning)**: Handles orders, procurement, financials
- **InventoryService**: Real-time inventory tracking and synchronization

When any of these systems experience downtime, warehouse operations can grind to a halt, costing thousands of dollars per minute. This notification service ensures that:

1. Operations managers receive immediate email alerts
2. On-call engineers get SMS notifications
3. All alerts are logged for post-incident analysis
4. Response times are minimized through instant notification

## Logging

The service logs all activities to the console with timestamps. Log levels:
- **INFO**: Successful operations, notifications sent
- **WARNING**: Non-critical issues, mock mode usage
- **ERROR**: Failed notifications, database errors

## Security Considerations

- Store credentials in environment variables, never in code
- Use `.env` file for local development (add to `.gitignore`)
- Implement authentication/authorization for production use
- Use HTTPS in production
- Rotate AWS and Twilio credentials regularly
- Implement rate limiting to prevent abuse

## Production Deployment

For production deployment:

1. Set up proper AWS SES and Twilio accounts
2. Configure environment variables with real credentials
3. Use a production WSGI server (e.g., Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
4. Set up reverse proxy (nginx) for SSL/TLS
5. Implement authentication middleware
6. Configure monitoring and alerting
7. Set up log aggregation

## License

MIT

## Support

For issues or questions, please contact the warehouse operations team.
