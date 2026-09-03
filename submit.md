## Inspiration

We kept seeing the same problem: developers already have plenty of tools, but those tools don't work together.

Ruff finds one thing, Semgrep finds another, OSV reports vulnerable dependencies, Gitleaks finds secrets, and pytest tells us something else is broken. Someone still has to make sense of all those reports, decide what matters, write the fixes, run everything again, and finally open a PR.

AI coding assistants can suggest a fix, but we wanted to go further.

We wanted an AI engineer that could actually take ownership of the workflow: **understand the repository, investigate issues, plan the work, make changes, verify them, ask for human approval when the risk is high, and deliver a real pull request.**

That's where theReCode came from.

## What it does

**theReCode is an autonomous software-engineering platform for Python repositories on GitHub and GitLab.**

A typical run looks like this:

**Connect → Clone → Diagnose → Correlate → Plan → Risk Check → Fix → Test → Peer Review → PR**

theReCode runs real open-source engineering tools such as **Ruff, Bandit, Semgrep, Gitleaks, OSV-Scanner, and Pytest**, then uses **Google ADK and Gemini API** to reason over the findings and coordinate the workflow.

High-risk changes stop for human approval. Engineers can see the live pipeline, findings, proposed changes, diffs, and verification results before anything is shipped.

When everything passes, theReCode can create a `fix/<run-id>` branch and open a pull request with an audit trail.

**It doesn't just tell you what to fix. It works toward getting the fix shipped.**

## How we built it

We deliberately didn't make everything LLM-driven.

The core workflow uses **Google ADK 2.0** with Gemini specialists for planning, code fixes, and peer review. Deterministic stages handle operations where reliability matters most—repository cloning, scanner execution, risk checks, testing, and Git operations.

The backend is built with **FastAPI and MongoDB**, while the React/Vite dashboard provides the operator experience: live SSE progress, pipeline visualization, approvals, diffs, findings, and run history.

Each repository runs inside an isolated workspace, and Git/Gemini credentials are encrypted and stored per user.

The project is packaged with Docker and deployed using **Google Cloud Run**.

## Challenges we ran into

Building an autonomous engineer sounds straightforward until you actually let it modify code.

One of our biggest challenges was **human approval**. An approval step isn't really an error or a failed agent—it is a legitimate state in the workflow. We redesigned the ADK flow around explicit pre- and post-risk stages.

We also discovered that fixing lint issues is very different from fixing semantic bugs. Early versions could automatically apply formatting changes, but meaningful code changes required Gemini to understand the surrounding code and generate a scoped patch.

We ran into workflow state issues where failed retries could leave runs stuck in `FIXING`, preventing Git operations. We had to make state transitions and recovery paths much more explicit.

Then there were the less glamorous problems: Cloud Build substitutions, frontend environment variables, workspace cleanup, Git push behavior, and making sure an autonomous patch never modifies files outside its approved scope.

Those problems taught us that **agent reliability is as much about engineering the system around the model as it is about the model itself.**

## Accomplishments we're proud of

The biggest achievement is that theReCode can complete the full loop:

**Clone → Diagnose → Plan → Fix → Verify → Peer Review → Push → PR**

We're especially proud of:

- **Risk-based human approval** with visible diffs
- **Multi-agent peer review** across security, testing, and architecture
- **Real scanner grounding** instead of relying only on LLM reasoning
- **Live execution visibility** through the dashboard and SSE timeline
- **Self-correction and verification** after fixes
- **Persistent memory** of previous run outcomes
- **Production-ready packaging** with Docker, Cloud Build, and Cloud Run

## What we learned

Our biggest lesson was simple:

**You don't need an LLM to control everything.**

The best results came from combining deterministic software engineering with intelligent agents.

Scanners provide reliable evidence. Deterministic stages provide predictable execution. Gemini handles the parts that require reasoning, planning, and understanding code.

We also learned that **human-in-the-loop isn't a fallback**. For risky changes, approval is part of the product.

And finally, we learned that a good agent isn't just about intelligence. Engineers need to know **what it's doing, why it stopped, what it changed, and whether the result is safe.**

## What's next

Today, theReCode focuses on Python repositories. Our next steps are to expand language and framework support, improve semantic fix quality, make long-running runs resilient to infrastructure restarts, and add deeper observability around agent execution and costs.

We also want to bring approvals and reviews closer to where developers already work—with tighter GitHub/GitLab and IDE integrations.

Our long-term goal is simple:

**Make software maintenance something developers can delegate, while keeping humans in control of the decisions that matter.**