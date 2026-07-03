from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0001_initial")]

    initial = False

    operations = [
        ops.CreateModel(
            name="AiMemory",
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
                        related_name="ai_memories",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("kind", fields.CharField(max_length=16)),
                ("content", fields.TextField(unique=False)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={"table": "ai_memories", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Meal",
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
                        related_name="meals",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("name", fields.CharField(null=True, max_length=64)),
                ("start", fields.DatetimeField(auto_now=False, auto_now_add=False)),
                ("end", fields.DatetimeField(auto_now=False, auto_now_add=False)),
                ("kcal_total", fields.FloatField(default=0)),
            ],
            options={"table": "meals", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FoodRecord",
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
                        related_name="food_records",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("raw_text", fields.TextField(unique=False)),
                ("source", fields.CharField(max_length=32)),
                ("kcal", fields.FloatField()),
                ("food_name", fields.CharField(max_length=64)),
                ("grams", fields.FloatField()),
                ("protein", fields.FloatField(null=True)),
                ("fat", fields.FloatField(null=True)),
                ("cho", fields.FloatField(null=True)),
                ("fiber", fields.FloatField(null=True)),
                (
                    "meal",
                    fields.ForeignKeyField(
                        "models.Meal",
                        source_field="meal_id",
                        null=True,
                        db_constraint=True,
                        to_field="id",
                        related_name="items",
                        on_delete=OnDelete.SET_NULL,
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "food_records", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Session",
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
                        related_name="sessions",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("name", fields.CharField(null=True, max_length=64)),
                ("start", fields.DatetimeField(auto_now=False, auto_now_add=False)),
                ("end", fields.DatetimeField(auto_now=False, auto_now_add=False)),
                ("kcal_total", fields.FloatField(default=0)),
            ],
            options={"table": "sessions", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="ExerciseRecord",
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
                        related_name="exercise_records",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("raw_text", fields.TextField(unique=False)),
                ("source", fields.CharField(max_length=32)),
                ("kcal", fields.FloatField()),
                ("exercise_name", fields.CharField(max_length=64)),
                ("met", fields.FloatField()),
                ("duration_min", fields.FloatField()),
                ("load_kg", fields.FloatField(null=True)),
                ("reps", fields.IntField(null=True)),
                (
                    "session",
                    fields.ForeignKeyField(
                        "models.Session",
                        source_field="session_id",
                        null=True,
                        db_constraint=True,
                        to_field="id",
                        related_name="items",
                        on_delete=OnDelete.SET_NULL,
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "exercise_records", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="WeightRecord",
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
                        related_name="weight_records",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("weight_kg", fields.FloatField()),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "weight_records", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.RenameField(
            model_name="User",
            old_name="weight_kg",
            new_name="height_cm",
        ),
        ops.AddField(
            model_name="User",
            name="birth_year",
            field=fields.IntField(),
        ),
        ops.AddField(
            model_name="User",
            name="sex",
            field=fields.CharField(max_length=8),
        ),
        ops.DeleteModel(name="Record"),
    ]
