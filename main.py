"""Demo script: build an owner with pets and tasks, then print today's schedule."""

from datetime import date, time

from pawpal_system import (
    Owner,
    Pet,
    Preference,
    Priority,
    Scheduler,
    Task,
    TaskCategory,
    TimeConstraint,
    format_time,
)


def build_owner() -> Owner:
    """Create a sample owner with two pets and their care tasks."""
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

    # Breakfast for both pets at 7:30; shareable, so they can happen together.
    biscuit.add_task(Task(
        "Breakfast", 10, Priority.HIGH,
        TimeConstraint(time(7, 30), time(7, 40), is_fixed=True),
        category=TaskCategory.FEEDING, shareable=True,
    ))
    miso.add_task(Task(
        "Breakfast", 10, Priority.HIGH,
        TimeConstraint(time(7, 30), time(7, 40), is_fixed=True),
        category=TaskCategory.FEEDING, shareable=True,
    ))

    # Miso's medicine has to happen at exactly noon.
    miso.add_task(Task(
        "Thyroid meds", 5, Priority.HIGH,
        TimeConstraint(time(12, 0), time(12, 5), is_fixed=True),
        category=TaskCategory.MEDS,
    ))

    # Flexible tasks: the scheduler picks the time.
    biscuit.add_task(Task("Walk", 45, Priority.HIGH, category=TaskCategory.WALK))
    biscuit.add_task(Task(
        "Brushing", 15, Priority.LOW,
        TimeConstraint(time(9, 0), time(10, 0)),
        category=TaskCategory.GROOMING,
    ))
    miso.add_task(Task("Feather wand play", 20, Priority.MEDIUM, category=TaskCategory.ENRICHMENT))

    return owner


def print_schedule(owner: Owner) -> None:
    """Generate today's plan and print it to the terminal."""
    plan = Scheduler(owner, date.today()).generate_plan()

    print("=" * 60)
    print(f"Today's Schedule for {owner.name} - {plan.plan_date.strftime('%A, %B %d, %Y')}")
    print("=" * 60)

    if not plan.items:
        print("Nothing scheduled today.")
    for item in plan.view_tasks():
        print(
            f"{format_time(item.start_time)} - {format_time(item.end_time)}  "
            f"{item.task.title} ({item.pet.name}) [{item.task.priority.name.lower()}]"
        )
        print(f"               Why: {item.reason}")

    if plan.skipped_tasks:
        print("\nSkipped today:")
        for task, pet, reason in plan.skipped_tasks:
            print(f"  - {task.title} ({pet.name}): {reason}")

    print("-" * 60)
    print(f"Total time: {plan.total_minutes()} of {owner.available_minutes} available minutes")


if __name__ == "__main__":
    print_schedule(build_owner())
