from datetime import date

from pawpal_system import Pet, Task


def test_mark_complete_changes_task_status():
    task = Task("Walk", 30)
    today = date(2026, 10, 20)
    assert not task.is_complete_on(today)

    task.mark_complete(today)

    assert task.is_complete_on(today)


def test_add_task_increases_pet_task_count():
    pet = Pet("Biscuit", "dog", 3)
    assert len(pet.get_tasks()) == 0

    pet.add_task(Task("Walk", 30))

    assert len(pet.get_tasks()) == 1


# --- Scheduler ---------------------------------------------------------------

from datetime import time

from pawpal_system import (
    DailyPlan, Owner, Preference, Priority, ScheduledTask, Scheduler, TaskCategory, TimeConstraint,
)

DAY = date(2026, 10, 20)


def make_owner(budget, *pets):
    owner = Owner("Nadia", budget, time(7, 0), time(21, 0))
    for pet in pets:
        owner.add_pet(pet)
    return owner


def shared_breakfast():
    return Task(
        "Breakfast", 10, Priority.HIGH,
        TimeConstraint(time(7, 30), time(7, 40), is_fixed=True),
        category=TaskCategory.FEEDING, shareable=True,
    )


def scheduled(plan):
    return [(i.pet.name, i.task.title) for i in plan.view_tasks()]


def test_shared_tasks_count_once_so_high_priority_task_fits():
    dog, cat = Pet("Biscuit", "dog", 3), Pet("Miso", "cat", 5)
    dog.add_task(shared_breakfast())
    cat.add_task(shared_breakfast())
    dog.add_task(Task("Walk", 40, Priority.HIGH))
    dog.add_task(Task("Brushing", 10, Priority.LOW))

    plan = Scheduler(make_owner(50, dog, cat), DAY).generate_plan()

    assert ("Biscuit", "Walk") in scheduled(plan)
    assert [t.title for t, _, _ in plan.skipped_tasks] == ["Brushing"]
    assert plan.total_minutes() == 50


def test_shared_task_is_free_even_when_budget_is_used_up():
    dog, cat = Pet("Biscuit", "dog", 3), Pet("Miso", "cat", 5)
    dog.add_task(shared_breakfast())
    cat.add_task(shared_breakfast())

    plan = Scheduler(make_owner(10, dog, cat), DAY).generate_plan()

    assert len(plan.items) == 2
    assert plan.total_minutes() == 10


def test_fixed_time_clash_keeps_higher_priority_task():
    cat = Pet("Miso", "cat", 5)
    noon = TimeConstraint(time(12, 0), time(12, 10), is_fixed=True)
    cat.add_task(Task("Nail trim", 10, Priority.LOW, noon))
    cat.add_task(Task("Meds", 10, Priority.HIGH, noon))

    plan = Scheduler(make_owner(60, cat), DAY).generate_plan()

    assert scheduled(plan) == [("Miso", "Meds")]
    assert plan.skipped_tasks[0][2] == "its fixed time (12:00) is already taken"


def test_plan_items_stay_sorted_and_minutes_match_times():
    dog = Pet("Biscuit", "dog", 3)
    dog.add_task(Task("Dinner", 10, Priority.HIGH, TimeConstraint(time(18, 0), time(18, 10), True)))
    dog.add_task(Task("Walk", 30, Priority.MEDIUM))
    dog.add_task(Task("Breakfast", 10, Priority.HIGH, TimeConstraint(time(8, 0), time(8, 10), True)))

    items = Scheduler(make_owner(120, dog), DAY).generate_plan().view_tasks()

    assert [i.start_min for i in items] == sorted(i.start_min for i in items)
    assert all(i.start_min == i.start_time.hour * 60 + i.start_time.minute for i in items)


def test_preference_added_between_plans_is_used():
    dog = Pet("Biscuit", "dog", 3)
    dog.add_task(Task("Walk", 30, category=TaskCategory.WALK))
    owner = make_owner(60, dog)
    scheduler = Scheduler(owner, DAY)
    assert scheduler.generate_plan().items[0].start_time == time(7, 0)

    owner.add_preference(Preference("Evening walks", "evening", categories=[TaskCategory.WALK]))

    assert scheduler.generate_plan().items[0].start_time == time(17, 0)


