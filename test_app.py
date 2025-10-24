import pytest
import json
import os
import sqlite3
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
