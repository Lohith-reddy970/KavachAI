# Post-optimization testing

Use [CHECKLIST.md](CHECKLIST.md) for acceptance testing on the target machine. Record results, evidence, tester, and date against each item. Items remain unchecked until verified on that deployment.

[VALIDATION.md](VALIDATION.md) distinguishes automated checks completed during cleanup from integration checks still needed. Test fixtures and inference doubles remain isolated under `backend/tests/` and `backend/evals/`; application runtime data starts empty.

For the mentor's five-result demonstration, use [mentor-testing/README.md](../mentor-testing/README.md). It provides three successful workflows and two expected rejection cases, with a runnable suite and the completed evidence report. Those controlled inputs and their results are stored separately under `mentor-testing/` and excluded from the production Docker build.
