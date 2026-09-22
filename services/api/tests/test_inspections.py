def test_create_and_reopen_inspection(client):
    create_response = client.post(
        "/api/v1/inspections",
        json={
            "product_name": "Sample Biscuit Pack",
            "product_identifier": "DEMO-001",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["product_name"] == "Sample Biscuit Pack"
    assert created["product_identifier"] == "DEMO-001"
    assert created["status"] == "draft"

    get_response = client.get(f"/api/v1/inspections/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


def test_list_inspections_uses_persisted_records(client):
    first = client.post(
        "/api/v1/inspections",
        json={"product_name": "First Product"},
    )
    second = client.post(
        "/api/v1/inspections",
        json={"product_name": "Second Product"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get("/api/v1/inspections")

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 2
    assert {item["product_name"] for item in records} == {
        "First Product",
        "Second Product",
    }


def test_missing_inspection_returns_404(client):
    response = client.get("/api/v1/inspections/not-a-real-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "Inspection not found"}
