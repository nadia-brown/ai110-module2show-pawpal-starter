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
