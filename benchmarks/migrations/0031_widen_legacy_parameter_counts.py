"""Allow language-model counts while preserving the dependent view definition."""

from django.db import migrations, models


def resize(schema_editor, sql_type):
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT pg_get_viewdef(c.oid), pg_get_userbyid(c.relowner),
                   obj_description(c.oid)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relname='mv_final_model_context' AND n.nspname=current_schema()
        """)
        view = cursor.fetchone()
        if view:
            cursor.execute(
                "SELECT indexdef FROM pg_indexes WHERE tablename='mv_final_model_context' AND schemaname=current_schema()"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            cursor.execute("""
                SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                       a.privilege_type, a.is_grantable
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
                     LATERAL aclexplode(c.relacl) a
                WHERE c.relname='mv_final_model_context' AND n.nspname=current_schema()
            """)
            grants = cursor.fetchall()
            # No CASCADE: an unexpected dependency aborts the transaction.
            cursor.execute("DROP MATERIALIZED VIEW mv_final_model_context")
        for column in ("total_parameter_count", "trainable_parameter_count"):
            cursor.execute(
                f"ALTER TABLE brainscore_modelmeta ALTER COLUMN {quote(column)} TYPE {sql_type}"
            )
        if view:
            definition, owner, comment = view
            cursor.execute(
                "CREATE MATERIALIZED VIEW mv_final_model_context AS " + definition
            )
            for index in indexes:
                cursor.execute(index)
            for role, privilege, grantable in grants:
                recipient = "PUBLIC" if role == "PUBLIC" else quote(role)
                cursor.execute(
                    f"GRANT {privilege} ON mv_final_model_context TO {recipient}"
                    + (" WITH GRANT OPTION" if grantable else "")
                )
            if comment:
                cursor.execute(
                    "COMMENT ON MATERIALIZED VIEW mv_final_model_context IS %s",
                    [comment],
                )
            cursor.execute(
                "ALTER MATERIALIZED VIEW mv_final_model_context OWNER TO "
                + quote(owner)
            )


def forward(apps, schema_editor):
    resize(schema_editor, "bigint")


def backward(apps, schema_editor):
    # PostgreSQL rejects rollback if a count no longer fits in an integer.
    resize(schema_editor, "integer")


class Migration(migrations.Migration):
    dependencies = [("benchmarks", "0030_metadata_publication_history")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(forward, backward)],
            state_operations=[
                migrations.AlterField(
                    model_name="modelmeta",
                    name=name,
                    field=models.BigIntegerField(default=None, null=True),
                )
                for name in ("total_parameter_count", "trainable_parameter_count")
            ],
        ),
    ]
