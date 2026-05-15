import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class UUIDMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Genre(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_("name"), max_length=255, unique=True)
    description = models.TextField(_("description"), blank=True, null=True)

    class Meta:
        db_table = "genre"
        verbose_name = _("Жанр")
        verbose_name_plural = _("Жанры")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FilmWork(UUIDMixin, TimeStampedMixin):
    class FilmType(models.TextChoices):
        MOVIE = "movie", _("Фильм")
        TV_SHOW = "tv_show", _("Сериал")

    title = models.CharField(_("title"), max_length=255)
    description = models.TextField(_("description"), blank=True, null=True)
    rating = models.FloatField(
        _("rating"),
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    type = models.CharField(
        _("type"), max_length=20, choices=FilmType.choices, default=FilmType.MOVIE
    )
    genres = models.ManyToManyField(
        Genre, through="GenreFilmWork", verbose_name=_("genres"), blank=True
    )

    class Meta:
        db_table = "film_work"
        verbose_name = _("Кинопроизведение")
        verbose_name_plural = _("Кинопроизведения")
        ordering = ["-rating"]
        indexes = [
            models.Index(fields=["title"], name="idx_film_work_title"),
            models.Index(fields=["-rating"], name="idx_film_work_rating"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_type_display()})"


class GenreFilmWork(UUIDMixin):
    film_work = models.ForeignKey(FilmWork, on_delete=models.CASCADE, verbose_name=_("film"))
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE, verbose_name=_("genre"))

    class Meta:
        db_table = "genre_film_work"
        verbose_name = _("Жанр фильма")
        verbose_name_plural = _("Жанры фильма")
        unique_together = [["film_work", "genre"]]

    def __str__(self) -> str:
        return f"{self.film_work} — {self.genre}"
