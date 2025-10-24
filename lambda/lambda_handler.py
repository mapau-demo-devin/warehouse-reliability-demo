import json
import logging
from datetime import datetime
from typing import Dict, Any
from notification_service import send_email, send_sms
from database_service import log_alert, get_alerts

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for API Gateway proxy integration"""
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', ''))
    path = event.get('path', event.get('rawPath', ''))
    
    if path.startswith('/prod/'):
        path = path[5:]
    elif path.startswith('/'):
        path = path
    
    if path == '/health' and http_method == 'GET':
        return health_handler(event, context)
    elif path == '/notify' and http_method == 'POST':
        return notify_handler(event, context)
    elif path == '/alerts' and http_method == 'GET':
        return alerts_handler(event, context)
    else:
        return create_response(404, {'error': 'Not found'})


def notify_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /notify endpoint"""
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            data = json.loads(body)
        else:
            data = body
        
        required_fields = ['channel', 'recipient', 'message', 'system', 'severity']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return create_response(400, {
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            })
        
        channel = data['channel'].lower()
        recipient = data['recipient']
        message = data['message']
        system = data['system']
        severity = data['severity'].lower()
        
        if channel not in ['email', 'sms']:
            return create_response(400, {
                'error': "Invalid channel. Must be 'email' or 'sms'"
            })
        
        if system not in ['WMS', 'ERP', 'InventoryService']:
            return create_response(400, {
                'error': "Invalid system. Must be 'WMS', 'ERP', or 'InventoryService'"
            })
        
        if severity not in ['critical', 'warning', 'info']:
            return create_response(400, {
                'error': "Invalid severity. Must be 'critical', 'warning', or 'info'"
            })
        
        logger.info(f"Processing notification: {channel} to {recipient} for {system} ({severity})")
        
        if channel == 'email':
            result = send_email(recipient, message, system, severity)
        else:
            result = send_sms(recipient, message, system, severity)
        
        if result['success']:
            log_alert(channel, recipient, message, system, severity, 'sent')
            return create_response(200, {
                'status': 'success',
                'message': result['message'],
                'channel': channel,
                'recipient': recipient,
                'system': system,
                'severity': severity,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            log_alert(channel, recipient, message, system, severity, 'failed', result['message'])
            return create_response(500, {
                'status': 'error',
                'message': result['message'],
                'channel': channel,
                'recipient': recipient
            })
            
    except json.JSONDecodeError:
        return create_response(400, {'error': 'Invalid JSON payload'})
    except Exception as e:
        logger.error(f"Unexpected error in /notify endpoint: {str(e)}")
        return create_response(500, {'error': f'Internal server error: {str(e)}'})


def health_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /health endpoint"""
    return create_response(200, {
        'status': 'healthy',
        'service': 'Warehouse Reliability Notification Service',
        'timestamp': datetime.utcnow().isoformat()
    })


def alerts_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /alerts endpoint"""
    try:
        query_params = event.get('queryStringParameters') or {}
        
        limit = int(query_params.get('limit', 100))
        system_filter = query_params.get('system')
        severity_filter = query_params.get('severity')
        
        result = get_alerts(limit, system_filter, severity_filter)
        
        if 'error' in result:
            return create_response(500, {
                'error': f"Failed to fetch alerts: {result['error']}"
            })
        
        return create_response(200, result)
        
    except ValueError:
        return create_response(400, {'error': 'Invalid limit parameter'})
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}")
        return create_response(500, {'error': f'Failed to fetch alerts: {str(e)}'})


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create API Gateway proxy response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body)
    }
