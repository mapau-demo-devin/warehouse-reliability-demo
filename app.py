import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = 'alerts.db'

AWS_SES_REGION = os.getenv('AWS_SES_REGION', 'us-east-1')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID', 'MOCK_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'MOCK_SECRET_KEY')
SES_SENDER_EMAIL = os.getenv('SES_SENDER_EMAIL', 'alerts@warehouse-ops.com')

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            channel TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            system TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def log_alert(channel: str, recipient: str, message: str, system: str, 
              severity: str, status: str, error_message: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (timestamp, channel, recipient, message, system, severity, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.utcnow().isoformat(), channel, recipient, message, system, severity, status, error_message))
        conn.commit()
        conn.close()
        logger.info(f"Alert logged: {channel} to {recipient} - {status}")
    except Exception as e:
        logger.error(f"Failed to log alert to database: {str(e)}")


def send_email(recipient: str, message: str, system: str, severity: str) -> Dict[str, Any]:
    try:
        if AWS_ACCESS_KEY == 'MOCK_ACCESS_KEY':
            logger.info(f"MOCK EMAIL: Sending email to {recipient}")
            logger.info(f"Subject: [{severity.upper()}] {system} Alert")
            logger.info(f"Body: {message}")
            return {"success": True, "message": "Email sent (mocked)", "message_id": "mock-message-id"}
        
        ses_client = boto3.client(
            'ses',
            region_name=AWS_SES_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY
        )
        
        subject = f"[{severity.upper()}] {system} Alert"
        body = f"""
Warehouse Operations Alert

System: {system}
Severity: {severity.upper()}
Time: {datetime.utcnow().isoformat()}

Message:
{message}

This is an automated alert from the Warehouse Reliability Notification Service.
"""
        
        response = ses_client.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        logger.info(f"Email sent successfully to {recipient}")
        return {"success": True, "message": "Email sent", "message_id": response['MessageId']}
        
    except ClientError as e:
        error_msg = f"AWS SES error: {e.response['Error']['Message']}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}


def send_sms(recipient: str, message: str, system: str, severity: str) -> Dict[str, Any]:
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.warning("Twilio credentials not configured, using mock mode")
            logger.info(f"MOCK SMS: Sending SMS to {recipient}")
            logger.info(f"Message: [{severity.upper()}] {system}: {message}")
            return {"success": True, "message": "SMS sent (mocked)", "message_id": "mock-sms-id"}
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        sms_body = f"[{severity.upper()}] {system}: {message}"
        
        twilio_message = client.messages.create(
            body=sms_body,
            from_=TWILIO_PHONE_NUMBER,
            to=recipient
        )
        
        logger.info(f"SMS sent successfully to {recipient}")
        return {"success": True, "message": "SMS sent", "message_id": twilio_message.sid}
        
    except TwilioRestException as e:
        error_msg = f"Twilio error: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}
    except Exception as e:
        error_msg = f"Failed to send SMS: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}


@app.route('/notify', methods=['POST'])
def notify():
    try:
        data = request.get_json(force=True, silent=True)
        
        if data is None:
            return jsonify({"error": "Invalid JSON payload"}), 400
        
        required_fields = ['channel', 'recipient', 'message', 'system', 'severity']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
        
        channel = data['channel'].lower()
        recipient = data['recipient']
        message = data['message']
        system = data['system']
        severity = data['severity'].lower()
        
        if channel not in ['email', 'sms']:
            return jsonify({"error": "Invalid channel. Must be 'email' or 'sms'"}), 400
        
        if system not in ['WMS', 'ERP', 'InventoryService']:
            return jsonify({"error": "Invalid system. Must be 'WMS', 'ERP', or 'InventoryService'"}), 400
        
        if severity not in ['critical', 'warning', 'info']:
            return jsonify({"error": "Invalid severity. Must be 'critical', 'warning', or 'info'"}), 400
        
        logger.info(f"Processing notification: {channel} to {recipient} for {system} ({severity})")
        
        if channel == 'email':
            result = send_email(recipient, message, system, severity)
        else:
            result = send_sms(recipient, message, system, severity)
        
        if result['success']:
            log_alert(channel, recipient, message, system, severity, 'sent')
            return jsonify({
                "status": "success",
                "message": result['message'],
                "channel": channel,
                "recipient": recipient,
                "system": system,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        else:
            log_alert(channel, recipient, message, system, severity, 'failed', result['message'])
            return jsonify({
                "status": "error",
                "message": result['message'],
                "channel": channel,
                "recipient": recipient
            }), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in /notify endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "Warehouse Reliability Notification Service",
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@app.route('/alerts', methods=['GET'])
def get_alerts():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        limit = request.args.get('limit', 100, type=int)
        system_filter = request.args.get('system', None)
        severity_filter = request.args.get('severity', None)
        
        query = 'SELECT * FROM alerts WHERE 1=1'
        params = []
        
        if system_filter:
            query += ' AND system = ?'
            params.append(system_filter)
        
        if severity_filter:
            query += ' AND severity = ?'
            params.append(severity_filter)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        alerts = [dict(row) for row in rows]
        conn.close()
        
        return jsonify({
            "count": len(alerts),
            "alerts": alerts
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}")
        return jsonify({"error": f"Failed to fetch alerts: {str(e)}"}), 500


if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
