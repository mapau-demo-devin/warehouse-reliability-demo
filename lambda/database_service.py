import os
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'warehouse-alerts')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)


def log_alert(channel: str, recipient: str, message: str, system: str, 
              severity: str, status: str, error_message: Optional[str] = None) -> bool:
    """Log alert to DynamoDB"""
    try:
        alert_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        item = {
            'id': alert_id,
            'timestamp': timestamp,
            'channel': channel,
            'recipient': recipient,
            'message': message,
            'system': system,
            'severity': severity,
            'status': status
        }
        
        if error_message:
            item['error_message'] = error_message
        
        table.put_item(Item=item)
        logger.info(f"Alert logged: {channel} to {recipient} - {status}")
        return True
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return False
    except Exception as e:
        logger.error(f"Failed to log alert to DynamoDB: {str(e)}")
        return False


def get_alerts(limit: int = 100, system_filter: Optional[str] = None, 
               severity_filter: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve alerts from DynamoDB with optional filtering"""
    try:
        scan_kwargs = {
            'Limit': limit
        }
        
        filter_expressions = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        if system_filter:
            filter_expressions.append('#sys = :system')
            expression_attribute_names['#sys'] = 'system'
            expression_attribute_values[':system'] = system_filter
        
        if severity_filter:
            filter_expressions.append('severity = :severity')
            expression_attribute_values[':severity'] = severity_filter
        
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeNames'] = expression_attribute_names
            scan_kwargs['ExpressionAttributeValues'] = expression_attribute_values
        
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        alerts = []
        for item in items:
            alert = {
                'id': item.get('id'),
                'timestamp': item.get('timestamp'),
                'channel': item.get('channel'),
                'recipient': item.get('recipient'),
                'message': item.get('message'),
                'system': item.get('system'),
                'severity': item.get('severity'),
                'status': item.get('status'),
                'error_message': item.get('error_message')
            }
            alerts.append(alert)
        
        return {
            'count': len(alerts),
            'alerts': alerts
        }
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return {'count': 0, 'alerts': [], 'error': str(e)}
    except Exception as e:
        logger.error(f"Failed to fetch alerts from DynamoDB: {str(e)}")
        return {'count': 0, 'alerts': [], 'error': str(e)}
