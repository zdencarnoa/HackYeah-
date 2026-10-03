# Security Copilot

## AI-Powered Phishing Detection, Incident Response & Organizational Resilience

## 1. Project Overview

Build a security-focused AI copilot designed primarily for **small and medium-sized organizations that do not have dedicated security teams**.

The system helps employees and administrators deal with suspicious emails and potential phishing incidents.

The core idea is:

> **Do not just detect the attack. Help people understand it, decide what to do, contain it, and recover from it.**

A basic phishing classifier is only one component of the system. The complete product should support the entire workflow:

```text
Suspicious message
        ↓
Detection
        ↓
Explanation
        ↓
Risk assessment
        ↓
Recommended action
        ↓
Incident response
        ↓
Organization-wide containment
        ↓
Recovery
```

The project should demonstrate that security technology can improve **preparedness, decision-making, response, and continuity**, particularly when organizations have limited resources.

---

# 2. Problem

Phishing remains dangerous not simply because people cannot recognize malicious emails, but because organizations often struggle with what happens **after** a suspicious message is received.

A typical small organization may have:

* No dedicated security team
* Employees with different levels of security awareness
* Limited monitoring
* No formal incident-response process
* No centralized view of who received a suspicious message
* No clear procedure when someone clicks a malicious link
* No way to quickly determine the potential impact of a compromised account

A conventional phishing detector answers:

> "Is this email malicious?"

Our system should answer a much more useful set of questions:

> "Why is this suspicious?"

> "What should I do?"

> "What happens if I already clicked it?"

> "Who else might be affected?"

> "What should the administrator do now?"

> "How can we contain the incident?"

---

# 3. Product Vision

The product is an **AI Security Copilot** consisting of two main experiences:

### Employee Copilot

Helps an ordinary employee safely evaluate suspicious messages.

The employee should not need cybersecurity expertise.

Example:

```text
Employee:
"Is this email safe?"

        ↓

Security Copilot:

HIGH RISK

Why:
• Sender domain does not match the claimed organization
• Link redirects to an unfamiliar domain
• Message uses urgent account-verification language
• Login page appears to imitate a trusted service

Recommended action:
Do not click the link.

[Report Message]
[I Already Clicked]
[I Entered My Password]
```

### Security Administrator Copilot

Helps administrators investigate, prioritize, and respond to incidents.

Example:

```text
SECURITY INCIDENT

Microsoft Account Verification Campaign

14 suspicious messages
7 affected employees
1 employee entered credentials

Potential impact:
HIGH

Recommended actions:

1. Revoke affected account sessions
2. Reset credentials
3. Verify MFA configuration
4. Search for similar messages
5. Notify affected employee
6. Monitor account activity
```

---

# 4. Target Users

## Primary User

Small and medium-sized organizations without a dedicated security operations team.

Examples:

* Small businesses
* Schools
* Non-profit organizations
* Local organizations
* Startups
* Small public-sector organizations

## Secondary Users

### Employees

Need simple, understandable guidance when they encounter suspicious content.

### IT/Security Administrators

Need centralized visibility and actionable recommendations.

---

# 5. Core Product Principles

The system should follow these principles.

## 5.1 Detection is not enough

Do not make the phishing classifier the centerpiece.

The classifier is an input into a larger decision-support system.

---

## 5.2 Explain every important decision

Never simply display:

```text
Phishing probability: 94%
```

Instead show understandable evidence:

```text
HIGH RISK

Reasons:

✓ Sender domain differs from claimed organization
✓ URL leads to an unrelated domain
✓ Urgency language detected
✓ Login page impersonates a known service
```

Machine-learning confidence may be shown as supporting information, but the human-readable evidence is more important.

---

## 5.3 Guide humans instead of overwhelming them

The system should translate technical findings into actions.

Bad:

```text
DMARC: fail
SPF: softfail
Domain reputation: 12
URL entropy: 4.81
```

