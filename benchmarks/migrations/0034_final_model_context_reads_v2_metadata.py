"""Leaderboard model filters read v2 metadata records, falling back to brainscore_modelmeta."""

from pathlib import Path

from django.db import migrations

SQL_DIR = Path(__file__).resolve().parent / 'sql'
FORWARD_SQL = (SQL_DIR / '0034_final_model_context.sql').read_text(encoding='utf-8')
REVERSE_SQL = (SQL_DIR / '0034_final_model_context_reverse.sql').read_text(encoding='utf-8')


def recreate(definition):
    def run(apps, schema_editor):
        quote = schema_editor.quote_name
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                SELECT pg_get_userbyid(c.relowner), obj_description(c.oid)
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE c.relname='mv_final_model_context' AND n.nspname=current_schema()
            """)
            view = cursor.fetchone()
            indexes, grants = [], []
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
            cursor.execute(definition)
            for index in indexes:
                cursor.execute(index)
            for role, privilege, grantable in grants:
                recipient = "PUBLIC" if role == "PUBLIC" else quote(role)
                cursor.execute(
                    f"GRANT {privilege} ON mv_final_model_context TO {recipient}"
                    + (" WITH GRANT OPTION" if grantable else "")
                )
            if view:
                owner, comment = view
                if comment:
                    cursor.execute(
                        "COMMENT ON MATERIALIZED VIEW mv_final_model_context IS %s", [comment]
                    )
                cursor.execute(
                    "ALTER MATERIALIZED VIEW mv_final_model_context OWNER TO " + quote(owner)
                )
    return run


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0033_metadata_revision_merged_by'),
    ]

    operations = [
        migrations.RunPython(recreate(FORWARD_SQL), recreate(REVERSE_SQL)),
    ]
