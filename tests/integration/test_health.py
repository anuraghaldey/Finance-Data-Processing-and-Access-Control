"""Integration tests for health check endpoint."""


class TestHealth:
    def test_health_check(self, client, db):
        response = client.get('/api/v1/health')
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert 'services' in data
        assert 'database' in data['services']