Better:

```text
The sender claims to be your bank, but the message
was sent from a different domain.

Recommended action:
Do not use the link in this message.
Open your bank's website directly instead.
```

Technical information can remain available under an "Advanced details" section.

---

## 5.4 Assume information may be incomplete

The system should explicitly communicate uncertainty.

For example:

```text
Risk: MEDIUM

We could not verify the sender's domain reputation.

This does not prove the message is malicious.

Recommended action:
Verify the request using another communication channel.
```

Never invent evidence.

---

## 5.5 Optimize for action

Every important detection should eventually answer:

> **What should the user do next?**

---

# 6. Core Features

## Feature 1 — Phishing Detection

Analyze an email/message and estimate its risk.

Potential inputs:

* Sender address
* Sender domain
* Recipient
* Subject
* Message body
* URLs
* Attachments
* Email headers
* Domain information
* Known threat indicators
* Language patterns
* Brand impersonation indicators

The system can combine:

### Machine Learning

Detect patterns associated with phishing.

Potential approaches:

* Text classification
* Embeddings
* LLM-based classification
* Traditional ML classifier
* Hybrid ML + rules

### Deterministic Security Checks

Examples:

* Sender/domain mismatch
* Suspicious URL
* Lookalike domain
* Excessive urgency
* Credential request
* Unexpected attachment
* Domain mismatch
* Suspicious redirect
* Known malicious indicator

The final result should combine these signals.

---

# 7. Feature 2 — Explainable Risk Assessment

Every analyzed message receives a risk level.

Suggested levels:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

The system should explain the result.

Example:

```text
HIGH RISK

This message contains several suspicious characteristics:

1. The sender claims to represent Microsoft,
   but the sender domain is not Microsoft.

2. The embedded link points to an unrelated domain.

3. The message creates urgency by threatening
   account suspension.

4. The link leads to a page requesting credentials.
```

Avoid claiming certainty unless the evidence supports it.

Use language such as:

* "This is suspicious because..."
* "We found..."
* "This increases the risk..."
* "We could not verify..."
* "This does not prove..."

---

# 8. Feature 3 — Employee Decision Flow

After analyzing a message, the system should ask what happened.

Example:

```text
What happened?

○ I haven't interacted with it
○ I clicked the link
○ I downloaded an attachment
○ I entered my password
○ I entered other information
```

The response should change depending on the answer.

### Case A — User has not interacted

Show:

```text
Recommended action:

Do not click any links or open attachments.

[Report Message]
```

### Case B — User clicked a link

Show:

```text
Potential exposure detected.

Recommended actions:

1. Close the page.
2. Do not enter additional information.
3. Report the incident.
4. If credentials were entered, select
   "I entered my password."
```

### Case C — User entered credentials

Escalate to incident response:

```text
POTENTIAL ACCOUNT COMPROMISE

Take these actions immediately:

1. Change your password using the legitimate service.
2. Revoke active sessions if possible.
3. Verify MFA.
4. Notify your administrator.

[Start Incident Response]
```

---

# 9. Feature 4 — Campaign Correlation

Do not analyze every email independently.

The system should recognize when multiple suspicious messages appear to belong to the same campaign.

Example:

```text
14 messages detected

Same campaign characteristics:

• Same sender infrastructure
• Similar subject
• Same destination URL
• Similar message content

Affected users:
7

Departments:
Finance
HR
Operations
```

This turns the product from an individual phishing detector into an organizational security system.

---

# 10. Feature 5 — Security Dashboard

The administrator should have a central dashboard.

Example:

```text
SECURITY OVERVIEW

Active incidents                 2
High-risk messages               8
Affected employees               7
Potentially compromised accounts 1

────────────────────────────────

ACTIVE CAMPAIGNS

Microsoft Account Verification
14 messages
7 employees
1 credential submission

Invoice Payment Fraud
3 messages
2 employees
```

The dashboard should prioritize actionable information.

