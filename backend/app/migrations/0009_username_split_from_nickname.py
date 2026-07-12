from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0008_auth_tables_and_password")]

    initial = False

    operations = [
        ops.AlterField(
            model_name="User",
            name="nickname",
            field=fields.CharField(max_length=50),
        ),
        ops.AddField(
            model_name="User",
            name="username",
            field=fields.CharField(null=True, unique=True, max_length=20),
        ),
    ]
