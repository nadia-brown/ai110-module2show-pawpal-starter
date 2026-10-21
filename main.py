"""Demo script: add tasks out of order, then show filtering, sorting, and today's schedule."""

import random
from datetime import date, time, timedelta

from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Preference,
    Priority,
    ScheduledTask,
    Scheduler,
    Task,
    TaskCategory,
    TimeConstraint,
    format_time,
)

# A fixed date keeps the demo repeatable (weekly tasks depend on the weekday).
DEMO_DATE = date(2026, 10, 20)  # a Tuesday
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def build_owner() -> Owner:
    """Create a sample owner with two pets, adding their tasks in no particular time order."""
    owner = Owner(name="Nadia", available_minutes=180, day_start=time(7, 0), day_end=time(21, 0))

    biscuit = Pet(name="Biscuit", species="dog", age=3)
    miso = Pet(name="Miso", species="cat", age=5)
    owner.add_pet(biscuit)
    owner.add_pet(miso)

    owner.add_preference(Preference(
        description="Biscuit likes evening walks",
        preferred_time_of_day="evening",
        weight=3,
        categories=[TaskCategory.WALK],
        pet_name="Biscuit",
    ))

    # Added out of order on purpose: evening, flexible, morning, mid-morning...
    biscuit.add_task(Task(
        "Dinner", 10, Priority.HIGH,
        TimeConstraint(time(18, 0), time(18, 10), is_fixed=True),
        category=TaskCategory.FEEDING,
    ))
    biscuit.add_task(Task("Walk", 45, Priority.HIGH, category=TaskCategory.WALK))
    biscuit.add_task(Task(
        "Breakfast", 10, Priority.HIGH,
        TimeConstraint(time(7, 30), time(7, 40), is_fixed=True),
        category=TaskCategory.FEEDING, shareable=True,
    ))
    biscuit.add_task(Task(
        "Brushing", 15, Priority.LOW,
        TimeConstraint(time(9, 0), time(10, 0)),
        category=TaskCategory.GROOMING,
    ))
    biscuit.add_task(Task(
        "Flea treatment", 5, Priority.MEDIUM,
        category=TaskCategory.MEDS, frequency=Frequency.WEEKLY, weekday=1,  # Tuesdays
    ))

    miso.add_task(Task(
        "Thyroid meds", 5, Priority.HIGH,
        TimeConstraint(time(12, 0), time(12, 5), is_fixed=True),
        category=TaskCategory.MEDS,
    ))
    miso.add_task(Task("Feather wand play", 20, Priority.MEDIUM, category=TaskCategory.ENRICHMENT))
    # Two deliberate clashes for the conflict check:
    # same pet (Miso's meds are also at 12:00) and different pets (Biscuit's dinner is at 18:00).
    miso.add_task(Task(
        "Nail trim", 10, Priority.LOW,
        TimeConstraint(time(12, 0), time(12, 10), is_fixed=True),
        category=TaskCategory.GROOMING,
    ))
    miso.add_task(Task(
        "Dinner", 10, Priority.HIGH,
        TimeConstraint(time(18, 0), time(18, 10), is_fixed=True),
        category=TaskCategory.FEEDING,
    ))
    miso.add_task(Task(
        "Breakfast", 10, Priority.HIGH,
        TimeConstraint(time(7, 30), time(7, 40), is_fixed=True),
        category=TaskCategory.FEEDING, shareable=True,
    ))
    miso.add_task(Task(
        "Litter deep-clean", 30, Priority.MEDIUM,
        category=TaskCategory.OTHER, frequency=Frequency.WEEKLY, weekday=5,  # Saturdays
    ))
    teeth = Task("Brush teeth", 5, Priority.LOW, category=TaskCategory.GROOMING)
    teeth.mark_complete(DEMO_DATE)  # already done today
    miso.add_task(teeth)

    return owner


def header(title: str) -> None:
    """Print a section title underlined to its own width."""
    print(f"\n{title}\n{'-' * len(title)}")


def describe(task: Task) -> str:
    """One-line summary of a task's timing rules."""
    tc = task.time_constraint
    if tc is None:
        when = "any time"
    elif tc.is_fixed:
        when = f"at {format_time(tc.earliest_start)}"
    else:
        when = f"{format_time(tc.earliest_start)}-{format_time(tc.latest_end)}"
    if task.frequency is Frequency.WEEKLY:
        when += f", weekly on {WEEKDAYS[task.weekday]}"
    return f"{task.duration_minutes:>3} min, {when}"


