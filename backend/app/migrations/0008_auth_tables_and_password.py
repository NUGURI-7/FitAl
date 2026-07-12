from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0007_add_inputs_table")]

    initial = False

    operations = [
        ops.CreateModel(
            name="AuthToken",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                ("token", fields.CharField(unique=True, max_length=64)),
                (
                    "user",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="auth_tokens",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={
                "table": "auth_tokens",
                "app": "models",
                "pk_attr": "id",
                "table_description": "登录令牌:纯随机不透明串,认人靠查表;长期有效,删行即失效。",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="InviteCode",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                ("code", fields.CharField(unique=True, max_length=32)),
                (
                    "used_by",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="used_by_id",
                        null=True,
                        db_constraint=True,
                        to_field="id",
                        related_name="invite_codes",
                        on_delete=OnDelete.SET_NULL,
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                (
                    "used_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
            ],
            options={
                "table": "invite_codes",
                "app": "models",
                "pk_attr": "id",
                "table_description": "邀请码:管理员脚本直插生成,一人一码,注册消耗即作废(used_at 非空=已用)。",
            },
            bases=["Model"],
        ),
        ops.AddField(
            model_name="User",
            name="password_hash",
            field=fields.CharField(null=True, max_length=128),
        ),
    ]
