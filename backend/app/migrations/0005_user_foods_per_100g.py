from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0004_nullable_fields_for_reported_and_userfood")]

    initial = False

    operations = [
        ops.AlterModelOptions(
            name="UserFood",
            options={
                "table": "user_foods",
                "app": "models",
                "unique_together": (("user", "name"),),
                "pk_attr": "id",
                "table_description": "用户自定义食物:每100克口径,与官方表同构;查表优先级高于标准表。",
            },
        ),
        ops.AddField(
            model_name="UserFood",
            name="form",
            field=fields.CharField(null=True, max_length=16),
        ),
        ops.RemoveField(model_name="UserFood", name="unit"),
    ]
