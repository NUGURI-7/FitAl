from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(primary_key=True)
    nickname = fields.CharField(max_length=50, unique=True)
    weight_kg = fields.FloatField()  # 参与运动消耗计算:kcal = MET × 体重 × 时长
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class Record(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="records", on_delete=fields.CASCADE
    )
    record_type = fields.CharField(max_length=16)  # exercise | food
    raw_text = fields.TextField()  # 用户原始输入,永久保留
    source = fields.CharField(
        max_length=32
    )  # user_reported | met_table | food_table | llm_estimated
    kcal = fields.FloatField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "records"
