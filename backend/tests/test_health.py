from fastapi.testclient import TestClient

from app.main import app


def test_健康检查_服务能启动且数据库连通():
    # TestClient 作为上下文管理器会执行 lifespan(含 Tortoise 初始化)
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
