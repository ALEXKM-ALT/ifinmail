import pytest


@pytest.fixture
def owner_token(client):
    r = client.post("/auth/register", json={"email": "org_owner@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "org_owner@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "org_owner@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def member_token(client):
    r = client.post("/auth/register", json={"email": "org_member@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "org_member@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "org_member@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/register", json={"email": "org_admin@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "org_admin@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "org_admin@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def org_id(client, owner_token):
    r = client.post("/orgs", json={"name": "TestOrg"}, headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture
def org_with_member(client, owner_token, member_token, org_id):
    client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
    return org_id


class TestOrganizations:
    def test_create_org(self, client, owner_token):
        r = client.post("/orgs", json={"name": "MyOrg"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 201
        assert r.json()["name"] == "MyOrg"

    def test_create_org_with_email(self, client, owner_token):
        r = client.post("/orgs", json={"name": "EmailOrg", "email": "team@myorg.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 201
        assert r.json()["email"] == "team@myorg.com"

    def test_list_orgs(self, client, owner_token, org_id):
        r = client.get("/orgs", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert len(r.json()) >= 1
        assert r.json()[0]["role"] == "owner"

    def test_get_org(self, client, owner_token, org_id):
        r = client.get(f"/orgs/{org_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["name"] == "TestOrg"
        assert r.json()["my_role"] == "owner"

    def test_get_org_not_found(self, client, owner_token):
        r = client.get("/orgs/99999", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_update_org(self, client, owner_token, org_id):
        r = client.put(f"/orgs/{org_id}", json={"name": "UpdatedOrg"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        r2 = client.get(f"/orgs/{org_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.json()["name"] == "UpdatedOrg"

    def test_update_org_email(self, client, owner_token, org_id):
        r = client.put(f"/orgs/{org_id}", json={"email": "new@team.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        r2 = client.get(f"/orgs/{org_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.json()["email"] == "new@team.com"

    def test_update_org_max_users(self, client, owner_token, org_id):
        r = client.put(f"/orgs/{org_id}", json={"max_users": 50}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        r2 = client.get(f"/orgs/{org_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.json()["max_users"] == 50

    def test_invite_member(self, client, owner_token, member_token, org_id):
        r = client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["message"] == "org_member@test.com invited"

    def test_invite_duplicate_member(self, client, owner_token, member_token, org_id):
        client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 409
        assert "already a member" in r.json()["detail"].lower()

    def test_invite_non_existent_user(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/invite", json={"email": "newuser@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["invited"] is False
        assert "invite_token" in r.json()

    def test_invite_forbidden_for_member(self, client, owner_token, member_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/invite", json={"email": "someone@test.com"}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_accept_invite(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/invite", json={"email": "newuser@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        token = r.json()["invite_token"]
        r2 = client.post(f"/auth/register", json={"email": "newuser@test.com", "password": "pass123"})
        login = client.post("/auth/login", json={"email": "newuser@test.com", "password": "pass123"})
        new_token = login.json()["access_token"]
        r3 = client.post(f"/orgs/accept-invite?token={token}", headers={"Authorization": f"Bearer {new_token}"})
        assert r3.status_code == 200
        assert r3.json()["message"] == "Invitation accepted"

    def test_accept_invite_wrong_email(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/invite", json={"email": "newuser@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        token = r.json()["invite_token"]
        r2 = client.post(f"/orgs/accept-invite?token={token}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.status_code == 403

    def test_member_access(self, client, owner_token, member_token, org_id):
        client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.get(f"/orgs/{org_id}", headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 200
        assert r.json()["my_role"] == "member"

    def test_remove_member(self, client, owner_token, member_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/remove/2", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200

    def test_remove_member_not_found(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/remove/99999", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_remove_owner_forbidden(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/remove/1", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 400

    def test_remove_self_forbidden(self, client, owner_token, member_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/remove/2", json={}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_non_owner_cannot_update(self, client, owner_token, member_token, org_id):
        client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.put(f"/orgs/{org_id}", json={"name": "Hacked"}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_leave_org(self, client, owner_token, member_token, org_id):
        client.post(f"/orgs/{org_id}/invite", json={"email": "org_member@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.post(f"/orgs/{org_id}/leave", json={}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 200

    def test_owner_cannot_leave(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/leave", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 400

    def test_leave_not_member(self, client, member_token, org_id):
        r = client.post(f"/orgs/{org_id}/leave", json={}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 404

    def test_delete_org(self, client, owner_token, org_id):
        r = client.delete(f"/orgs/{org_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 204

    def test_delete_org_forbidden_non_owner(self, client, owner_token, member_token, org_with_member):
        r = client.delete(f"/orgs/{org_with_member}", headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_delete_org_cleans_related_data(self, client, owner_token, org_with_member):
        client.post(f"/orgs/{org_with_member}/contacts", json={"email": "contact@test.com", "name": "Test Contact"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.delete(f"/orgs/{org_with_member}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 204
        r2 = client.get(f"/orgs/{org_with_member}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.status_code == 404

    def test_org_not_found_access(self, client, owner_token):
        r = client.get("/orgs/99999", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_create_org_unauthorized(self, client):
        r = client.post("/orgs", json={"name": "NoAuthOrg"})
        assert r.status_code == 401

    def test_list_orgs_empty_for_new_user(self, client):
        r = client.post("/auth/register", json={"email": "fresh_user@test.com", "password": "pass123"})
        login = client.post("/auth/login", json={"email": "fresh_user@test.com", "password": "pass123"})
        token = login.json()["access_token"]
        r = client.get("/orgs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []


class TestOrgContacts:
    def test_add_org_contact(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/contacts", json={"email": "friend@test.com", "name": "Friend"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 201
        assert r.json()["email"] == "friend@test.com"
        assert r.json()["name"] == "Friend"

    def test_list_org_contacts(self, client, owner_token, org_id):
        client.post(f"/orgs/{org_id}/contacts", json={"email": "c1@test.com", "name": "C1"}, headers={"Authorization": f"Bearer {owner_token}"})
        client.post(f"/orgs/{org_id}/contacts", json={"email": "c2@test.com", "name": "C2"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.get(f"/orgs/{org_id}/contacts", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_delete_org_contact(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/contacts", json={"email": "del@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        cid = r.json()["id"]
        r2 = client.delete(f"/orgs/{org_id}/contacts/{cid}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.status_code == 204

    def test_delete_org_contact_forbidden_member(self, client, owner_token, member_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/contacts", json={"email": "del@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        cid = r.json()["id"]
        r2 = client.delete(f"/orgs/{org_with_member}/contacts/{cid}", headers={"Authorization": f"Bearer {member_token}"})
        assert r2.status_code == 403

    def test_member_contacts_search(self, client, owner_token, member_token, org_with_member):
        r = client.get(f"/orgs/{org_with_member}/member-contacts?q=member", headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 200
        assert any("member" in c["email"] for c in r.json())


class TestOrgRolesAndTransfer:
    def test_change_role_to_admin(self, client, owner_token, org_with_member):
        r = client.put(f"/orgs/{org_with_member}/members/2/role", json={"role": "admin"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_change_role_invalid(self, client, owner_token, org_with_member):
        r = client.put(f"/orgs/{org_with_member}/members/2/role", json={"role": "superadmin"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 400

    def test_change_role_not_owner(self, client, owner_token, member_token, org_with_member):
        r = client.put(f"/orgs/{org_with_member}/members/2/role", json={"role": "admin"}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_change_owner_role_forbidden(self, client, owner_token, org_id):
        r = client.put(f"/orgs/{org_id}/members/1/role", json={"role": "member"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 400

    def test_transfer_ownership(self, client, owner_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/transfer/2", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["new_owner_id"] == 2
        org = client.get(f"/orgs/{org_with_member}", headers={"Authorization": f"Bearer {owner_token}"})
        assert org.json()["my_role"] == "admin"

    def test_transfer_ownership_to_self(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/transfer/1", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 400

    def test_transfer_ownership_not_owner(self, client, owner_token, member_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/transfer/1", json={}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_transfer_ownership_member_not_found(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/transfer/99999", json={}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404


class TestOrgEmailAssignment:
    def test_assign_email(self, client, owner_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/emails/1/assign", json={"user_id": 2}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["user_id"] == 2

    def test_assign_email_forbidden_member(self, client, owner_token, member_token, org_with_member):
        r = client.post(f"/orgs/{org_with_member}/emails/1/assign", json={"user_id": 2}, headers={"Authorization": f"Bearer {member_token}"})
        assert r.status_code == 403

    def test_assign_email_member_not_in_org(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/emails/1/assign", json={"user_id": 99999}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_get_assignment(self, client, owner_token, org_with_member):
        client.post(f"/orgs/{org_with_member}/emails/1/assign", json={"user_id": 2}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.get(f"/orgs/{org_with_member}/emails/1/assign", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["assigned"] is True

    def test_get_assignment_not_assigned(self, client, owner_token, org_with_member):
        r = client.get(f"/orgs/{org_with_member}/emails/1/assign", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["assigned"] is False

    def test_unassign_email(self, client, owner_token, org_with_member):
        client.post(f"/orgs/{org_with_member}/emails/1/assign", json={"user_id": 2}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.delete(f"/orgs/{org_with_member}/emails/1/assign", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 204

    def test_add_email_note(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/emails/1/notes", json={"note": "Important email"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert "note_id" in r.json()

    def test_add_email_note_empty(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/emails/1/notes", json={"note": "   "}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 400

    def test_list_email_notes(self, client, owner_token, org_id):
        client.post(f"/orgs/{org_id}/emails/1/notes", json={"note": "First note"}, headers={"Authorization": f"Bearer {owner_token}"})
        client.post(f"/orgs/{org_id}/emails/1/notes", json={"note": "Second note"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.get(f"/orgs/{org_id}/emails/1/notes", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert len(r.json()) == 2


class TestOrgSharedInbox:
    def test_list_shared_inbox_empty(self, client, owner_token, org_id):
        r = client.get(f"/orgs/{org_id}/shared-inbox", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []

    def test_create_shared_inbox_message(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/shared-inbox/99999/notes", json={"note": "test"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_get_shared_inbox_message_not_found(self, client, owner_token, org_id):
        r = client.get(f"/orgs/{org_id}/shared-inbox/99999", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_shared_inbox_status_update(self, client, owner_token, org_id):
        client.post(f"/orgs/{org_id}/contacts", json={"email": "incoming@test.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        r = client.get(f"/orgs/{org_id}/shared-inbox", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200

    def test_shared_inbox_forbidden_non_member(self, client, org_id):
        r = client.post("/auth/register", json={"email": "outsider@test.com", "password": "pass123"})
        login = client.post("/auth/login", json={"email": "outsider@test.com", "password": "pass123"})
        token = login.json()["access_token"]
        r = client.get(f"/orgs/{org_id}/shared-inbox", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    def test_shared_inbox_add_note(self, client, owner_token, org_id):
        r = client.post(f"/orgs/{org_id}/shared-inbox/1/notes", json={"note": "Internal note"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_shared_inbox_list_notes(self, client, owner_token, org_id):
        r = client.get(f"/orgs/{org_id}/shared-inbox/1/notes", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 404

    def test_shared_inbox_filter_by_status(self, client, owner_token, org_id):
        r = client.get(f"/orgs/{org_id}/shared-inbox?status=pending", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200

    def test_org_inbox(self, client, owner_token, org_id):
        r = client.get(f"/orgs/{org_id}/inbox", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200
        assert "items" in r.json()

    def test_org_inbox_forbidden_non_member(self, client, org_id):
        r = client.post("/auth/register", json={"email": "outsider2@test.com", "password": "pass123"})
        login = client.post("/auth/login", json={"email": "outsider2@test.com", "password": "pass123"})
        token = login.json()["access_token"]
        r = client.get(f"/orgs/{org_id}/inbox", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    def test_create_org_with_email_syncs_aliases(self, client, owner_token, db_session):
        from ifinmail.db.models import Domain, Alias
        db_session.add(Domain(domain="example.com", verified=1))
        db_session.commit()

        r = client.post("/orgs", json={"name": "AliasOrg", "email": "team@example.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 201
        org_id = r.json()["id"]

        r = client.post("/auth/register", json={"email": "alias_member@example.com", "password": "pass123"})
        assert r.status_code in (200, 201)

        invite = client.post(f"/orgs/{org_id}/invite", json={"email": "alias_member@example.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert invite.status_code == 200
        assert invite.json()["invited"] is True

        aliases = db_session.query(Alias).filter(Alias.source == "team@example.com").all()
        assert len(aliases) == 2
        targets = {a.target for a in aliases}
        assert "org_owner@test.com" in targets
        assert "alias_member@example.com" in targets

    def test_update_org_email_syncs_aliases(self, client, owner_token, org_id, db_session):
        from ifinmail.db.models import Domain, Alias
        db_session.add(Domain(domain="newteam.com", verified=1))
        db_session.commit()

        r = client.put(f"/orgs/{org_id}", json={"email": "team@newteam.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200

        aliases = db_session.query(Alias).filter(Alias.source == "team@newteam.com").all()
        assert len(aliases) == 1
        assert aliases[0].target == "org_owner@test.com"

    def test_remove_member_syncs_aliases(self, client, owner_token, member_token, org_with_member, db_session):
        from ifinmail.db.models import Domain, Alias, User
        db_session.add(Domain(domain="alias.com", verified=1))
        db_session.commit()

        r = client.put(f"/orgs/{org_with_member}", json={"email": "team@alias.com"}, headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200

        before = db_session.query(Alias).filter(Alias.source == "team@alias.com").all()
        assert len(before) == 2

        member_user = db_session.query(User).filter(User.email == "org_member@test.com").first()
        client.post(f"/orgs/{org_with_member}/remove/{member_user.id}", headers={"Authorization": f"Bearer {owner_token}"})

        after = db_session.query(Alias).filter(Alias.source == "team@alias.com").all()
        assert len(after) == 1
        assert after[0].target == "org_owner@test.com"
