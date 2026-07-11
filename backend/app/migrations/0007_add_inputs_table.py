from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise.fields.base import OnDelete
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0006_food_records_dish_tag")]

    initial = False

    operations = [
        ops.CreateModel(
            name="Input",
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
                        related_name="inputs",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("text", fields.TextField(unique=False)),
                ("status", fields.CharField(default="pending", max_length=16)),
                (
                    "ai_rounds",
                    fields.JSONField(
                        null=True,
                        encoder=functools.partial(dumps, separators=(",", ":")),
                        decoder=loads,
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={
                "table": "inputs",
                "app": "models",
                "pk_attr": "id",
                "table_description": "输入表:一次原始输入一行,raw 记录挂外键指回(一句话→多记录)。",
            },
            bases=["Model"],
        ),
        ops.AddField(
            model_name="ExerciseRecord",
            name="input",
            field=fields.ForeignKeyField(
                "models.Input",
                source_field="input_id",
                null=True,
                db_constraint=True,
                to_field="id",
                related_name="exercise_records",
                on_delete=OnDelete.SET_NULL,
            ),
        ),
        ops.AddField(
            model_name="FoodRecord",
            name="input",
            field=fields.ForeignKeyField(
                "models.Input",
                source_field="input_id",
                null=True,
                db_constraint=True,
                to_field="id",
                related_name="food_records",
                on_delete=OnDelete.SET_NULL,
            ),
        ),
        ops.AddField(
            model_name="WeightRecord",
            name="input",
            field=fields.ForeignKeyField(
                "models.Input",
                source_field="input_id",
                null=True,
                db_constraint=True,
                to_field="id",
                related_name="weight_records",
                on_delete=OnDelete.SET_NULL,
            ),
        ),
    ]