def test_detect_conflicts_flags_hand_edited_overlap():
    dog = Pet("Biscuit", "dog", 3)
    walk, bath = Task("Walk", 30), Task("Bath", 20)
    plan = Scheduler(make_owner(60, dog), DAY).generate_plan()
    plan.items = [  # out of order on purpose
        ScheduledTask(bath, dog, time(9, 15), time(9, 35)),
        ScheduledTask(walk, dog, time(9, 0), time(9, 30)),
    ]

    conflicts = Scheduler(make_owner(60, dog), DAY).detect_conflicts(plan)

    assert conflicts == ["'Walk' (Biscuit, 09:00-09:30) overlaps 'Bath' (Biscuit, 09:15-09:35)"]


def test_sort_by_time_orders_by_start_then_end():
    dog = Pet("Biscuit", "dog", 3)
    late = ScheduledTask(Task("Dinner", 10), dog, time(18, 0), time(18, 10))
    long_early = ScheduledTask(Task("Walk", 45), dog, time(8, 0), time(8, 45))
    short_early = ScheduledTask(Task("Breakfast", 10), dog, time(8, 0), time(8, 10))

    result = Scheduler(make_owner(60, dog), DAY).sort_by_time([late, long_early, short_early])

    assert [i.task.title for i in result] == ["Breakfast", "Walk", "Dinner"]


def test_generated_plan_is_chronological_regardless_of_insertion_order():
    dog, cat = Pet("Biscuit", "dog", 3), Pet("Miso", "cat", 5)
    dog.add_task(fixed("Dinner", 18))
    cat.add_task(Task("Play", 20, Priority.LOW))
    dog.add_task(Task("Walk", 30, Priority.HIGH, TimeConstraint(time(9, 0), time(11, 0))))
    cat.add_task(fixed("Breakfast", 7, 30))
    dog.add_task(Task("Brushing", 15))

    scheduler = Scheduler(make_owner(180, dog, cat), DAY)
    items = scheduler.generate_plan().view_tasks()

    assert len(items) == 5
    assert [(i.start_min, i.end_min) for i in items] == sorted((i.start_min, i.end_min) for i in items)
    assert all(a.end_min <= b.start_min for a, b in zip(items, items[1:]))  # nothing shareable
    assert scheduler.sort_by_time(items) == items


def test_add_item_keeps_plan_chronological_and_ties_in_insertion_order():
    dog = Pet("Biscuit", "dog", 3)
    plan = DailyPlan(DAY)
    for title, hour in [("Dinner", 18), ("Breakfast", 8), ("Lunch", 12), ("Meds", 8)]:
        plan.add_item(ScheduledTask(Task(title, 10), dog, time(hour), time(hour, 10)))

    assert [i.task.title for i in plan.view_tasks()] == ["Breakfast", "Meds", "Lunch", "Dinner"]


def test_sort_by_time_returns_new_list_and_handles_empty():
    dog = Pet("Biscuit", "dog", 3)
    scheduler = Scheduler(make_owner(60, dog), DAY)
    items = [
        ScheduledTask(Task("Dinner", 10), dog, time(18, 0), time(18, 10)),
        ScheduledTask(Task("Breakfast", 10), dog, time(8, 0), time(8, 10)),
    ]

    result = scheduler.sort_by_time(items)

    assert [i.task.title for i in result] == ["Breakfast", "Dinner"]
    assert [i.task.title for i in items] == ["Dinner", "Breakfast"]  # input untouched
    assert scheduler.sort_by_time([]) == []


# --- Recurring tasks ---------------------------------------------------------

from datetime import timedelta

from pawpal_system import Frequency


def test_completing_daily_task_creates_next_days_instance():
    dog = Pet("Biscuit", "dog", 3)
    walk = Task("Walk", 30, Priority.HIGH)
    dog.add_task(walk)
    owner = make_owner(60, dog)

    upcoming = Scheduler(owner, DAY).complete_task(dog, walk)

    assert upcoming.due_date == DAY + timedelta(days=1)
    assert upcoming.completed_dates == set()
    assert (upcoming.title, upcoming.duration_minutes, upcoming.priority) == ("Walk", 30, Priority.HIGH)
    assert walk.due_date == DAY and walk.is_complete_on(DAY)
    assert Scheduler(owner, DAY).generate_plan().items == []
    tomorrow = Scheduler(owner, DAY + timedelta(days=1)).generate_plan()
    assert [i.task for i in tomorrow.items] == [upcoming]  # once, not twice


