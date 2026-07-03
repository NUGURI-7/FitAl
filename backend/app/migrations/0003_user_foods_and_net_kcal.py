from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0002_raw_new_seven_tables")]

    initial = False

    operations = [
        ops.CreateModel(
            name="UserFood",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                (
                    "user",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="user_foods",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("name", fields.CharField(max_length=64)),
                ("unit", fields.CharField(default="份", max_length=16)),
                ("kcal", fields.FloatField()),
                ("protein", fields.FloatField(null=True)),
                ("fat", fields.FloatField(null=True)),
                ("cho", fields.FloatField(null=True)),
                ("fiber", fields.FloatField(null=True)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={
                "table": "user_foods",
                "app": "models",
                "unique_together": (("user", "name"),),
                "pk_attr": "id",
                "table_description": '用户自定义食物:按"份"定义一次,查表优先级高于标准表。',
            },
            bases=["Model"],
        ),
        ops.AddField(
            model_name="ExerciseRecord",
            name="kcal_net",
            field=fields.FloatField(null=True),
        ),
    ]
