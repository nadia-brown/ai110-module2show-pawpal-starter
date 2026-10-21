"""PawPal+ core system, based on diagrams/uml.mmd.

An Owner has Pets; each Pet has care Tasks. The Scheduler builds a
DailyPlan from those tasks using time constraints, priority, and preferences.

Times are stored as datetime.time for readability, but all scheduling math is
done in "minutes since midnight" (plain ints), since datetime.time does not
support arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Optional


# --- Time helpers ---------------------------------------------------------

def to_minutes(t: time) -> int:
    """Convert a time to minutes since midnight."""
    return t.hour * 60 + t.minute


def from_minutes(minutes: int) -> time:
    """Convert minutes since midnight back to a time (clamped to 23:59)."""
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return time(minutes // 60, minutes % 60)


def format_time(t: time) -> str:
    """Format a time as HH:MM."""
    return t.strftime("%H:%M")


# Windows used by Preference.preferred_time_of_day, as (start, end) minutes.
TIME_OF_DAY_WINDOWS: dict[str, tuple[int, int]] = {
    "morning": (6 * 60, 12 * 60),
    "afternoon": (12 * 60, 17 * 60),
    "evening": (17 * 60, 22 * 60),
}


# --- Model ----------------------------------------------------------------

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TaskCategory(Enum):
    WALK = "walk"
    FEEDING = "feeding"
    MEDS = "meds"
    GROOMING = "grooming"
    ENRICHMENT = "enrichment"
    OTHER = "other"


class Frequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class TimeConstraint:
    earliest_start: time
    latest_end: time
    is_fixed: bool = False  # if True, the task must start exactly at earliest_start

    def __post_init__(self) -> None:
        if to_minutes(self.earliest_start) >= to_minutes(self.latest_end):
            raise ValueError("earliest_start must be before latest_end.")

    def fits(self, start: time, duration_minutes: int) -> bool:
        """Return True if a task starting at `start` and lasting `duration_minutes` fits this window."""
        start_min = to_minutes(start)
        if self.is_fixed and start_min != to_minutes(self.earliest_start):
            return False
        return (
            start_min >= to_minutes(self.earliest_start)
            and start_min + duration_minutes <= to_minutes(self.latest_end)
        )


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    time_constraint: Optional[TimeConstraint] = None
    category: TaskCategory = TaskCategory.OTHER
    frequency: Frequency = Frequency.DAILY
    weekday: Optional[int] = None  # 0=Monday..6=Sunday; required for WEEKLY tasks
    shareable: bool = False  # can happen at the same time as another pet's shareable task
    completed_dates: set[date] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0:
            raise ValueError("Task duration must be positive.")
        if self.frequency is Frequency.WEEKLY and self.weekday not in range(7):
            raise ValueError("Weekly tasks need a weekday from 0 (Monday) to 6 (Sunday).")

    def mark_complete(self, on: Optional[date] = None) -> None:
        """Mark this task as completed for a given day (today by default)."""
        self.completed_dates.add(on or date.today())

    def is_complete_on(self, day: date) -> bool:
        """Return True if this task was completed on the given day."""
        return day in self.completed_dates

    def is_due_on(self, day: date) -> bool:
        """Return True if this task should happen on the given day."""
        if self.frequency is Frequency.WEEKLY:
            return day.weekday() == self.weekday
        return True

    def has_time_constraint(self) -> bool:
        """Return True if this task has a time constraint."""
        return self.time_constraint is not None

    def is_fixed(self) -> bool:
        """Return True if this task must happen at an exact time."""
        return self.time_constraint is not None and self.time_constraint.is_fixed

    def priority_score(self) -> int:
        """Return a numeric score used for sorting tasks by importance."""
        return self.priority.value


@dataclass
class Pet:
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task for this pet. Task titles must be unique per pet."""
        if any(t.title.lower() == task.title.lower() for t in self.tasks):
            raise ValueError(f"{self.name} already has a task called '{task.title}'.")
        self.tasks.append(task)

    def remove_task(self, task_title: str) -> None:
        """Remove the task with the given title."""
        for i, t in enumerate(self.tasks):
            if t.title.lower() == task_title.lower():
                del self.tasks[i]
                return
        raise ValueError(f"{self.name} has no task called '{task_title}'.")

    def get_tasks(self) -> list[Task]:
        """Return all tasks for this pet."""
        return list(self.tasks)


