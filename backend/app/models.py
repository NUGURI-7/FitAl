from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(primary_key=True)
    nickname = fields.CharField(max_length=50, unique=True)
    # 身体档案:修正 MET 公式(Mifflin-St Jeor)用,一次性填;体重走 weight_records
    height_cm = fields.FloatField()
    sex = fields.CharField(max_length=8)  # male | female
    birth_year = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class WeightRecord(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="weight_records", on_delete=fields.CASCADE
    )
    weight_kg = fields.FloatField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "weight_records"


# ── new 层:聚合粒度,AI+规则维护,可随时从 raw 整层重算 ──────────────────


class Meal(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="meals", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=64, null=True)  # AI 起名,如"番茄炒蛋+米饭"
    start = fields.DatetimeField()
    end = fields.DatetimeField()
    kcal_total = fields.FloatField(default=0)

    class Meta:
        table = "meals"


class Session(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="sessions", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=64, null=True)  # AI 起名,如"晚间胸部训练"
    start = fields.DatetimeField()
    end = fields.DatetimeField()
    kcal_total = fields.FloatField(default=0)

    class Meta:
        table = "sessions"


# ── raw 层:碎片粒度,怎么说的怎么存;唯一事实源,修正/删除只落这里 ──────


class ExerciseRecord(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="exercise_records", on_delete=fields.CASCADE
    )
    raw_text = fields.TextField()  # 用户原话,永久保留
    source = fields.CharField(
        max_length=32
    )  # user_reported | met_table | llm_estimated
    kcal = fields.FloatField()
    exercise_name = fields.CharField(max_length=64)
    met = fields.FloatField()
    duration_min = fields.FloatField()  # 力量组=组动作时间+距上一组间隔(后端推断)
    load_kg = fields.FloatField(null=True)
    reps = fields.IntField(null=True)
    # 归属场次由聚合维护;删场次不动 raw
    session = fields.ForeignKeyField(
        "models.Session", related_name="items", null=True, on_delete=fields.SET_NULL
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "exercise_records"


class FoodRecord(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="food_records", on_delete=fields.CASCADE
    )
    raw_text = fields.TextField()
    source = fields.CharField(
        max_length=32
    )  # user_reported | food_table | llm_estimated
    kcal = fields.FloatField()
    food_name = fields.CharField(max_length=64)
    grams = fields.FloatField()
    protein = fields.FloatField(null=True)
    fat = fields.FloatField(null=True)
    cho = fields.FloatField(null=True)
    fiber = fields.FloatField(null=True)
    meal = fields.ForeignKeyField(
        "models.Meal", related_name="items", null=True, on_delete=fields.SET_NULL
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "food_records"


class AiMemory(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="ai_memories", on_delete=fields.CASCADE
    )
    kind = fields.CharField(max_length=16)  # alias | habit | correction
    content = fields.TextField()
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "ai_memories"
