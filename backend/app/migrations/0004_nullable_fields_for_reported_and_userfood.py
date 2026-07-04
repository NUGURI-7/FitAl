from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0003_user_foods_and_net_kcal")]

    initial = False

    operations = [
        ops.AlterField(
            model_name="ExerciseRecord",
            name="duration_min",
            field=fields.FloatField(null=True),
        ),
        ops.AlterField(
            model_name="ExerciseRecord",
            name="met",
            field=fields.FloatField(null=True),
        ),
        ops.AlterField(
            model_name="FoodRecord",
            name="grams",
            field=fields.FloatField(null=True),
        ),
    ]