@dataclass
class Preference:
    description: str
    preferred_time_of_day: str  # "morning", "afternoon", or "evening"
    weight: int = 1
    categories: list[TaskCategory] = field(default_factory=list)
    pet_name: Optional[str] = None  # None means it applies to every pet

    def __post_init__(self) -> None:
        self.preferred_time_of_day = self.preferred_time_of_day.lower()
        if self.preferred_time_of_day not in TIME_OF_DAY_WINDOWS:
            raise ValueError(
                f"preferred_time_of_day must be one of {', '.join(TIME_OF_DAY_WINDOWS)}."
            )

    def applies_to(self, task: Task, pet: Optional[Pet] = None) -> bool:
        """Return True if this preference is relevant to the given task (and pet)."""
        if self.pet_name is not None and (pet is None or pet.name.lower() != self.pet_name.lower()):
            return False
        return task.category in self.categories

    def window(self) -> tuple[int, int]:
        """Return the preferred (start, end) window in minutes."""
        return TIME_OF_DAY_WINDOWS[self.preferred_time_of_day]


@dataclass
class Owner:
    name: str
    available_minutes: int  # total care time budget for the day
    day_start: time         # tasks are only scheduled between day_start and day_end
    day_end: time
    pets: list[Pet] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.available_minutes < 0:
            raise ValueError("available_minutes can't be negative.")
        if to_minutes(self.day_start) >= to_minutes(self.day_end):
            raise ValueError("day_start must be before day_end.")

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner. Pet names must be unique."""
        if self.get_pet(pet.name) is not None:
            raise ValueError(f"{self.name} already has a pet named '{pet.name}'.")
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> None:
        """Remove the pet with the given name."""
        pet = self.get_pet(pet_name)
        if pet is None:
            raise ValueError(f"{self.name} has no pet named '{pet_name}'.")
        self.pets.remove(pet)

    def get_pet(self, pet_name: str) -> Optional[Pet]:
        """Return the pet with the given name, or None if not found."""
        for pet in self.pets:
            if pet.name.lower() == pet_name.lower():
                return pet
        return None

    def add_preference(self, pref: Preference) -> None:
        """Add a scheduling preference."""
        self.preferences.append(pref)

    def get_all_tasks(self) -> list[tuple[Pet, Task]]:
        """Return every (pet, task) pair across all of this owner's pets."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]


@dataclass
class ScheduledTask:
    task: Task
    pet: Pet
    start_time: time
    end_time: time
    reason: str = ""

    def overlaps(self, other: ScheduledTask) -> bool:
        """Return True if this scheduled task's time range overlaps another's."""
        return (
            to_minutes(self.start_time) < to_minutes(other.end_time)
            and to_minutes(other.start_time) < to_minutes(self.end_time)
        )

    def can_share_time_with(self, task: Task, pet: Pet) -> bool:
        """Return True if `task` for `pet` may happen at the same time as this one."""
        return self.task.shareable and task.shareable and self.pet.name != pet.name


@dataclass
class DailyPlan:
    plan_date: date = field(default_factory=date.today)
    items: list[ScheduledTask] = field(default_factory=list)
    skipped_tasks: list[tuple[Task, Pet, str]] = field(default_factory=list)  # (task, pet, reason)

    def add_item(self, item: ScheduledTask) -> None:
        """Add a scheduled task to the plan, keeping items ordered by start time."""
        self.items.append(item)
        self.items.sort(key=lambda i: to_minutes(i.start_time))

    def total_minutes(self) -> int:
        """Return the owner's busy minutes; tasks done at the same time count once."""
        total, busy_until = 0, -1
        for item in self.view_tasks():
            start, end = to_minutes(item.start_time), to_minutes(item.end_time)
            if end > busy_until:
                total += end - max(start, busy_until)
                busy_until = end
        return total

    def view_tasks(self) -> list[ScheduledTask]:
        """Return the scheduled tasks, ordered by start time."""
        return sorted(self.items, key=lambda i: to_minutes(i.start_time))

    def explain(self) -> str:
        """Return a human-readable explanation of why the plan looks the way it does."""
        lines = [f"Plan for {self.plan_date.isoformat()} ({self.total_minutes()} min scheduled):"]
        if not self.items:
            lines.append("  No tasks scheduled.")
        for item in self.view_tasks():
            lines.append(
                f"  {format_time(item.start_time)}-{format_time(item.end_time)}  "
                f"{item.task.title} for {item.pet.name} "
                f"[{item.task.priority.name.lower()}] - {item.reason}"
            )
        if self.skipped_tasks:
            lines.append("Skipped:")
            for task, pet, reason in self.skipped_tasks:
                lines.append(f"  {task.title} for {pet.name} - {reason}")
        return "\n".join(lines)


# --- Scheduling -----------------------------------------------------------

