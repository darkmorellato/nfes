import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.gap_detector import auditar_saltos_numeracao
from backend.services.notification_service import gerar_link_whatsapp_alerta, get_whatsapp_alert_numbers
from backend.routers.auth import _sessions
import uuid, datetime

token = str(uuid.uuid4())
_sessions[token] = {'email': 'contasgeraljack@gmail.com', 'perfil': 'admin', 'expires_at': datetime.datetime.now() + datetime.timedelta(hours=1)}
client = TestClient(app)

def test_auditar_saltos_numeracao():
    res = auditar_saltos_numeracao()
    assert res['success'] is True
    assert 'total_empresas_auditadas' in res
    assert 'total_gaps_encontrados' in res
    assert 'empresas' in res

def test_auditoria_gaps_endpoint():
    res = client.get('/api/gestao/auditoria/gaps-numeracao', headers={'X-Session-Token': token})
    assert res.status_code == 200
    data = res.json()
    assert data['success'] is True
    assert 'empresas' in data

def test_whatsapp_helpers():
    nums = get_whatsapp_alert_numbers()
    assert '5519989354849' in nums or len(nums) >= 1
    link = gerar_link_whatsapp_alerta('5519989354849', 'Alerta Teste', 'Mensagem de teste', chave='35260834511185000110550010000005351002907810')
    assert 'api.whatsapp.com/send' in link
    assert '5519989354849' in link
    assert 'Alerta+Teste' in link or 'Alerta%20Teste' in link
