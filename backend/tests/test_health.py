from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check_returns_ok() -> None:
    # 健康检查用于确认应用已启动，不依赖数据库和外部服务。
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
