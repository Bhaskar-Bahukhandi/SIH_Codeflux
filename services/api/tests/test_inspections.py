def create_inspection(client, name="Sample Biscuit Pack", identifier="DEMO-001"):
    response = client.post(
        "/api/v1/inspections",
        json={
            "product_name": name,
            "product_identifier": identifier,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_reopen_inspection(client):
    created = create_inspection(client)

    assert created["product_name"] == "Sample Biscuit Pack"
    assert created["product_identifier"] == "DEMO-001"
    assert created["status"] == "draft"
    assert created["submitted_at"] is None

    get_response = client.get(f"/api/v1/inspections/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


def test_list_inspections_uses_persisted_records(client):
    first = create_inspection(client, "First Product", None)
    second = create_inspection(client, "Second Product", None)

    response = client.get("/api/v1/inspections")

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 2
    assert {item["id"] for item in records} == {first["id"], second["id"]}


def test_draft_inspection_can_be_updated(client):
    created = create_inspection(client)

    response = client.patch(
        f"/api/v1/inspections/{created['id']}",
        json={
            "product_name": "Updated Biscuit Pack",
            "product_identifier": "",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["product_name"] == "Updated Biscuit Pack"
    assert updated["product_identifier"] is None
    assert updated["status"] == "draft"


def test_submit_moves_draft_to_pending_review(client):
    created = create_inspection(client)

    response = client.post(f"/api/v1/inspections/{created['id']}/submit")

    assert response.status_code == 200
    submitted = response.json()
    assert submitted["status"] == "pending_review"
    assert submitted["submitted_at"] is not None


def test_submitted_inspection_cannot_be_edited(client):
    created = create_inspection(client)
    submit = client.post(f"/api/v1/inspections/{created['id']}/submit")
    assert submit.status_code == 200

    response = client.patch(
        f"/api/v1/inspections/{created['id']}",
        json={"product_name": "Should Not Apply"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "inspection_not_editable",
            "message": "Only draft inspections can be edited.",
        }
    }


def test_second_submit_is_rejected(client):
    created = create_inspection(client)
    first_submit = client.post(f"/api/v1/inspections/{created['id']}/submit")
    assert first_submit.status_code == 200

    second_submit = client.post(f"/api/v1/inspections/{created['id']}/submit")

    assert second_submit.status_code == 409
    assert second_submit.json()["error"]["code"] == "inspection_not_editable"


def test_missing_inspection_returns_domain_404(client):
    response = client.get("/api/v1/inspections/not-a-real-id")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "inspection_not_found",
            "message": "Inspection not found.",
        }
    }


def test_blank_product_name_is_rejected(client):
    response = client.post(
        "/api/v1/inspections",
        json={"product_name": "   "},
    )

    assert response.status_code == 422
