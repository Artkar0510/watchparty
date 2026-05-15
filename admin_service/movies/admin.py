from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from movies.models import FilmWork, Genre, GenreFilmWork


class GenreFilmWorkInline(admin.TabularInline):
    model = GenreFilmWork
    extra = 1


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(FilmWork)
class FilmWorkAdmin(admin.ModelAdmin):
    inlines = [GenreFilmWorkInline]
    list_display = ("title", "type", "rating", "created_at")
    list_filter = ("type", "genres")
    search_fields = ("title", "description", "id")
    ordering = ("-rating",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "type", "description")}),
        (_("Рейтинг"), {"fields": ("rating",)}),
        (_("Даты"), {"fields": ("created_at", "updated_at")}),
    )


admin.site.site_header = "Кино вместе — Администрирование"
admin.site.site_title = "Кино вместе"
admin.site.index_title = "Управление контентом"
