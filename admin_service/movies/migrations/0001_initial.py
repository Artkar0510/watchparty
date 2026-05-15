import uuid
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Genre",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, unique=True, verbose_name="name")),
                ("description", models.TextField(blank=True, null=True, verbose_name="description")),
            ],
            options={"db_table": "genre", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="FilmWork",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=255, verbose_name="title")),
                ("description", models.TextField(blank=True, null=True, verbose_name="description")),
                ("rating", models.FloatField(
                    blank=True, null=True, verbose_name="rating",
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(10),
                    ],
                )),
                ("type", models.CharField(
                    choices=[("movie", "Фильм"), ("tv_show", "Сериал")],
                    default="movie", max_length=20, verbose_name="type",
                )),
            ],
            options={"db_table": "film_work", "ordering": ["-rating"]},
        ),
        migrations.CreateModel(
            name="GenreFilmWork",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("film_work", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="movies.filmwork", verbose_name="film",
                )),
                ("genre", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="movies.genre", verbose_name="genre",
                )),
            ],
            options={"db_table": "genre_film_work"},
        ),
        migrations.AddField(
            model_name="filmwork",
            name="genres",
            field=models.ManyToManyField(
                blank=True, through="movies.GenreFilmWork",
                to="movies.genre", verbose_name="genres",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="genrefilmwork",
            unique_together={("film_work", "genre")},
        ),
        migrations.AddIndex(
            model_name="filmwork",
            index=models.Index(fields=["title"], name="idx_film_work_title"),
        ),
        migrations.AddIndex(
            model_name="filmwork",
            index=models.Index(fields=["-rating"], name="idx_film_work_rating"),
        ),
    ]
