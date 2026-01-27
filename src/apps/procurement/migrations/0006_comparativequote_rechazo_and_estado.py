from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0005_comparativequoteattachment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="comparativequote",
            name="rechazado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="comparativequote",
            name="rechazado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cc_rechazados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="comparativequote",
            name="estado",
            field=models.CharField(
                choices=[
                    ("BORRADOR", "Borrador"),
                    ("EN_REVISION", "En revisión"),
                    ("REVISADO", "Revisado"),
                    ("APROBADO", "Aprobado"),
                    ("RECHAZADO", "Rechazado"),
                ],
                default="BORRADOR",
                max_length=20,
            ),
        ),
    ]
