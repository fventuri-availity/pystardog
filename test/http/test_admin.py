import pytest

from stardog.content_types import TURTLE
from stardog.exceptions import StardogException
from stardog.http.admin import Admin
from stardog.http.client import Client
from stardog.http.connection import Connection

DEFAULT_USERS = ['admin', 'anonymous']
DEFAULT_ROLES = ['reader']


@pytest.fixture(scope="module")
def admin():
    with Admin() as admin:

        for db in admin.databases():
            db.drop()

        for user in admin.users():
            if user.name not in DEFAULT_USERS:
                user.delete()

        for role in admin.roles():
            if role.name not in DEFAULT_ROLES:
                role.delete()

        yield admin


def test_databases(admin):
    assert len(admin.databases()) == 0

    # create database
    db = admin.new_database('db', {'search.enabled': True, 'spatial.enabled': True})

    assert len(admin.databases()) == 1
    assert db.name == 'db'
    assert db.get_options('search.enabled', 'spatial.enabled') == {'search.enabled': True, 'spatial.enabled': True}

    # change options
    db.offline()
    db.set_options({'spatial.enabled': False})
    db.online()

    assert db.get_options('search.enabled', 'spatial.enabled') == {'search.enabled': True, 'spatial.enabled': False}

    # optimize
    db.optimize()

    # repair
    db.offline()
    db.repair()
    db.online()

    # copy to new database
    db.offline()
    copy = db.copy('copy')

    assert len(admin.databases()) == 2
    assert copy.name == 'copy'
    assert copy.get_options('search.enabled', 'spatial.enabled') == {'search.enabled': True, 'spatial.enabled': False}

    # bulk load
    with open('test/data/example.ttl', 'rb') as f:
        bl = admin.new_database('bulkload', {}, {'name': 'example.ttl', 'content': f, 'content-type': TURTLE, 'context': 'urn:a'})

    with Connection('bulkload', username='admin', password='admin') as c:
        assert c.size() == 1

    # clear
    copy.drop()
    db.drop()
    bl.drop()

    assert len(admin.databases()) == 0


def test_users(admin):
    assert len(admin.users()) == len(DEFAULT_USERS)

    # new user
    user = admin.new_user('username', 'password', False)

    assert len(admin.users()) == len(DEFAULT_USERS) + 1
    assert user.is_superuser() == False
    assert user.is_enabled() == True

    # check if able to connect
    with Admin(username='username', password='password') as uadmin:
        uadmin.validate()

    # change password
    user.set_password('new_password')
    with Admin(username='username', password='new_password') as uadmin:
        uadmin.validate()

    # disable/enable
    user.set_enabled(False)
    assert user.is_enabled() == False
    user.set_enabled(True)
    assert user.is_enabled() == True

    # roles
    assert len(user.roles()) == 0

    user.add_role('reader')
    assert len(user.roles()) == 1

    user.set_roles('reader')
    assert len(user.roles()) == 1

    user.remove_role('reader')
    assert len(user.roles()) == 0

    # permissions
    assert user.permissions() == [{'action': 'READ', 'resource_type': 'user', 'resource': ['username']}]
    assert user.effective_permissions() == [{'action': 'READ', 'resource_type': 'user', 'resource': ['username']}]

    user.add_permission('WRITE', 'user', 'username')
    assert user.permissions() == [{'action': 'READ', 'resource_type': 'user', 'resource': ['username']}, {'action': 'WRITE', 'resource_type': 'user', 'resource': ['username']}]

    user.remove_permission('WRITE', 'user', 'username')
    assert user.permissions() == [{'action': 'READ', 'resource_type': 'user', 'resource': ['username']}]

    # delete user
    user.delete()

    assert len(admin.users()) == len(DEFAULT_USERS)


def test_roles(admin):
    assert len(admin.roles()) == len(DEFAULT_ROLES)

    # users
    role = admin.role('reader')
    assert len(role.users()) > 0

    # new role
    role = admin.new_role('writer')
    assert len(admin.roles()) == len(DEFAULT_ROLES) + 1

    # permissions
    assert role.permissions() == []

    role.add_permission('WRITE', '*', '*')
    assert role.permissions() == [{'action': 'WRITE', 'resource_type': '*', 'resource': ['*']}]

    role.remove_permission('WRITE', '*', '*')
    assert role.permissions() == []

    # remove role
    role.delete()

    assert len(admin.roles()) == len(DEFAULT_ROLES)


def test_queries(admin):
    assert len(admin.queries()) == 0

    with pytest.raises(StardogException, match='UnknownQuery: Query not found: 1'):
        admin.query(1)

    with pytest.raises(StardogException, match='UnknownQuery: Query not found: 1'):
        admin.kill_query(1)


def test_virtual_graphs(admin):

    assert len(admin.virtual_graphs()) == 0

    with open('test/data/r2rml.ttl') as f:
        mappings = f.read()

    options = {
        "namespaces": "stardog=tag:stardog:api",
        "jdbc.driver": "com.mysql.jdbc.Driver",
        "jdbc.username": "admin",
        "jdbc.password": "admin",
        "jdbc.url": "jdbc:mysql://localhost/support"
    }

    vg = admin.virtual_graph('test')

    # TODO add VG to test server
    with pytest.raises(StardogException, match='java.sql.SQLException'):
        admin.new_virtual_graph('vg', mappings, options)

    with pytest.raises(StardogException, match='java.sql.SQLException'):
        vg.update('vg', mappings, options)

    with pytest.raises(StardogException, match='Virtual Graph test Not Found!'):
        vg.available()

    with pytest.raises(StardogException, match='Virtual Graph test Not Found!'):
        vg.options()

    with pytest.raises(StardogException, match='Virtual Graph test Not Found!'):
        vg.mappings()

    with pytest.raises(StardogException, match='Virtual Graph test Not Found!'):
        vg.delete()
