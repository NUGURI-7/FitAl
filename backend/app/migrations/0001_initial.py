from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields


class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                ("nickname", fields.CharField(unique=True, max_length=50)),
                ("weight_kg", fields.FloatField()),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "users", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Record",
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
                        related_name="records",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("record_type", fields.CharField(max_length=16)),
                ("raw_text", fields.TextField(unique=False)),
                ("source", fields.CharField(max_length=32)),
                ("kcal", fields.FloatField()),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "records", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
