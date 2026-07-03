from datetime import datetime

from app.models import FoodRecord, Meal, User


async def test_七张表模型_可建用户与饮食记录并归入餐次(db):
    user = await User.create(
        nickname="测试", height_cm=178, sex="male", birth_year=1997
    )
    meal = await Meal.create(
        user=user,
        name="午餐",
        start=datetime(2026, 7, 2, 12, 3),
        end=datetime(2026, 7, 2, 12, 6),
        kcal_total=371,
    )
    await FoodRecord.create(
        user=user,
        raw_text="米饭200g",
        source="food_table",
        kcal=232,
        food_name="米饭(蒸)",
        grams=200,
        meal=meal,
    )
    await FoodRecord.create(
        user=user,
        raw_text="鸡蛋100g",
        source="food_table",
        kcal=139,
        food_name="鸡蛋(代表值)",
        grams=100,
        meal=meal,
    )

    items = await meal.items.all()
    assert len(items) == 2
    assert sum(i.kcal for i in items) == 371


async def test_删除餐次_raw记录保留仅解除归属(db):
    user = await User.create(
        nickname="测试2", height_cm=165, sex="female", birth_year=2000
    )
    meal = await Meal.create(
        user=user,
        start=datetime(2026, 7, 2, 12, 0),
        end=datetime(2026, 7, 2, 12, 0),
    )
    record = await FoodRecord.create(
        user=user,
        raw_text="鸡蛋100g",
        source="food_table",
        kcal=139,
        food_name="鸡蛋(代表值)",
        grams=100,
        meal=meal,
    )

    await meal.delete()
    await record.refresh_from_db()
    assert record.meal_id is None  # raw 是唯一事实源,new 层删除不伤 raw
