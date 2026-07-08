from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0005_user_foods_per_100g")]

    initial = False

    operations = [
        ops.AddField(
            model_name="FoodRecord",
            name="dish",
            field=fields.CharField(null=True, max_length=64),
        ),
    ]