---

# 11. Feature 6 — Incident Response Copilot

This is one of the most important features.

When an incident occurs, the system should create a structured incident.

Example:

```text
INCIDENT #1042

Type:
Credential Phishing

Severity:
HIGH

Affected users:
7

Confirmed interactions:
1

Potentially compromised accounts:
1
```

Then provide a response checklist.

```text
RECOMMENDED RESPONSE

☐ Revoke active sessions
☐ Reset credentials
☐ Verify MFA
☐ Search for related messages
☐ Notify affected users
☐ Monitor account activity
☐ Document incident
```

The system should explain why actions are recommended.

Example:

> Because credentials may have been submitted to a phishing site, revoking active sessions can reduce the risk of an attacker continuing to use an existing authenticated session.

The recommendations should be presented as guidance, not as claims that the AI knows exactly what happened.

---

# 12. Feature 7 — Organizational Blast-Radius Visualization

Represent important organizational dependencies.

Example:

```text
Employee
   │
   ▼
Identity Provider
   │
   ├──────────────► Email
   │
   ├──────────────► File Storage
   │
   └──────────────► Internal Applications
```

If an identity account may be compromised, show the potentially affected services.

Example:

```text
Potential impact

Employee account
      ↓
Identity provider
      ↓
Email ───────► Internal users
      ↓
File storage
      ↓
Sensitive documents
```

This does NOT need to be a real production dependency mapper.

For the hackathon, a simulated organizational graph is acceptable.

The important concept is:

> A security incident can have consequences beyond the original email.

---

# 13. Feature 8 — Recommended Containment

The administrator should be able to perform or simulate containment actions.

Potential actions:

```text
[Quarantine Messages]
[Block Sender]
[Block Domain]
[Notify Users]
[Disable Account]
[Reset Credentials]
[Revoke Sessions]
[Start Investigation]
```

For a hackathon prototype, these actions can operate on a simulated environment rather than real infrastructure.

The UI should clearly indicate when an action is simulated.

Example:

```text
✓ SIMULATION

7 matching phishing messages would be quarantined.
```

Do not build functionality that could accidentally affect real users or infrastructure.

---

# 14. AI Copilot Responsibilities

The AI component should primarily be used for:

### Analysis

* Explain suspicious characteristics
* Summarize incidents
* Correlate related messages
* Identify relevant evidence

### Decision support

* Suggest next steps
* Prioritize incidents
* Explain consequences
* Generate response checklists

### Communication

* Explain technical findings in plain language
* Generate employee notifications
* Summarize incidents for administrators

The AI should NOT pretend to have access to information it does not actually have.

---

# 15. Suggested System Architecture

A possible architecture:

```text
                    ┌────────────────────┐
                    │   Email / Message  │
                    └─────────┬──────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │   Ingestion Layer      │
                  └───────────┬────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
          ┌──────────┐ ┌───────────┐ ┌────────────┐
          │ ML Model │ │ URL/Domain │ │ Rule Engine│
          │          │ │ Analysis   │ │            │
          └────┬─────┘ └─────┬─────┘ └──────┬─────┘
               │             │              │
               └─────────────┼──────────────┘
                             ▼
                   ┌──────────────────┐
                   │ Risk Assessment  │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │ Explanation / AI │
                   │ Copilot Layer    │
                   └────────┬─────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      ┌────────────────┐          ┌─────────────────┐
      │ Employee UI    │          │ Admin Dashboard │
      └───────┬────────┘          └────────┬────────┘
              │                            │
              └────────────┬───────────────┘
                           ▼
                 ┌────────────────────┐
                 │ Incident Management │
                 └─────────┬──────────┘
                           ▼
                 ┌────────────────────┐
                 │ Response / Recovery│
                 └────────────────────┘
```

---

# 16. Suggested Technology Stack

The exact stack can change according to the team's experience.

One possible implementation:

## Frontend

