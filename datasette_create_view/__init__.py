from datasette import hookimpl, Response
from datasette.utils import derive_named_parameters
import urllib


@hookimpl
def query_actions(datasette, database, actor, query_name, sql):
    if query_name:
        return

    async def inner():
        db = datasette.get_database(database)
        parameters = await derive_named_parameters(db, sql)
        if parameters:
            return
        # User must have create-table permission
        if not await datasette.permission_allowed(
            actor, "create-table", resource=database
        ):
            return
        return [
            {
                "href": datasette.urls.database(database)
                + "/-/create-view?"
                + urllib.parse.urlencode(
                    {
                        "sql": sql,
                    }
                ),
                "label": "Create SQL view for this query",
                "description": "A named SQL view provides a convenient alias for executing this query and using it in joins.",
            },
        ]

    return inner


async def create_view(request, datasette):
    database = request.url_vars["database"]
    db = datasette.get_database(database)
    if request.method == "POST":
        post_vars = await request.post_vars()
        sql = (post_vars.get("sql") or "").strip()
        name = (post_vars.get("name") or "").strip()
        error_response = Response.redirect(
            request.path
            + "?"
            + urllib.parse.urlencode(
                {
                    "sql": sql,
                    "name": name,
                }
            )
        )
        if not await datasette.permission_allowed(
            request.actor, "create-table", resource=database
        ):
            datasette.add_message(
                request,
                "create-table permission is needed to create views",
                datasette.ERROR,
            )
            return error_response
        if (not sql) or (not name):
            datasette.add_message(
                request, "SQL and name are both required", datasette.ERROR
            )
            return error_response
        parameters = await derive_named_parameters(db, sql)
        if parameters:
            datasette.add_message(
                request, "SQL query cannot have :named parameters", datasette.ERROR
            )
            return error_response
        # Try to create the view
        try:
            await db.execute_write("create view {} as {}".format(name, sql))
        except Exception as ex:
            datasette.add_message(request, str(ex), datasette.ERROR)
            return error_response
        # View was created, redirect to it
        datasette.add_message(
            request, f"SQL view '{name}' has been created", datasette.INFO
        )
        return Response.redirect(datasette.urls.table(database, name))
    return Response.html(
        await datasette.render_template(
            "create_view.html",
            {
                "sql": request.args.get("sql") or "",
                "name": request.args.get("name") or "",
                "database": db.name,
            },
            request=request,
        )
    )


@hookimpl
def register_routes():
    return [
        (r"^/(?P<database>[^/]+)/-/create-view$", create_view),
    ]
