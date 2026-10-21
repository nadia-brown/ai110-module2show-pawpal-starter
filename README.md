# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

```
============================================================
Today's Schedule for Nadia - Tuesday, October 20, 2026
============================================================
07:00 - 07:20  Feather wand play (Miso) [medium]
               Why: medium priority
07:30 - 07:40  Breakfast (Biscuit) [high]
               Why: high priority; fixed at 07:30
07:30 - 07:40  Breakfast (Miso) [high]
               Why: high priority; fixed at 07:30; done alongside Biscuit's breakfast
09:00 - 09:15  Brushing (Biscuit) [low]
               Why: low priority; must happen between 09:00 and 10:00
12:00 - 12:05  Thyroid meds (Miso) [high]
               Why: high priority; fixed at 12:00
17:00 - 17:45  Walk (Biscuit) [high]
               Why: high priority; matches preference: Biscuit likes evening walks
```
## Implementation Summary 

An Owner can register one or more Pet objects. An Owner can also customize Preference objects to control scheduling.

A Pet maintains a list of Task objects. These Tasks can include a TimeConstarint object that defines when activities should occur. 

The scheduler collets taks from the owner and determines which tasks need to be completed and when they can be scheduled and creates a DailyPlan. 

## Smart Scheduling 

### Sorting
Scheduler.sort_by_time(items): Organizes scheduled tasks in time order   

### Filtering 
Scheduler.filter_tasks(tasks): Filters tasks by date 

### Conflict Detection 
Scheduler.detect_time_conflicts(tasks):
Warns when tasks have overlapping times for the same pet or different pets 

Scheduler.clashes(enteries): Takes a lists of tasks and returns pairs that have taks with overlapping times. 

### Recurring Task Logic 
Task.is_due_on(day): Determines whether a tasks is due on a given day

Task.next_due_date(after): Determines the next due date

Task.next_occurrence(completed_on): makes a new copy of the dasks with a new due date

Task.is_overdue_on(day): Determines if the due date has passed 

Scheduler.complete_tasks(pet, task, on): Marks a task as complete.

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | | e.g., by priority, duration |
| Filtering | | e.g., skip tasks if time runs out |
| Conflict handling | | e.g., overlapping time slots |
| Recurring tasks | | e.g., daily vs. weekly |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
