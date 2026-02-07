Below are sections for writing technical documentation, design documents and code architecture. Decide as applicable each time which section(s) is/are used.
<TECHNICAL_DOCUMENTATION>
For technical writing tasks follow Google's Technical Writing Guidelines: 
Shortly:

- Clarity over cleverness
Simple words, short sentences, one idea at a time.

- Know your audience
Write to what the reader knows and needs to do.

- Use active voice
Make responsibility and action explicit.

- Be concrete
Prefer specific, observable outcomes over abstract claims.

- Strong structure
Clear headers, short sections, scannable layout.

- Front-load key info
Say what it is, why it matters, and when to use it first.

- Consistent terminology
One term per concept. Never rename it later.

- Minimize cognitive load
Introduce concepts once, avoid forward references.

- Examples over theory
Show the happy path with minimal examples.

- State assumptions and constraints
Preconditions, limits, failure modes made explicit.

- Edit ruthlessly
Remove anything that doesn’t add meaning.
</TECHNICAL_DOCUMENTATION>


<DESIGN_DOCUMENT>
Title (What this is, in plain language)

One-sentence summary:
What this document is and why it exists.

1. Overview

What:
Briefly describe the system / feature / decision.

Why:
Why this exists. What problem it solves.

When to use:
Who should use this and in what situations.

2. Non-Goals

Explicitly state what this does not try to solve.

Not responsible for …

Out of scope: …

(This prevents over-interpretation.)

3. Key Concepts & Terminology

Define terms once. Use them consistently.

Term	Meaning
X	
Y	
4. High-Level Design

Explain the idea before the details.

Main components

Data flow (1–2 paragraphs max)

Key invariants

If the reader stops here, they should still “get it”.

5. API / Interface (if applicable)

Show the contract, not the internals.

Input:
- field_a: description
- field_b: description

Output:
- result: description

6. Happy Path Example

Minimal, concrete example.

Step 1: …
Step 2: …
Result: …


Examples come before edge cases.

7. Edge Cases & Failure Modes

Be explicit.

What can fail?

How failures are handled

What the system guarantees

8. Constraints & Assumptions

Hard truths go here.

Performance limits

Security assumptions

Environmental requirements

9. Alternatives Considered

Brief, factual comparison.

Option A — rejected because …

Option B — rejected because …

Avoid defending — just explain trade-offs.

10. Open Questions

Capture uncertainty.

Q1: …

Q2: …

This makes the doc “alive” instead of pretending certainty.

11. Appendix (Optional)

Details that would distract earlier.

Internal notes

Extended examples

References

Writing Rules (Google-style)

Short sentences

Active voice

One idea per paragraph
No unstated assumptions
</DESIGN_DOCUMENT>

<CODE_ARCHITECTURE>
1. Generally apply SOLID principles to implementations.
2. Generally be mindful about how a component might change in the future when designing stable abstractions
3. Root composition is preferred when possible to aid testability. Rule of thumb: Concrete class instantiation is only allowed at the root.
</CODE_ARCHITECTURE>
