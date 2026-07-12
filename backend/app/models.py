from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(primary_key=True)
    # 登录标识(2026-07-12 用户定,与昵称拆分):字母数字下划线3-20位,注册后不可改;
    # 可空过渡——拆分前的存量用户无用户名,脚本补
    username = fields.CharField(max_length=20, unique=True, null=True)
    # 纯显示名,允许重名,设置页随便改;与登录无关
    nickname = fields.CharField(max_length=50)
    # bcrypt 哈希;可空过渡——登录实施前的存量用户无密码,切换时脚本补
    password_hash = fields.CharField(max_length=128, null=True)
    # 身体档案:修正 MET 公式(Mifflin-St Jeor)用,一次性填;体重走 weight_records
    height_cm = fields.FloatField()
    sex = fields.CharField(max_length=8)  # male | female
    birth_year = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class InviteCode(Model):
    """邀请码:管理员脚本直插生成,一人一码,注册消耗即作废(used_at 非空=已用)。"""

    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=32, unique=True)
    used_by = fields.ForeignKeyField(
        "models.User",
        related_name="invite_codes",
        null=True,
        on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    used_at = fields.DatetimeField(null=True)

    class Meta:
        table = "invite_codes"


class AuthToken(Model):
    """登录令牌:纯随机不透明串,认人靠查表;长期有效,删行即失效。

    一用户多令牌(多设备并存);行数=登录次数,非请求次数。
    """

    id = fields.IntField(primary_key=True)
    token = fields.CharField(max_length=64, unique=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="auth_tokens", on_delete=fields.CASCADE
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "auth_tokens"


class WeightRecord(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="weight_records", on_delete=fields.CASCADE
    )
    weight_kg = fields.FloatField()
    # 来自哪次输入;老数据为空。删输入行不动 raw(raw 是唯一事实源)
    input = fields.ForeignKeyField(
        "models.Input",
        related_name="weight_records",
        null=True,
        on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "weight_records"


class Input(Model):
    """输入表:一次原始输入一行,raw 记录挂外键指回(一句话→多记录)。

    失败也留底(此前整句炸连原话都不剩);ai_rounds 存各轮 AI 原始吐出,
    纯日志只为错例回放,业务数据照旧走正规表列。
    """

    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="inputs", on_delete=fields.CASCADE
    )
    text = fields.TextField()  # 原话全文,永久保留
    status = fields.CharField(
        max_length=16, default="pending"
    )  # pending | ok | partial | failed
    ai_rounds = fields.JSONField(null=True)  # {轮名: 原始输出} 错例回放用
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "inputs"


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
    kcal = fields.FloatField()  # 总耗(含同时段基础代谢,市面口径)
    kcal_net = fields.FloatField(null=True)  # 净耗(MET-1 计;自报热量时未知)
    exercise_name = fields.CharField(max_length=64)
    met = fields.FloatField(null=True)  # 自报热量的表外运动可能未知
    duration_min = fields.FloatField(null=True)  # ≤20min 取距上组实际间隔,否则动作时间
    load_kg = fields.FloatField(null=True)
    reps = fields.IntField(null=True)
    # 归属场次由聚合维护;删场次不动 raw
    session = fields.ForeignKeyField(
        "models.Session", related_name="items", null=True, on_delete=fields.SET_NULL
    )
    input = fields.ForeignKeyField(
        "models.Input",
        related_name="exercise_records",
        null=True,
        on_delete=fields.SET_NULL,
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
    grams = fields.FloatField(null=True)  # 自报总热量没报克数时可空
    dish = fields.CharField(
        max_length=64, null=True
    )  # 所属菜名:同菜成分同名;菜合计现算,不建菜表
    protein = fields.FloatField(null=True)
    fat = fields.FloatField(null=True)
    cho = fields.FloatField(null=True)
    fiber = fields.FloatField(null=True)
    meal = fields.ForeignKeyField(
        "models.Meal", related_name="items", null=True, on_delete=fields.SET_NULL
    )
    input = fields.ForeignKeyField(
        "models.Input",
        related_name="food_records",
        null=True,
        on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "food_records"


class UserFood(Model):
    """用户自定义食物:每100克口径,与官方表同构;查表优先级高于标准表。"""

    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="user_foods", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=64)
    form = fields.CharField(max_length=16, null=True)  # 形态:生/熟/干/水发/即食
    kcal = fields.FloatField()  # 每100克
    protein = fields.FloatField(null=True)
    fat = fields.FloatField(null=True)
    cho = fields.FloatField(null=True)
    fiber = fields.FloatField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_foods"
        unique_together = (("user", "name"),)


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