def test_completing_weekly_task_creates_next_weeks_instance():
    cat = Pet("Miso", "cat", 5)
    flea = Task("Flea treatment", 5, frequency=Frequency.WEEKLY, weekday=DAY.weekday())
    cat.add_task(flea)

    upcoming = Scheduler(make_owner(60, cat), DAY).complete_task(cat, flea)

    assert upcoming.due_date == DAY + timedelta(days=7)
    assert upcoming.due_date.weekday() == DAY.weekday()


def test_weekly_task_finished_late_still_recurs_on_its_weekday():
    cat = Pet("Miso", "cat", 5)
    flea = Task("Flea treatment", 5, frequency=Frequency.WEEKLY, due_date=DAY)  # a Tuesday
    cat.add_task(flea)

    upcoming = Scheduler(make_owner(60, cat), DAY).complete_task(cat, flea, on=DAY + timedelta(days=2))

    assert upcoming.due_date == date(2026, 10, 27)  # the following Tuesday


def test_completing_twice_on_same_day_does_not_duplicate():
    dog = Pet("Biscuit", "dog", 3)
    walk = Task("Walk", 30)
    dog.add_task(walk)
    scheduler = Scheduler(make_owner(60, dog), DAY)

    scheduler.complete_task(dog, walk)

    assert scheduler.complete_task(dog, walk) is None
    assert len(dog.get_tasks()) == 2


def test_recurring_instances_share_a_title_but_not_a_due_date():
    dog = Pet("Biscuit", "dog", 3)
    dog.add_task(Task("Walk", 30, due_date=DAY))
    dog.add_task(Task("Walk", 30, due_date=DAY + timedelta(days=1)))

    try:
        dog.add_task(Task("walk", 30, due_date=DAY))
        assert False, "duplicate instance should be rejected"
    except ValueError:
        pass

    dog.remove_task("Walk")
    assert dog.get_tasks() == []


def test_missed_instance_carries_forward_until_done():
    dog = Pet("Biscuit", "dog", 3)
    walk = Task("Walk", 30, due_date=DAY)
    dog.add_task(walk)
    owner = make_owner(60, dog)
    later = DAY + timedelta(days=2)

    plan = Scheduler(owner, later).generate_plan()

    assert [i.task for i in plan.items] == [walk]
    assert "overdue since Tue Oct 20" in plan.items[0].reason

    upcoming = Scheduler(owner, later).complete_task(dog, walk)

    assert upcoming.due_date == later + timedelta(days=1)
    assert not walk.is_due_on(later + timedelta(days=1))
    next_day = Scheduler(owner, later + timedelta(days=1)).generate_plan()
    assert [i.task for i in next_day.items] == [upcoming]


def test_daily_recurrence_rolls_over_month_and_year():
    dog = Pet("Biscuit", "dog", 3)
    walk = Task("Walk", 30)
    dog.add_task(walk)
    new_years_eve = date(2026, 12, 31)

    upcoming = Scheduler(make_owner(60, dog), new_years_eve).complete_task(dog, walk)

    assert upcoming.due_date == date(2027, 1, 1)


def test_completing_each_daily_instance_keeps_exactly_one_due_per_day():
    dog = Pet("Biscuit", "dog", 3)
    dog.add_task(Task("Walk", 30))
    owner = make_owner(60, dog)

    for offset in range(3):
        day = DAY + timedelta(days=offset)
        scheduler = Scheduler(owner, day)
        [item] = scheduler.generate_plan().items  # exactly one walk due today
        upcoming = scheduler.complete_task(dog, item.task)
        assert upcoming.due_date == day + timedelta(days=1)

    assert sorted(t.due_date for t in dog.get_tasks()) == [DAY + timedelta(days=n) for n in range(4)]


# --- Conflict detection ------------------------------------------------------

