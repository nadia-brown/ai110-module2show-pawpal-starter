# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

The classes I created are Scheduler, Owner, DailyPlan, Preference, ScheduledTask, Preference, Pet, Task, Priority, and TimeConstraint

The Owner class is responsible for add and remove a pet, get a pet by name, add preferences and get all tasks. 

The Pet class is responsible for adding and removing taks, and getting all tasks. 

The Tasks class is responsible for marking a task comlete, it can display whether the task has a time constraint, and assign a task a priority score.  

The Scheduler class is responible for generating the daily plan, sorting tasks, filtering tasks, finding tasks by time, and determining if there are conflicts. 

The DailyPlan class is responsible for adding task items, and displaying tasks. 


**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes there are logic issues. A fixed taks can be moved off it's fixed time. 
 
---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

Removing the early exit recommendation from Claude Code. The `sortest_after = list(accumulate(reversed(...), min))[::-1]` is the most difficult line to read in the file with minimal benefit.  

The early exit creates a shortcut for checking if there is enough time to complete the task. If so the task is added to the daily task list. If not it gets skipped. 

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

Claude Code suggested adding an additional class called SkippedTasks for all the tasks that were skipped in the daily plan.

 I determined addind a seperate class to track tasks that could not be scheduled would introduce unnecessary complexity and potentially errors into this project. 

I rejectd Claude Code's design after evaluating whether an additional class was necessary for the current requirements and decided not to include it. 
---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
