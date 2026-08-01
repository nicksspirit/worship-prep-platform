import unicodedata

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations, models


def populate_normalized_titles(apps, schema_editor):
    CatalogEntry = apps.get_model("catalog", "CatalogEntry")
    for entry in CatalogEntry.objects.only("pk", "title").iterator(chunk_size=500):
        decomposed = unicodedata.normalize("NFKD", entry.title)
        unaccented = "".join(
            character for character in decomposed if not unicodedata.combining(character)
        )
        entry.normalized_title = " ".join(unaccented.casefold().split())
        entry.save(update_fields=["normalized_title"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_initial"),
    ]

    operations = [
        UnaccentExtension(),
        TrigramExtension(),
        migrations.RunSQL(
            sql="""
                CREATE TEXT SEARCH CONFIGURATION public.wpp_simple_unaccent
                    (COPY = pg_catalog.simple);
                ALTER TEXT SEARCH CONFIGURATION public.wpp_simple_unaccent
                    ALTER MAPPING FOR hword, hword_part, word
                    WITH unaccent, simple;
            """,
            reverse_sql="""
                DROP TEXT SEARCH CONFIGURATION IF EXISTS
                    public.wpp_simple_unaccent;
            """,
        ),
        migrations.AddField(
            model_name="catalogentry",
            name="normalized_title",
            field=models.CharField(default="", max_length=512),
            preserve_default=False,
        ),
        migrations.RunPython(
            populate_normalized_titles,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunSQL(
            sql="""
                UPDATE catalog_catalogentry
                SET title_search = to_tsvector(
                        'public.wpp_simple_unaccent',
                        coalesce(title, '')
                    ),
                    lyrics_search = to_tsvector(
                        'public.wpp_simple_unaccent',
                        coalesce(cleaned_lyrics, '')
                    );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="catalogentry",
            index=models.Index(
                fields=["snapshot", "normalized_title", "song_uid"],
                name="catalog_page_order_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="catalogentry",
            index=GinIndex(
                fields=["title_search"],
                name="catalog_title_fts_gin",
            ),
        ),
        migrations.AddIndex(
            model_name="catalogentry",
            index=GinIndex(
                fields=["lyrics_search"],
                name="catalog_lyrics_fts_gin",
            ),
        ),
        migrations.AddIndex(
            model_name="catalogentry",
            index=GinIndex(
                fields=["normalized_title"],
                name="catalog_title_trgm_gin",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
