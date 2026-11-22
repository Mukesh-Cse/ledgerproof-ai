# SEB Tech Trainee Programme application notes

## CV project entry

**Payment Change Review | Agentic AI and software delivery research**

Built a transactional SQLite payment ledger and an AI reviewer that turns a reproduced defect into a permanent CI check after human approval. Verified 800 concurrent delivery attempts with 200 correct bookings and 600 suppressed replays. Benchmarked fixed review policies on 24 synthetic changes and designed a blinded pilot to measure agent value and reviewer effort.

## Short application response

I wanted to see whether a coding agent could give a banking engineer something concrete to act on during review. I built a small payment ledger and gave the agent two tests. After a within-account replay passed, the agent changed one field and showed that a legitimate booking disappeared when two accounts shared an event ID. I then used that counterexample to add a CI test that runs without a model. The project pairs that implementation with a 24-case static benchmark and a blinded pilot design. At SEB, I’d like to study which changes justify this extra review step and whether it helps teams learn the payment rules they maintain.

## Interview demo

1. Open the [interactive demo](output/demo/index.html) on **Faulty change**. Show the replay passing, then select **Change account** to show the 850-minor-unit booking that disappears.
2. Switch to **Current ledger** and show the same input booking both payments. Explain why the uniqueness key includes account ID, and why the ledger acquires the write lock before reading that key.
3. Run `python payment_review.py --candidate global-id-regression` and show that the promoted case fails with the exact same evidence. Explain why the ordinary CI run needs neither a model nor a credential.
4. Share the local concurrency evidence and the separate 24-case study. The concurrency test verifies booking totals and replay handling under local load. The study shows that focused and routine examples catch different defects.
5. Ask how the product owner would define event identity, which defects warrant a hold, and what review time is acceptable. Explain how a blinded pilot would change your recommendation if the agent adds effort without improving material defect detection.

SEB asks for an English CV and lists the application deadline as **10 January 2027 at 23:59 CET**. [Official vacancy and application entry](https://sebgroup.com/career/find-your-new-job/our-vacant-positions/seb-tech-trainee-programme-2027-28-ai-research-analyst--seb-stockholm-6bb6f12e-d9ef-4a9b-9806-2cde4fee402d)
