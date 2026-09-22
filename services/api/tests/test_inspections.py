from app.models.user import UserRole


def create_inspection(client, headers, name="Sample Biscuit Pack", identifier="DEMO-001"):
    response = client.post(
        "/api/v1/inspections",
        headers=headers,
        json={
            "product_name": name,
            "product_identifier": identifier,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_authentication_is_required_for_inspections(client):
    response = client.get("/api/v1/inspections")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_create_and_reopen_owned_inspection(client, user_factory, auth_headers):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)

    created = create_inspection(client, headers)

    assert created["product_name"] == "Sample Biscuit Pack"
    assert created["product_identifier"] == "DEMO-001"
    assert created["officer_id"] == officer.id
    assert created["status"] == "draft"

    get_response = client.get(
        f"/api/v1/inspections/{created['id']}",
        headers=headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


def test_officer_list_is_scoped_to_owned_inspections(client, user_factory, auth_headers):
    first_officer = user_factory(UserRole.OFFICER)
    second_officer = user_factory(UserRole.OFFICER)
    first_headers = auth_headers(first_officer)
    second_headers = auth_headers(second_officer)

    first = create_inspection(client, first_headers, "First Product", None)
    create_inspection(client, second_headers, "Second Product", None)

    response = client.get("/api/v1/inspections", headers=first_headers)

    assert response.status_code == 200
    records = response.json()
    assert [item["id"] for item in records] == [first["id"]]


def test_officer_cannot_read_another_officers_inspection(
    client,
    user_factory,
    auth_headers,
):
    owner = user_factory(UserRole.OFFICER)
    other = user_factory(UserRole.OFFICER)
    created = create_inspection(client, auth_headers(owner))

    response = client.get(
        f"/api/v1/inspections/{created['id']}",
        headers=auth_headers(other),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inspection_not_found"


def test_supervisor_can_read_but_cannot_create_or_edit(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    supervisor = user_factory(UserRole.SUPERVISOR)
    created = create_inspection(client, auth_headers(officer))
    supervisor_headers = auth_headers(supervisor)

    get_response = client.get(
        f"/api/v1/inspections/{created['id']}",
        headers=supervisor_headers,
    )
    assert get_response.status_code == 200

    create_response = client.post(
        "/api/v1/inspections",
        headers=supervisor_headers,
        json={"product_name": "Not Allowed"},
    )
    assert create_response.status_code == 403

    edit_response = client.patch(
        f"/api/v1/inspections/{created['id']}",
        headers=supervisor_headers,
        json={"product_name": "Not Allowed"},
    )
    assert edit_response.status_code == 403


def test_draft_inspection_can_be_updated_and_submitted(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    created = create_inspection(client, headers)

    update_response = client.patch(
        f"/api/v1/inspections/{created['id']}",
        headers=headers,
        json={
            "product_name": "Updated Biscuit Pack",
            "product_identifier": "",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["product_name"] == "Updated Biscuit Pack"
    assert updated["product_identifier"] is None

    submit_response = client.post(
        f"/api/v1/inspections/{created['id']}/submit",
        headers=headers,
    )

    assert submit_response.status_code == 200
    submitted = submit_response.json()
    assert submitted["status"] == "pending_review"
    assert submitted["submitted_at"] is not None


def test_submitted_inspection_cannot_be_edited_or_resubmitted(
    client,
    user_factory,
    auth_headers,
):
    officer = user_factory(UserRole.OFFICER)
    headers = auth_headers(officer)
    created = create_inspection(client, headers)

    first_submit = client.post(
        f"/api/v1/inspections/{created['id']}/submit",
        headers=headers,
    )
    assert first_submit.status_code == 200

    edit_response = client.patch(
        f"/api/v1/inspections/{created['id']}",
        headers=headers,
        json={"product_name": "Should Not Apply"},
    )
    assert edit_response.status_code == 409

    second_submit = client.post(
        f"/api/v1/inspections/{created['id']}/submit",
        headers=headers,
    )
    assert second_submit.status_code == 409


def test_blank_product_name_is_rejected(client, user_factory, auth_headers):
    officer = user_factory(UserRole.OFFICER)

    response = client.post(
        "/api/v1/inspections",
        headers=auth_headers(officer),
        json={"product_name": "   "},
    )

    assert response.status_code == 422
