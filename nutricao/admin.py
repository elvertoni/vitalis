from django.contrib import admin

from .models import DailyLog, Diet, Food, Meal, MealItem, WeightLog


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'calories', 'protein_g', 'carbs_g', 'fat_g']
    search_fields = ['name', 'user__email']


class MealInline(admin.TabularInline):
    model = Meal
    extra = 0


@admin.register(Diet)
class DietAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'goal', 'is_active', 'daily_calorie_target']
    list_filter = ['goal', 'is_active']
    search_fields = ['name', 'user__email']
    inlines = [MealInline]


class MealItemInline(admin.TabularInline):
    model = MealItem
    extra = 0


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ['name', 'diet', 'user', 'time']
    inlines = [MealItemInline]


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ['date', 'meal_name', 'food', 'quantity_g', 'user']
    list_filter = ['date']
    search_fields = ['user__email', 'food__name']


@admin.register(WeightLog)
class WeightLogAdmin(admin.ModelAdmin):
    list_display = ['date', 'weight_kg', 'user']
    list_filter = ['date']
    search_fields = ['user__email']
