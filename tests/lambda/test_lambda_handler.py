import pytest
import json
import os
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

from lambda_handler import lambda_handler, notify_handler, health_handler, alerts_handler, create_response


@pytest.fixture
def mock_notification_service():
    with patch('lambda_handler.send_email') as mock_email, \
         patch('lambda_handler.send_sms') as mock_sms:
        mock_email.return_value = {'success': True, 'message': 'Email sent', 'message_id': 'test-id'}
        mock_sms.return_value = {'success': True, 'message': 'SMS sent', 'message_id': 'test-sms-id'}
        yield mock_email, mock_sms


@pytest.fixture
def mock_database_service():
    with patch('lambda_handler.log_alert') as mock_log, \
         patch('lambda_handler.get_alerts') as mock_get:
        mock_log.return_value = True
        mock_get.return_value = {'count': 0, 'alerts': []}
        yield mock_log, mock_get


def test_health_endpoint():
    event = {
        'httpMethod': 'GET',
        'path': '/health',
        'queryStringParameters': None
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'healthy'
    assert 'timestamp' in body


def test_notify_email_success(mock_notification_service, mock_database_service):
    mock_email, mock_sms = mock_notification_service
    mock_log, mock_get = mock_database_service
    
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'email',
            'recipient': 'test@example.com',
            'message': 'Test alert',
            'system': 'WMS',
            'severity': 'critical'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'success'
    assert body['channel'] == 'email'
    assert body['system'] == 'WMS'
    assert body['severity'] == 'critical'
    
    mock_email.assert_called_once()
    mock_log.assert_called_once()


def test_notify_sms_success(mock_notification_service, mock_database_service):
    mock_email, mock_sms = mock_notification_service
    mock_log, mock_get = mock_database_service
    
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'sms',
            'recipient': '+12345678900',
            'message': 'Test SMS',
            'system': 'ERP',
            'severity': 'warning'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'success'
    assert body['channel'] == 'sms'
    
    mock_sms.assert_called_once()
    mock_log.assert_called_once()


def test_notify_missing_fields():
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'email',
            'recipient': 'test@example.com'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'error' in body
    assert 'Missing required fields' in body['error']


def test_notify_invalid_channel():
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'telegram',
            'recipient': 'test@example.com',
            'message': 'Test',
            'system': 'WMS',
            'severity': 'critical'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Invalid channel' in body['error']


def test_notify_invalid_system():
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'email',
            'recipient': 'test@example.com',
            'message': 'Test',
            'system': 'InvalidSystem',
            'severity': 'critical'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Invalid system' in body['error']


def test_notify_invalid_severity():
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'email',
            'recipient': 'test@example.com',
            'message': 'Test',
            'system': 'WMS',
            'severity': 'urgent'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Invalid severity' in body['error']


def test_notify_invalid_json():
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': 'not valid json'
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'error' in body


def test_alerts_endpoint_empty(mock_database_service):
    mock_log, mock_get = mock_database_service
    
    event = {
        'httpMethod': 'GET',
        'path': '/alerts',
        'queryStringParameters': None
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['count'] == 0
    assert body['alerts'] == []


def test_alerts_with_filters(mock_database_service):
    mock_log, mock_get = mock_database_service
    mock_get.return_value = {
        'count': 1,
        'alerts': [{
            'id': 'test-id',
            'timestamp': '2025-10-24T10:00:00',
            'channel': 'email',
            'recipient': 'test@example.com',
            'message': 'Test',
            'system': 'WMS',
            'severity': 'critical',
            'status': 'sent',
            'error_message': None
        }]
    }
    
    event = {
        'httpMethod': 'GET',
        'path': '/alerts',
        'queryStringParameters': {
            'system': 'WMS',
            'severity': 'critical',
            'limit': '10'
        }
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['count'] == 1
    mock_get.assert_called_once_with(10, 'WMS', 'critical')


def test_not_found_endpoint():
    event = {
        'httpMethod': 'GET',
        'path': '/unknown',
        'queryStringParameters': None
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert 'error' in body


def test_create_response():
    response = create_response(200, {'test': 'data'})
    
    assert response['statusCode'] == 200
    assert 'Content-Type' in response['headers']
    assert response['headers']['Content-Type'] == 'application/json'
    assert 'Access-Control-Allow-Origin' in response['headers']
    body = json.loads(response['body'])
    assert body['test'] == 'data'


def test_notify_failed_notification(mock_notification_service, mock_database_service):
    mock_email, mock_sms = mock_notification_service
    mock_log, mock_get = mock_database_service
    
    mock_email.return_value = {'success': False, 'message': 'SES error'}
    
    event = {
        'httpMethod': 'POST',
        'path': '/notify',
        'body': json.dumps({
            'channel': 'email',
            'recipient': 'test@example.com',
            'message': 'Test',
            'system': 'WMS',
            'severity': 'critical'
        })
    }
    context = {}
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 500
    body = json.loads(response['body'])
    assert body['status'] == 'error'
    assert 'SES error' in body['message']
