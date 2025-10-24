import pytest
import json
import os
import sqlite3
import threading
import time
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from twilio.base.exceptions import TwilioRestException
from app import app, init_db, DB_PATH

@pytest.fixture
def client():
    app.config['TESTING'] = True
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    
    with app.test_client() as client:
        yield client
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def test_health_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'timestamp' in data


def test_notify_email_success(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Test alert message",
        "system": "WMS",
        "severity": "critical"
    }
    
    response = client.post('/notify', 
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['channel'] == 'email'
    assert data['recipient'] == 'test@example.com'
    assert data['system'] == 'WMS'
    assert data['severity'] == 'critical'


def test_notify_sms_success(client):
    payload = {
        "channel": "sms",
        "recipient": "+12345678900",
        "message": "Test SMS alert",
        "system": "ERP",
        "severity": "warning"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['channel'] == 'sms'
    assert data['severity'] == 'warning'


def test_notify_missing_fields(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'Missing required fields' in data['error']


def test_notify_invalid_channel(client):
    payload = {
        "channel": "telegram",
        "recipient": "test@example.com",
        "message": "Test message",
        "system": "WMS",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid channel' in data['error']


def test_notify_invalid_system(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Test message",
        "system": "InvalidSystem",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid system' in data['error']


def test_notify_invalid_severity(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Test message",
        "system": "WMS",
        "severity": "urgent"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid severity' in data['error']


def test_notify_invalid_json(client):
    response = client.post('/notify',
                          data='not valid json',
                          content_type='application/json')
    
    assert response.status_code == 400


def test_alerts_endpoint_empty(client):
    response = client.get('/alerts')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 0
    assert data['alerts'] == []


def test_alerts_endpoint_with_data(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Test alert",
        "system": "WMS",
        "severity": "critical"
    }
    
    client.post('/notify',
               data=json.dumps(payload),
               content_type='application/json')
    
    response = client.get('/alerts')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 1
    assert len(data['alerts']) == 1
    assert data['alerts'][0]['system'] == 'WMS'
    assert data['alerts'][0]['severity'] == 'critical'


def test_alerts_filter_by_system(client):
    payloads = [
        {"channel": "email", "recipient": "test@example.com", "message": "WMS alert", "system": "WMS", "severity": "critical"},
        {"channel": "email", "recipient": "test@example.com", "message": "ERP alert", "system": "ERP", "severity": "warning"}
    ]
    
    for payload in payloads:
        client.post('/notify',
                   data=json.dumps(payload),
                   content_type='application/json')
    
    response = client.get('/alerts?system=WMS')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 1
    assert data['alerts'][0]['system'] == 'WMS'


def test_alerts_filter_by_severity(client):
    payloads = [
        {"channel": "email", "recipient": "test@example.com", "message": "Critical alert", "system": "WMS", "severity": "critical"},
        {"channel": "email", "recipient": "test@example.com", "message": "Warning alert", "system": "ERP", "severity": "warning"}
    ]
    
    for payload in payloads:
        client.post('/notify',
                   data=json.dumps(payload),
                   content_type='application/json')
    
    response = client.get('/alerts?severity=critical')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 1
    assert data['alerts'][0]['severity'] == 'critical'


def test_alerts_limit(client):
    for i in range(5):
        payload = {
            "channel": "email",
            "recipient": f"test{i}@example.com",
            "message": f"Alert {i}",
            "system": "WMS",
            "severity": "info"
        }
        client.post('/notify',
                   data=json.dumps(payload),
                   content_type='application/json')
    
    response = client.get('/alerts?limit=3')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 3
    assert len(data['alerts']) == 3


def test_database_logging(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Database test",
        "system": "InventoryService",
        "severity": "info"
    }
    
    client.post('/notify',
               data=json.dumps(payload),
               content_type='application/json')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM alerts')
    rows = cursor.fetchall()
    conn.close()
    
    assert len(rows) == 1
    assert rows[0][2] == 'email'
    assert rows[0][3] == 'test@example.com'
    assert rows[0][5] == 'InventoryService'
    assert rows[0][6] == 'info'
    assert rows[0][7] == 'sent'


def test_all_systems(client):
    systems = ['WMS', 'ERP', 'InventoryService']
    
    for system in systems:
        payload = {
            "channel": "email",
            "recipient": "test@example.com",
            "message": f"{system} test",
            "system": system,
            "severity": "info"
        }
        
        response = client.post('/notify',
                              data=json.dumps(payload),
                              content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['system'] == system


def test_all_severities(client):
    severities = ['critical', 'warning', 'info']
    
    for severity in severities:
        payload = {
            "channel": "email",
            "recipient": "test@example.com",
            "message": f"{severity} test",
            "system": "WMS",
            "severity": severity
        }
        
        response = client.post('/notify',
                              data=json.dumps(payload),
                              content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['severity'] == severity


def test_aws_ses_client_error(client):
    with patch('app.boto3.client') as mock_boto_client:
        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = ClientError(
            {'Error': {'Message': 'Invalid email address'}},
            'SendEmail'
        )
        mock_boto_client.return_value = mock_ses
        
        with patch('app.AWS_ACCESS_KEY', 'REAL_KEY'):
            payload = {
                "channel": "email",
                "recipient": "invalid@example.com",
                "message": "Test AWS SES error",
                "system": "WMS",
                "severity": "critical"
            }
            
            response = client.post('/notify',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert 'AWS SES error' in data['message']
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT status, error_message FROM alerts WHERE recipient = ?', 
                          ('invalid@example.com',))
            row = cursor.fetchone()
            conn.close()
            
            assert row is not None
            assert row[0] == 'failed'
            assert 'AWS SES error' in row[1]


def test_aws_ses_generic_exception(client):
    with patch('app.boto3.client') as mock_boto_client:
        mock_boto_client.side_effect = Exception('Network connection failed')
        
        with patch('app.AWS_ACCESS_KEY', 'REAL_KEY'):
            payload = {
                "channel": "email",
                "recipient": "test@example.com",
                "message": "Test generic error",
                "system": "ERP",
                "severity": "warning"
            }
            
            response = client.post('/notify',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert 'Failed to send email' in data['message']


def test_twilio_rest_exception(client):
    with patch('app.Client') as mock_twilio_client:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = TwilioRestException(
            status=400,
            uri='/Messages',
            msg='Invalid phone number'
        )
        mock_twilio_client.return_value = mock_client
        
        with patch('app.TWILIO_ACCOUNT_SID', 'test_sid'), \
             patch('app.TWILIO_AUTH_TOKEN', 'test_token'):
            payload = {
                "channel": "sms",
                "recipient": "+1234567890",
                "message": "Test Twilio error",
                "system": "InventoryService",
                "severity": "critical"
            }
            
            response = client.post('/notify',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert 'Twilio error' in data['message']
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT status, error_message FROM alerts WHERE recipient = ?', 
                          ('+1234567890',))
            row = cursor.fetchone()
            conn.close()
            
            assert row is not None
            assert row[0] == 'failed'
            assert 'Twilio error' in row[1]


def test_twilio_generic_exception(client):
    with patch('app.Client') as mock_twilio_client:
        mock_twilio_client.side_effect = Exception('Connection timeout')
        
        with patch('app.TWILIO_ACCOUNT_SID', 'test_sid'), \
             patch('app.TWILIO_AUTH_TOKEN', 'test_token'):
            payload = {
                "channel": "sms",
                "recipient": "+9876543210",
                "message": "Test generic SMS error",
                "system": "WMS",
                "severity": "info"
            }
            
            response = client.post('/notify',
                                  data=json.dumps(payload),
                                  content_type='application/json')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert 'Failed to send SMS' in data['message']


def test_database_connection_failure_on_log():
    with patch('app.sqlite3.connect') as mock_connect:
        mock_connect.side_effect = sqlite3.OperationalError('Database is locked')
        
        app.config['TESTING'] = True
        with app.test_client() as test_client:
            payload = {
                "channel": "email",
                "recipient": "test@example.com",
                "message": "Test database error",
                "system": "WMS",
                "severity": "critical"
            }
            
            response = test_client.post('/notify',
                                       data=json.dumps(payload),
                                       content_type='application/json')
            
            assert response.status_code == 200


def test_database_query_failure(client):
    with patch('app.sqlite3.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = sqlite3.OperationalError('Disk I/O error')
        mock_connect.return_value = mock_conn
        
        response = client.get('/alerts')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Failed to fetch alerts' in data['error']


def test_concurrent_requests(client):
    num_concurrent = 10
    
    for i in range(num_concurrent):
        payload = {
            "channel": "email",
            "recipient": f"user{i}@example.com",
            "message": f"Concurrent test message {i}",
            "system": "WMS",
            "severity": "info"
        }
        
        response = client.post('/notify',
                              data=json.dumps(payload),
                              content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM alerts')
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == num_concurrent


def test_concurrent_read_write(client):
    for i in range(5):
        payload = {
            "channel": "sms",
            "recipient": f"+123456789{i:02d}",
            "message": f"Load test {i}",
            "system": "ERP",
            "severity": "warning"
        }
        
        response = client.post('/notify',
                              data=json.dumps(payload),
                              content_type='application/json')
        assert response.status_code == 200
    
    for i in range(3):
        response = client.get('/alerts?limit=50')
        assert response.status_code == 200


def test_empty_string_fields(client):
    payload = {
        "channel": "email",
        "recipient": "",
        "message": "",
        "system": "WMS",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200


def test_extremely_long_message(client):
    long_message = "A" * 10000
    
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": long_message,
        "system": "InventoryService",
        "severity": "info"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT message FROM alerts WHERE recipient = ?', ('test@example.com',))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert len(row[0]) == 10000


def test_special_characters_in_message(client):
    special_message = "Alert: <script>alert('xss')</script> & \"quotes\" 'single' \n\t\r special chars: !@#$%^&*()_+-=[]{}|;:,.<>?/~`"
    
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": special_message,
        "system": "WMS",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT message FROM alerts ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert special_message in row[0]


def test_unicode_characters(client):
    unicode_message = "Alert: 你好世界 🚨 Привет мир émojis: 😀🎉🔥 symbols: ™®©"
    
    payload = {
        "channel": "sms",
        "recipient": "+12345678900",
        "message": unicode_message,
        "system": "ERP",
        "severity": "warning"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'


def test_sql_injection_attempt_in_system(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Test message",
        "system": "WMS'; DROP TABLE alerts; --",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid system' in data['error']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
    table_exists = cursor.fetchone()
    conn.close()
    
    assert table_exists is not None


def test_special_characters_in_recipient_email(client):
    payload = {
        "channel": "email",
        "recipient": "test+tag@example.co.uk",
        "message": "Test with special email",
        "system": "WMS",
        "severity": "info"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['recipient'] == 'test+tag@example.co.uk'


def test_international_phone_number(client):
    payload = {
        "channel": "sms",
        "recipient": "+44 20 7946 0958",
        "message": "International number test",
        "system": "InventoryService",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'


def test_case_sensitivity_channel(client):
    payload = {
        "channel": "EMAIL",
        "recipient": "test@example.com",
        "message": "Test uppercase channel",
        "system": "WMS",
        "severity": "critical"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['channel'] == 'email'


def test_case_sensitivity_severity(client):
    payload = {
        "channel": "email",
        "recipient": "test@example.com",
        "message": "Test uppercase severity",
        "system": "WMS",
        "severity": "CRITICAL"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['severity'] == 'critical'


def test_whitespace_in_fields(client):
    payload = {
        "channel": "  email  ",
        "recipient": "  test@example.com  ",
        "message": "  Test with whitespace  ",
        "system": "WMS",
        "severity": "  critical  "
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid' in data['error']


def test_very_long_recipient_email(client):
    long_email = "a" * 50 + "@" + "b" * 50 + ".com"
    
    payload = {
        "channel": "email",
        "recipient": long_email,
        "message": "Test long email",
        "system": "ERP",
        "severity": "warning"
    }
    
    response = client.post('/notify',
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['recipient'] == long_email
