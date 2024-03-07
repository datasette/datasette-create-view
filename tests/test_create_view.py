from datasette.app import Datasette
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor,sql,should_see_option",
    (
        (None, "select 1", False),
        ("non_root", "select 1", False),
        ("root", "select 1", True),
        ("root", "select :name", False),
    ),
)
async def test_query_action_menu(actor, sql, should_see_option):
    datasette = Datasette()
    db = datasette.add_memory_database("test")
    cookies = {}
    if actor:
        cookies = {"ds_actor": datasette.client.actor_cookie({"id": actor})}
    response = await datasette.client.get("/test", params={"sql": sql}, cookies=cookies)
    fragment = (
        '<a href="/test/-/create-view?sql=select+1">Create SQL view for this query</a>'
    )
    if should_see_option:
        assert fragment in response.text
    else:
        assert fragment not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor,args,expected_error",
    (
        (
            None,
            {"name": "a", "sql": "select 1"},
            "create-table permission is needed to create views",
        ),
        (
            "non_root",
            {"name": "a", "sql": "select 1"},
            "create-table permission is needed to create views",
        ),
        ("root", {"name": "", "sql": "select 1"}, "SQL and name are both required"),
        ("root", {"name": "a", "sql": ""}, "SQL and name are both required"),
        (
            "root",
            {"name": "a", "sql": "select :id"},
            "SQL query cannot have :named parameters",
        ),
    ),
)
async def test_create_view_errors(actor, args, expected_error):
    # Get csfrtoken
    datasette = Datasette()
    db = datasette.add_memory_database("test")
    cookies = {}
    if actor:
        cookies = {"ds_actor": datasette.client.actor_cookie({"id": actor})}
    get_response = await datasette.client.get(
        "/test/-/create-view", params=args, cookies=cookies
    )
    assert get_response.status_code == 200
    csrftoken = get_response.cookies["ds_csrftoken"]
    cookies["ds_csrftoken"] = csrftoken
    # Now do the POST
    response = await datasette.client.post(
        "/test/-/create-view", data=dict(args, csrftoken=csrftoken), cookies=cookies
    )
    assert response.status_code == 302
    assert response.url == "http://localhost/test/-/create-view"
    messages = datasette.unsign(response.cookies["ds_messages"], "messages")
    assert messages == [[expected_error, 3]]


@pytest.mark.asyncio
async def test_happy_path():
    datasette = Datasette()
    db = datasette.add_memory_database("test")
    cookies = {"ds_actor": datasette.client.actor_cookie({"id": "root"})}
    get_response = await datasette.client.get("/test/-/create-view", cookies=cookies)
    csrftoken = get_response.cookies["ds_csrftoken"]
    cookies["ds_csrftoken"] = csrftoken

    assert await db.view_names() == []

    # Create the view
    response = await datasette.client.post(
        "/test/-/create-view",
        data={"sql": "select 1", "name": "new_view", "csrftoken": csrftoken},
        cookies=cookies,
    )
    assert response.status_code == 302
    assert response.url == "http://localhost/test/-/create-view"
    messages = datasette.unsign(response.cookies["ds_messages"], "messages")
    assert messages == [["SQL view 'new_view' has been created", 1]]

    assert await db.view_names() == ["new_view"]
