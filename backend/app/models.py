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
    )  # pending | ok | partial | failed | need_clarify
    ai_rounds = fields.JSONField(null=True)  # {轮名: 原始输出} 错例回放用
    # 待澄清(2026-07-12 澄清表单):段原话+问题清单+专科半成品——补交要用的
    # 业务数据,与 ai_rounds 日志分工不混;补交成功后清空。无状态标识路线:
    # 两次请求间服务器零记忆,唯一共享上下文就是这一行
    pending_clarify = fields.JSONField(null=True)
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
    food_name = fields.CharField(max_length=64)  # 成分表学名:改克数回查表重算、展示用
    spoken_name = fields.CharField(
        max_length=64, null=True
    )  # 用户的原话叫法:个人食物库按它精确命中,沉淀时用它当条目名
    grams = fields.FloatField(null=True)  # 自报总热量没报克数时可空
    unit = fields.CharField(
        max_length=8, null=True
    )  # 用户说的量词(碗/根/份/个/杯),照抄原话;没用量词为空
    unit_count = fields.IntField(
        null=True
    )  # 该量词的数量("两碗面"=2);沉淀时用它还原单份热量
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
    """用户自定义食物:查表优先级高于标准表。两种口径二选一——

    量词为空 = 每100克口径(与官方表同构,kcal 有值);
    量词有值 = 按份口径(如"一碗=550千卡",kcal_per_unit 有值,不谈克数)。
    整份食物(一碗面/一份肠粉)的克数是模型倒填的,不可信,故不作分母。
    """

    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="user_foods", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=64)
    # 量词:碗/根/份;空串=每100克口径。不可空是刻意的——两方言的唯一约束都
    # 把 NULL 视为互不相等,可空会让"重复记住即更新"退化成插多条
    unit = fields.CharField(max_length=8, default="")
    form = fields.CharField(max_length=16, null=True)  # 形态:生/熟/干/水发/即食
    kcal = fields.FloatField(null=True)  # 每100克(量词为空时有值)
    kcal_per_unit = fields.FloatField(null=True)  # 一个该量词多少千卡(量词有值时)
    protein = fields.FloatField(null=True)
    fat = fields.FloatField(null=True)
    cho = fields.FloatField(null=True)
    fiber = fields.FloatField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_foods"
        unique_together = (("user", "name", "unit"),)


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
