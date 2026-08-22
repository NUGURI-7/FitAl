from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0012_food_record_unit_count")]

    initial = False

    operations = [
        ops.AddField(
            model_name="FoodRecord",
            name="spoken_name",
            field=fields.CharField(null=True, max_length=64),
        ),
    ]