def fixed(title, hour, minute=0, duration=10, priority=Priority.MEDIUM, shareable=False):
    end = time(hour, minute + duration)
    return Task(title, duration, priority, TimeConstraint(time(hour, minute), end, True), shareable=shareable)


def test_same_pet_clash_warns_instead_of_crashing():
    cat = Pet("Miso", "cat", 5)
    cat.add_task(fixed("Meds", 12, duration=5, priority=Priority.HIGH))
    cat.add_task(fixed("Nail trim", 12))

    plan = Scheduler(make_owner(60, cat), DAY).generate_plan()

    assert plan.warnings == [
        "Time conflict: 'Meds' (Miso, 12:00-12:05) overlaps 'Nail trim' (Miso, 12:00-12:10); "
        "only one can be scheduled"
    ]
    assert scheduled(plan) == [("Miso", "Meds")]


def test_different_pets_clash_warns():
    dog, cat = Pet("Biscuit", "dog", 3), Pet("Miso", "cat", 5)
    dog.add_task(fixed("Dinner", 18))
    cat.add_task(fixed("Vet call", 18, 5, duration=15))  # 18:05-18:20, partial overlap

    plan = Scheduler(make_owner(60, dog, cat), DAY).generate_plan()

    assert len(plan.warnings) == 1
    assert "'Dinner' (Biscuit, 18:00-18:10) overlaps 'Vet call' (Miso, 18:05-18:20)" in plan.warnings[0]


def test_no_warning_for_shareable_flexible_or_back_to_back_tasks():
    dog, cat = Pet("Biscuit", "dog", 3), Pet("Miso", "cat", 5)
    dog.add_task(fixed("Breakfast", 7, 30, shareable=True))
    cat.add_task(fixed("Breakfast", 7, 30, shareable=True))
    dog.add_task(fixed("Meds", 7, 40))  # starts right as breakfast ends
    dog.add_task(Task("Walk", 30))      # flexible, can move

    plan = Scheduler(make_owner(120, dog, cat), DAY).generate_plan()

    assert plan.warnings == []
    assert len(plan.items) == 4


def test_identical_fixed_times_for_different_pets_are_flagged():
    dog, cat = Pet("Biscuit", "dog", 3), Pet("Miso", "cat", 5)
    dog.add_task(fixed("Dinner", 18))
    cat.add_task(fixed("Dinner", 18))

    plan = Scheduler(make_owner(60, dog, cat), DAY).generate_plan()

    assert plan.warnings == [
        "Time conflict: 'Dinner' (Biscuit, 18:00-18:10) overlaps 'Dinner' (Miso, 18:00-18:10); "
        "only one can be scheduled"
    ]
    assert scheduled(plan) == [("Biscuit", "Dinner")]
    assert [(t.title, p.name) for t, p, _ in plan.skipped_tasks] == [("Dinner", "Miso")]


def test_shareable_tasks_at_same_time_for_same_pet_are_still_flagged():
    dog = Pet("Biscuit", "dog", 3)
    dog.add_task(fixed("Breakfast", 7, 30, shareable=True))
    dog.add_task(fixed("Meds", 7, 30, shareable=True))

    plan = Scheduler(make_owner(60, dog), DAY).generate_plan()

    assert len(plan.warnings) == 1
    assert len(plan.items) == 1


def test_three_tasks_at_same_time_flag_every_pair():
    cat = Pet("Miso", "cat", 5)
    for title in ("Meds", "Nail trim", "Brushing"):
        cat.add_task(fixed(title, 12))

    plan = Scheduler(make_owner(60, cat), DAY).generate_plan()

    assert len(plan.warnings) == 3
    assert len(plan.items) == 1


def test_detect_conflicts_flags_identical_times_in_hand_edited_plan():
    dog = Pet("Biscuit", "dog", 3)
    scheduler = Scheduler(make_owner(60, dog), DAY)
    plan = scheduler.generate_plan()
    plan.items = [
        ScheduledTask(Task("Walk", 30), dog, time(9, 0), time(9, 30)),
        ScheduledTask(Task("Bath", 30), dog, time(9, 0), time(9, 30)),
    ]

    assert scheduler.detect_conflicts(plan) == [
        "'Walk' (Biscuit, 09:00-09:30) overlaps 'Bath' (Biscuit, 09:00-09:30)"
    ]
