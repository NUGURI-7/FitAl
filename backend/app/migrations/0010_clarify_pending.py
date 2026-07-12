from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0009_username_split_from_nickname")]

    initial = False

    operations = [
        ops.AddField(
            model_name="Input",
            name="pending_clarify",
            field=fields.JSONField(
                null=True,
                encoder=functools.partial(dumps, separators=(",", ":")),
                decoder=loads,
            ),
        ),
    ]