class Scheduler:
    """Builds a DailyPlan in three steps:

    1. Choose tasks that fit the time budget, most important first.
    2. Place the chosen tasks, least flexible first (fixed, then narrow windows),
       so flexible tasks can't take a constrained task's only slot.
    3. Use any budget left over (from unplaced or shared-time tasks) for tasks
       that didn't make the cut in step 1.
    """

    def __init__(self, owner: Owner, plan_date: Optional[date] = None) -> None:
        self.owner = owner
        self.plan_date = plan_date or date.today()

    def generate_plan(self) -> DailyPlan:
        """Build a DailyPlan from the owner's pets, tasks, and preferences."""
        plan = DailyPlan(plan_date=self.plan_date)

        # Drop tasks that can never fit today, whatever else is scheduled.
        feasible = []
        for pet, task in self.filter_tasks(self.owner.get_all_tasks()):
            problem = self._infeasible_reason(task)
            if problem:
                plan.skipped_tasks.append((task, pet, problem))
            else:
                feasible.append((pet, task))

        # 1. Choose by importance within the budget.
        chosen, over_budget = [], []
        budget_left = self.owner.available_minutes
        for pet, task in self.sort_tasks(feasible):
            if task.duration_minutes <= budget_left:
                chosen.append((pet, task))
                budget_left -= task.duration_minutes
            else:
                over_budget.append((pet, task))

        # 2. Place least flexible first.
        chosen.sort(key=lambda pt: (
            not pt[1].is_fixed(),
            not pt[1].has_time_constraint(),
            self._slack(pt[1]),
            -self.score_task(pt[1], pt[0]),
        ))
        for pet, task in chosen:
            if not self._place(task, pet, plan):
                plan.skipped_tasks.append((task, pet, self._no_slot_reason(task)))

        # 3. Fill in with leftover budget.
        for pet, task in over_budget:
            if plan.total_minutes() + task.duration_minutes > self.owner.available_minutes:
                plan.skipped_tasks.append((
                    task, pet,
                    f"not enough time left in the {self.owner.available_minutes}-min budget",
                ))
            elif not self._place(task, pet, plan):
                plan.skipped_tasks.append((task, pet, self._no_slot_reason(task)))

        return plan

    def score_task(self, task: Task, pet: Optional[Pet] = None) -> int:
        """Combine priority with the weights of any preferences that apply to the task."""
        pref_bonus = sum(p.weight for p in self.owner.preferences if p.applies_to(task, pet))
        return task.priority_score() * 10 + pref_bonus

    def sort_tasks(self, tasks: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Order tasks by importance: highest score first, then shortest first."""
        return sorted(tasks, key=lambda pt: (-self.score_task(pt[1], pt[0]), pt[1].duration_minutes))

    def filter_tasks(self, tasks: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Return only tasks that are due on the plan date and not already done that day."""
        return [
            (pet, task) for pet, task in tasks
            if task.is_due_on(self.plan_date) and not task.is_complete_on(self.plan_date)
        ]

    def find_slot(self, task: Task, pet: Pet, plan: DailyPlan) -> Optional[time]:
        """Return the earliest valid start time for a task in the plan, or None if none fits.

        Fixed tasks only ever get their exact time. Other tasks try the pet's
        preferred time-of-day window(s) first, then any allowed time in the day.
        """
        lo, hi = self._window(task)
        windows = []
        if not task.is_fixed():
            for pref in self.owner.preferences:
                if pref.applies_to(task, pet):
                    w_lo, w_hi = pref.window()
                    windows.append((max(lo, w_lo), min(hi, w_hi)))
        windows.append((lo, hi))

        for w_lo, w_hi in windows:
            start = self._earliest_gap(task, pet, w_lo, w_hi, plan)
            if start is not None:
                return from_minutes(start)
        return None

    def detect_conflicts(self, plan: DailyPlan) -> list[str]:
        """Return descriptions of tasks that overlap but aren't allowed to.

        generate_plan() never creates these; this checks plans edited by hand.
        """
        items = plan.view_tasks()
        conflicts = []
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if to_minutes(b.start_time) >= to_minutes(a.end_time):
                    break  # sorted by start, so nothing later can overlap `a`
                if a.overlaps(b) and not a.can_share_time_with(b.task, b.pet):
                    conflicts.append(
                        f"'{a.task.title}' ({a.pet.name}, {format_time(a.start_time)}-"
                        f"{format_time(a.end_time)}) overlaps '{b.task.title}' "
                        f"({b.pet.name}, {format_time(b.start_time)}-{format_time(b.end_time)})"
                    )
        return conflicts

    # --- internal helpers ---

    def _window(self, task: Task) -> tuple[int, int]:
        """Return the (start, end) minutes a task may occupy: the owner's day narrowed by its constraint."""
        lo, hi = to_minutes(self.owner.day_start), to_minutes(self.owner.day_end)
        tc = task.time_constraint
        if tc is None:
            return lo, hi
        if tc.is_fixed:
            start = to_minutes(tc.earliest_start)
            return start, start + task.duration_minutes
        return max(lo, to_minutes(tc.earliest_start)), min(hi, to_minutes(tc.latest_end))

    def _slack(self, task: Task) -> int:
        """Return how many minutes of wiggle room a task has in its window."""
        lo, hi = self._window(task)
        return hi - lo - task.duration_minutes

    def _infeasible_reason(self, task: Task) -> Optional[str]:
        """Return why a task can never be scheduled today, or None if it could be."""
        day = f"{format_time(self.owner.day_start)}-{format_time(self.owner.day_end)}"
        tc = task.time_constraint
        if tc is not None:
            window = f"{format_time(tc.earliest_start)}-{format_time(tc.latest_end)}"
            if not tc.fits(tc.earliest_start, task.duration_minutes):
                return f"its time window ({window}) is shorter than the task"
            lo, hi = self._window(task)
            if tc.is_fixed and (
                lo < to_minutes(self.owner.day_start) or hi > to_minutes(self.owner.day_end)
            ):
                return f"its fixed time ({format_time(tc.earliest_start)}) is outside your day ({day})"
            if hi - lo < task.duration_minutes:
                return f"its time window ({window}) doesn't fit inside your day ({day})"
        elif self._slack(task) < 0:
            return f"it's longer than your whole day ({day})"
        if task.duration_minutes > self.owner.available_minutes:
            return f"it's longer than your {self.owner.available_minutes}-min budget"
        return None

    def _no_slot_reason(self, task: Task) -> str:
        """Explain why a feasible task couldn't be placed in this plan."""
        if task.is_fixed():
            return f"its fixed time ({format_time(task.time_constraint.earliest_start)}) is already taken"
        return "no open time slot fits it"

    def _earliest_gap(
        self, task: Task, pet: Pet, lo: int, hi: int, plan: DailyPlan
    ) -> Optional[int]:
        """Return the earliest start in [lo, hi] where the task fits without a disallowed overlap."""
        duration = task.duration_minutes
        if hi - lo < duration:
            return None
        blocking = [i for i in plan.items if not i.can_share_time_with(task, pet)]
        busy = [(to_minutes(i.start_time), to_minutes(i.end_time)) for i in blocking]
        # A task can only start at the window start or right after a blocking item.
        candidates = sorted({lo} | {end for _, end in busy})
        for start in candidates:
            end = start + duration
            if start < lo or end > hi:
                continue
            tc = task.time_constraint
            if tc is not None and not tc.fits(from_minutes(start), duration):
                continue
            if all(end <= b_start or start >= b_end for b_start, b_end in busy):
                return start
        return None

    def _place(self, task: Task, pet: Pet, plan: DailyPlan) -> bool:
        """Try to schedule a task; return True if it was added to the plan."""
        start = self.find_slot(task, pet, plan)
        if start is None:
            return False
        end = from_minutes(to_minutes(start) + task.duration_minutes)
        item = ScheduledTask(task, pet, start, end)
        shared_with = [i for i in plan.items if i.overlaps(item)]
        item.reason = self._reason(task, pet, start, shared_with)
        plan.add_item(item)
        return True

    def _reason(
        self, task: Task, pet: Pet, start: time, shared_with: list[ScheduledTask]
    ) -> str:
        """Explain why a task landed where it did."""
        parts = [f"{task.priority.name.lower()} priority"]
        tc = task.time_constraint
        if task.is_fixed():
            parts.append(f"fixed at {format_time(tc.earliest_start)}")
        elif tc is not None:
            parts.append(
                f"must happen between {format_time(tc.earliest_start)} and {format_time(tc.latest_end)}"
            )
        if task.frequency is Frequency.WEEKLY:
            parts.append("weekly task")
        if not task.is_fixed():
            for pref in self.owner.preferences:
                if pref.applies_to(task, pet):
                    w_lo, w_hi = pref.window()
                    if w_lo <= to_minutes(start) < w_hi:
                        parts.append(f"matches preference: {pref.description}")
                    else:
                        parts.append(f"couldn't fit preferred {pref.preferred_time_of_day}")
        for other in shared_with:
            parts.append(f"done alongside {other.pet.name}'s {other.task.title.lower()}")
        return "; ".join(parts)