* React
* Next.js
* TypeScript
* Tailwind CSS

## Backend

* Python
* FastAPI

## Machine Learning

Potential options:

* scikit-learn
* Hugging Face models
* sentence-transformers
* LLM API
* A hybrid approach

## Database

* PostgreSQL

For a hackathon prototype, SQLite is also acceptable.

## Graph / Dependency Visualization

* React Flow
* D3.js
* Cytoscape.js

## AI

Use an LLM for:

* explanations
* summaries
* recommendations
* natural-language interaction

Do not make the LLM solely responsible for determining whether an email is malicious.

A hybrid architecture is preferred:

```text
Deterministic signals
        +
ML classification
        +
Threat intelligence
        +
LLM explanation
        =
Security Copilot
```

---

# 17. Data Strategy

The prototype should use safe, synthetic, or publicly available phishing examples.

Create a small demonstration dataset containing:

### Legitimate messages

Examples:

* Password reset notifications
* Invoices
* Internal announcements
* Delivery notifications
* Meeting invitations

### Phishing messages

Examples:

* Credential theft
* Fake invoices
* Account suspension
* MFA scams
* CEO impersonation
* Delivery scams

Create several variants of the same phishing campaign so that campaign correlation can be demonstrated.

---

# 18. Demonstration Scenario

The demo should revolve around one realistic incident.

## Step 1 — Initial phishing email

An employee receives:

```text
From:
Microsoft Security <security@micr0soft-example.com>

Subject:
URGENT: Your account will be suspended
```

The message asks the user to verify their account.

---

## Step 2 — Employee analyzes it

The employee submits the email to the Security Copilot.

The system detects:

```text
HIGH RISK

Suspicious indicators:

• Lookalike sender domain
• Urgency language
• Credential request
• Suspicious URL
• Brand impersonation
```

---

## Step 3 — Employee makes a mistake

For the demo, select:

> "I entered my password."

The system immediately changes from detection mode to incident-response mode.

```text
POTENTIAL ACCOUNT COMPROMISE

Immediate actions recommended:

1. Change password
2. Revoke active sessions
3. Verify MFA
4. Notify administrator
```

---

# 19. Step 4 — Administrator receives alert

The admin dashboard updates:

```text
🔴 NEW HIGH-SEVERITY INCIDENT

Employee:
Alice

Incident:
Potential credential compromise

Related messages:
14

Other recipients:
6

Potential campaign:
Microsoft Account Verification
```

---

# 20. Step 5 — Campaign Discovery

The administrator opens the campaign.

The system shows:

```text
14 messages
7 recipients
3 departments

Campaign characteristics:

Same sender pattern
Same URL
Similar message content
Similar delivery time
```

---

# 21. Step 6 — Blast Radius

The administrator views the organizational graph.

```text
Alice
 ↓
Identity Provider
 ├── Email
 ├── File Storage
 └── Internal Applications
```

The system explains:

> If the account is compromised, an attacker may potentially gain access to services connected to that identity. Immediate credential and session protection is therefore recommended.

---

# 22. Step 7 — Containment

Administrator selects:

```text
[Contain Campaign]
```

The system simulates:

```text
✓ 14 messages quarantined
✓ Sender blocked
✓ 7 employees notified
✓ 1 affected account flagged
✓ Incident response checklist created
```

---

# 23. Step 8 — Recovery

The system displays:

```text
RECOVERY STATUS

Account protection       ██████████ 100%
Message containment      ██████████ 100%
Affected users notified  ██████████ 100%
Investigation            ██████░░░░  60%

Remaining actions:

☐ Review account activity
☐ Confirm password reset
☐ Complete incident report
```

This gives the judges a clear beginning, middle, and end.

---

# 24. Important UX Goal

The product should feel like a **security assistant**, not a cybersecurity textbook.

Avoid overwhelming users with:

* Raw logs
* Excessive technical terminology
* Huge tables
* ML statistics without context
* Long AI-generated explanations