def print_tasks(pairs: list[tuple[Pet, Task]]) -> None:
    """Print one line per task: title, pet, priority, duration, and timing rules."""
    for pet, task in pairs:
        print(f"  {task.title + ' (' + pet.name + ')':<30} [{task.priority.name.lower():<6}] {describe(task)}")


def print_items(items: list[ScheduledTask], with_reasons: bool = False) -> None:
    """Print scheduled tasks in the given order, optionally with the reason for each slot."""
    for item in items:
        print(f"  {format_time(item.start_time)}-{format_time(item.end_time)}  {item.task.title} ({item.pet.name})")
        if with_reasons:
            print(f"               Why: {item.reason}")


def main() -> None:
    """Run the demo: list, filter, sort, schedule, check conflicts, and complete tasks."""
    owner = build_owner()
    scheduler = Scheduler(owner, DEMO_DATE)
    print("=" * 64)
    print(f"PawPal+ demo for {owner.name} - {DEMO_DATE.strftime('%A, %B %d, %Y')}")
    print("=" * 64)

    all_tasks = owner.get_all_tasks()
    header(f"1. All tasks, in the order they were added ({len(all_tasks)})")
    print_tasks(all_tasks)

    due = scheduler.filter_tasks(all_tasks)
    header(f"2. filter_tasks(): due today and not done yet ({len(due)})")
    print_tasks(due)
    print("  Filtered out:")
    due_ids = {id(task) for _, task in due}  # by identity: both Breakfasts compare equal
    for pet, task in all_tasks:
        if id(task) not in due_ids:
            why = "already completed today" if task.is_complete_on(DEMO_DATE) else "not due today"
            print(f"    - {task.title} ({pet.name}): {why}")

    header("3. sort_tasks(): most important first (score, then shortest)")
    for pet, task in scheduler.sort_tasks(due):
        print(f"  score {scheduler.score_task(task, pet):>2}  {task.title} ({pet.name}), {task.duration_minutes} min")

    plan = scheduler.generate_plan()
    header("4. Conflict check: tasks asking for the same time")
    if plan.warnings:
        for warning in plan.warnings:
            print(f"  WARNING: {warning}")
    else:
        print("  No conflicts.")

    shuffled = plan.view_tasks()
    random.Random(7).shuffle(shuffled)  # scramble to show sort_by_time doing the work
    header("5. Scheduled tasks, scrambled")
    print_items(shuffled)

    header("6. sort_by_time(): today's schedule in time order")
    print_items(scheduler.sort_by_time(shuffled), with_reasons=True)
    if plan.skipped_tasks:
        print("\n  Skipped today:")
        for task, pet, reason in plan.skipped_tasks:
            print(f"    - {task.title} ({pet.name}): {reason}")

    print("-" * 64)
    print(f"Total time: {plan.total_minutes()} of {owner.available_minutes} available minutes")

    header("7. complete_task(): finishing recurring tasks creates the next instance")
    biscuit = owner.get_pet("Biscuit")
    for title in ("Walk", "Flea treatment"):
        task = next(t for t in biscuit.get_tasks() if t.title == title)
        upcoming = scheduler.complete_task(biscuit, task)
        print(f"  Done: {title} ({task.frequency.value}) -> next one due "
              f"{upcoming.due_date.strftime('%a %b %d')}")

    for day in (DEMO_DATE + timedelta(days=1), DEMO_DATE + timedelta(days=7)):
        due_titles = [
            t.title + (" (overdue)" if t.is_overdue_on(day) else "")
            for _, t in Scheduler(owner, day).filter_tasks(biscuit_tasks(owner))
        ]
        print(f"  Biscuit's tasks due {day.strftime('%a %b %d')}: {', '.join(due_titles)}")


def biscuit_tasks(owner: Owner) -> list[tuple[Pet, Task]]:
    """Return the (pet, task) pairs that belong to Biscuit."""
    return [(pet, task) for pet, task in owner.get_all_tasks() if pet.name == "Biscuit"]


if __name__ == "__main__":
    main()
