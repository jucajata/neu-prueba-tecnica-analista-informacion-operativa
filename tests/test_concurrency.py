from concurrent.futures import ThreadPoolExecutor


def test_more_requests_than_threads_and_connections(real_pool_client):
    """Más peticiones simultáneas que hilos (40) y conexiones (10) no deben bloquear la API."""

    def calculate(_: int) -> int:
        response = real_pool_client.post(
            "/calculate-invoice", json={"service_id": 2256, "month": "2023-09"}
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=60) as executor:
        statuses = list(executor.map(calculate, range(240)))

    assert set(statuses) == {200}


def test_dead_idle_connection_does_not_fail_the_next_request(real_pool_client, conn):
    with real_pool_client.app.state.pool.connection() as pooled:
        backend_pid = pooled.info.backend_pid
    conn.execute("SELECT pg_terminate_backend(%s)", (backend_pid,))

    response = real_pool_client.get("/client-statistics/2256?month=2023-09")

    assert response.status_code == 200
