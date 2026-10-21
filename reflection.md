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

Yes there were some logic issues.  There was output logic that was either duplicated or hardcoded. This was cleaned up with code refactoring. 
 
---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?

The constrains the schuedule considers is priority. The tasks with the highest priority will be added the the schedule first, with the other rankings following behind.  


- How did you decide which constraints mattered most?

I determined the constraits that mattered the most based on the initial UI design. 

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

In the browser I tested scheduling by priority, for a user with multiple pets. I created multiple tasks for each pet with different priority rankings, and times for each tasks.   

I observed that the test revealed that the tasks with the highest ranking were added to the schedule first, followed by tasks with the next highest priority. 

I also obeserved the time for each task was taken into consideration. This revealed that the time alloted for each task was also conidered. 


- Why were these tests important?

These tests are important because there are several factors that need to be considered when scheduling a task. These factors are the task priority, time required  for the task and the time alloted for the day. 

If a task reqires more time, and is low priority it will be skipped. 

**b. Confidence**

I am fairly confident that it works correctly. Although if more time allowed I would implemented the features differently.  

- What edge cases would you test next if you had more time?

Edge cases I would consider would be if a pet had more than one owner. 

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

I am satisified with my test coverage. I feel that I covered either all or most of the areas that would affect task scheduling like priority, time allotted, and total time for all tasks. 

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

I would account for if multiple pet owners, and add a task completed list. 
This may introduce more complexity, but it is a realistic scenario. 

For example, if there are two owners of the same pet, a task like "morning walk" could be completed by more than one person. If a pet has already completed their "morning walk" that task can be removed from the to-do  lists and be marked as "completed".  

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

AI can sometimes overcompicated or over-engineer a project. It is a good idea to relect on the design choices. 
