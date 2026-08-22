from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0011_unit_columns")]

    initial = False

    operations = [
        ops.AddField(
            model_name="FoodRecord",
            name="unit_count",
            field=fields.IntField(null=True),
        ),
    ]
