from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("movies", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="filmwork",
            name="video_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Прямой URL до MP4 или путь /videos/myfile.mp4 для локального файла",
                max_length=2048,
                verbose_name="Ссылка на видео",
            ),
        ),
    ]
