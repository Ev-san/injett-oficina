import uuid

from django.db import migrations, models


def gerar_tokens(apps, schema_editor):
    Checklist = apps.get_model("oficina", "Checklist")
    for c in Checklist.objects.all():
        c.token = uuid.uuid4()
        c.save(update_fields=["token"])


class Migration(migrations.Migration):

    dependencies = [
        ("oficina", "0004_checklist"),
    ]

    operations = [
        migrations.AddField(
            model_name="checklist",
            name="token",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(gerar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="checklist",
            name="token",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
