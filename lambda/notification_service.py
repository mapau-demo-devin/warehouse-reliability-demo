import os
import logging
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_SES_REGION = os.getenv('AWS_SES_REGION', 'us-east-1')
SES_SENDER_EMAIL = os.getenv('SES_SENDER_EMAIL', 'alerts@warehouse-ops.com')

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')


def send_email(recipient: str, message: str, system: str, severity: str) -> Dict[str, Any]:
    """Send email notification via AWS SES"""
    try:
        ses_client = boto3.client('ses', region_name=AWS_SES_REGION)
        
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
    """Send SMS notification via Twilio"""
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