Prefer:

```text
What happened?

Why does it matter?

What should I do?

What happens next?
```

---

# 25. What Makes This Different From a Simple Phishing Detector?

The project should explicitly demonstrate the following progression:

```text
Traditional approach:

Email
 ↓
Phishing classifier
 ↓
Warning
```

Our approach:

```text
Email
 ↓
Detection
 ↓
Evidence
 ↓
Risk assessment
 ↓
Human guidance
 ↓
Incident creation
 ↓
Campaign correlation
 ↓
Impact analysis
 ↓
Containment
 ↓
Recovery
```

The innovation is not necessarily inventing a completely new phishing classifier.

The innovation is combining detection with **human-centered incident response and organizational resilience**.

---

# 26. Hackathon MVP

Do NOT attempt to build every possible feature.

The minimum viable product should contain:

### Required

* [ ] Email upload/input
* [ ] Phishing analysis
* [ ] Risk classification
* [ ] Explainable detection
* [ ] Employee decision flow
* [ ] Incident creation
* [ ] Admin dashboard
* [ ] Campaign correlation
* [ ] Recommended response actions
* [ ] Simulated containment
* [ ] Basic organizational dependency graph

### Nice to have

* [ ] Real-time email integration
* [ ] Threat intelligence APIs
* [ ] URL sandboxing
* [ ] Attachment analysis
* [ ] Automated notifications
* [ ] Interactive AI chat
* [ ] Historical incident analytics
* [ ] Security training mode

Do not sacrifice a polished end-to-end demonstration just to add more features.

---

# 27. Safety and Scope

This is a defensive cybersecurity project.

The prototype should operate primarily on:

* Synthetic emails
* Publicly available security examples
* Simulated organizational infrastructure
* Sandboxed data

Do not send real phishing emails.

Do not attempt to compromise real accounts.

Do not automatically execute suspicious attachments.

Do not perform destructive actions on real infrastructure.

Actions such as account disabling, email quarantine, domain blocking, or session revocation should be simulated unless the project is explicitly deployed in a controlled test environment.

---

# 28. Success Criteria

The project should be judged primarily by whether it demonstrates that it can improve the organization's ability to:

### Prepare

Identify suspicious messages and understand potential threats.

### Detect

Identify phishing and related campaigns early.

### Decide

Give humans understandable evidence and actionable recommendations.

### Respond

Guide users and administrators through appropriate containment steps.

### Coordinate

Identify other affected users and related messages.

### Maintain continuity

Help the organization understand what services could be affected and prioritize recovery.

---

# 29. Core Demo Message

The final presentation should communicate one simple idea:

> **Security isn't just about detecting threats. It's about helping people make the right decision when a threat occurs.**

The system should demonstrate this progression:

```text
"Is this email suspicious?"

             ↓

"Why?"

             ↓

"What should I do?"

             ↓

"I already clicked it. Now what?"

             ↓

"Who else is affected?"

             ↓

"What could this compromise affect?"

             ↓

"What should our organization do next?"

             ↓

"Are we back to normal?"
```

That is the Security Copilot.

---

# 30. Development Priority

When making implementation decisions, prioritize in this order:

1. **End-to-end working demo**
2. **Excellent user experience**
3. **Credible phishing detection**
4. **Clear explanations**
5. **Incident-response workflow**
6. **Campaign correlation**
7. **Impact/dependency visualization**
8. Additional AI features

A smaller system that works flawlessly from detection → response → recovery is preferable to a large collection of unfinished features.

---

# 31. Product Definition

The final product can be summarized as:

> **An AI-powered security copilot that helps organizations detect phishing, understand why a message is dangerous, guide employees through the correct response, identify related incidents, visualize potential impact, and coordinate containment and recovery.**

The phishing classifier is the **sensor**.

The copilot is the **decision-support system**.

The incident-response workflow is the **resilience mechanism**.
