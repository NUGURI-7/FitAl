from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields
from tortoise.migrations.constraints import UniqueConstraint


class Migration(migrations.Migration):
    dependencies = [("models", "0010_clarify_pending")]

    initial = False

    operations = [
        ops.AddField(
            model_name="FoodRecord",
            name="unit",
            field=fields.CharField(null=True, max_length=8),
        ),
        ops.RemoveConstraint(
            model_name="UserFood",
            name=None,
            fields=["user", "name"],
        ),
        ops.AlterModelOptions(
            name="UserFood",
            options={
                "table": "user_foods",
                "app": "models",
                "unique_together": (("user", "name", "unit"),),
                "pk_attr": "id",
                "table_description": "用户自定义食物:查表优先级高于标准表。两种口径二选一——",
            },
        ),
        ops.AlterField(
            model_name="UserFood",
            name="kcal",
            field=fields.FloatField(null=True),
        ),
        ops.AddField(
            model_name="UserFood",
            name="kcal_per_unit",
            field=fields.FloatField(null=True),
        ),
        # 量词列分三步落:直接加非空列会被已有行卡住(自动生成的 DDL 不带 DEFAULT,
        # 存量行填不进值)。先加可空列 → 回填空串 → 再收紧为非空。
        ops.AddField(
            model_name="UserFood",
            name="unit",
            field=fields.CharField(null=True, max_length=8),
        ),
        ops.RunSQL(
            "UPDATE user_foods SET unit = '' WHERE unit IS NULL",
            reverse_sql="",
        ),
        ops.AlterField(
            model_name="UserFood",
            name="unit",
            field=fields.CharField(default="", max_length=8),
        ),
        ops.AddConstraint(
            model_name="UserFood",
            constraint=UniqueConstraint(fields=("user", "name", "unit"), name=None),
        ),
    ]
