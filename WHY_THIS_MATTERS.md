# Why Security Copilot matters: the case for SMB phishing defence

_Compiled 2026-10-04. Figures are quoted with their sources; see **Sources & caveats** at the end for how reliable each one is._

Security Copilot is built for **small and medium-sized organisations that have no security team**. The data below supports three claims behind the project:

1. Phishing is the single most common attack, and it hits small businesses too.
2. The attack works because it targets people, and employees click fast.
3. Small businesses are the least equipped to detect, explain, or respond — which is exactly the gap the product fills.

---

## 1. Phishing is the most common attack — and SMBs are in scope

- In the UK government's **Cyber Security Breaches Survey 2025/26**, **43% of all businesses** (about **612,000 UK businesses**) identified a cyber breach or attack in the previous 12 months. Among businesses that were attacked, **phishing was the most common type**, and **69% named phishing the most disruptive** attack they faced. ([gov.uk](https://www.gov.uk/government/statistics/cyber-security-breaches-survey-20252026/cyber-security-breaches-survey-20252026))
- The same survey shows the risk rises with size but is already high for small firms: breaches were identified by **42% of micro, 46% of small, 65% of medium and 69% of large** businesses. ([gov.uk](https://www.gov.uk/government/statistics/cyber-security-breaches-survey-20252026/cyber-security-breaches-survey-20252026))
- The share of businesses whose incidents were **phishing only** rose to **51%** (from 45% the year before) — for many smaller organisations, phishing *is* the threat. ([gov.uk](https://www.gov.uk/government/statistics/cyber-security-breaches-survey-20252026/cyber-security-breaches-survey-20252026))
- In the US, the **FBI's IC3 2024 report** ranked **phishing/spoofing as the #1 complaint type by volume, with 193,407 complaints** — more than any other category. ([IC3 2024 report](https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf), [CyberScoop summary](https://cyberscoop.com/fbi-ic3-cybercrime-report-2024-key-statistics-trends/))

---

## 2. It works because it targets people, and people click

- **Verizon's 2024 DBIR** found the median time for a user to fall for a phishing email is **under 60 seconds** — from opening the email to entering data. In simulations, only about **20% of users reported** the phishing attempt. ([Verizon 2024 DBIR](https://www.verizon.com/business/resources/reports/2024-dbir-data-breach-investigations-report.pdf))
- The **2025 DBIR** found roughly **60% of breaches involved a human element** — a click, a reply, a socially engineered call, or a mistake. ([Verizon 2025 DBIR](https://www.verizon.com/business/resources/reports/2025-dbir-data-breach-investigations-report.pdf), [RCR Wireless summary](https://www.rcrwireless.com/20250423/business/verizons-cybersecurity))
- **Proofpoint's 2024 State of the Phish** (drawn from 2.8 trillion scanned emails and 183 million simulated phishing tests across ~230,000 organisations) reported an average **click rate of 9.3%** on simulated phishing — up 36% year over year — and that **71% of working adults admitted taking a risky action**, most of them knowing the risk. ([Proofpoint press release](https://www.proofpoint.com/us/newsroom/press-releases/proofpoints-2024-state-phish-report-68-employees-willingly-gamble), [report PDF](https://webobjects2.cdw.com/is/content/CDW/cdw/on-domain-cdw/brands/proofpoint/2024-state-of-the-phish-report.pdf))

**Takeaway for the product:** awareness training alone leaves ~1 in 11 users clicking, and detection that waits for the employee to report is too slow when the median time-to-click is under a minute. Security Copilot scores every delivered email on arrival rather than relying on the employee.

---

## 3. Small businesses are the least equipped — the gap we fill

- When small businesses are breached, the damage is severe: the **2025 DBIR** found **ransomware was present in 88% of breaches at SMBs**, versus **39% at large organisations**. Smaller firms are hit harder, not less. ([Verizon 2025 DBIR SMB snapshot](https://www.verizon.com/business/resources/infographics/2025-dbir-smb-snapshot.pdf), [summary](https://cinchops.com/2025-verizon-data-breach-investigation-report/))
- Yet small firms' defences are thin and even **slipping**. In the UK survey, among small businesses only **41%** do risk assessments (down from 48%), **52%** have a formal cyber policy (down from 59%), and **44%** have a business continuity plan covering cyber (down from 53%). Only **37%** have a board member responsible for cyber security. ([gov.uk](https://www.gov.uk/government/statistics/cyber-security-breaches-survey-20252026/cyber-security-breaches-survey-20252026))
- Industry surveys of SMBs point the same way: a large share allocate little or no dedicated cybersecurity budget, most cannot justify a full-time security hire, and the majority run no regular security-awareness training. (See **Sources & caveats** — these are vendor/aggregator figures, directionally consistent but less authoritative than the government and DBIR data above.) ([StationX compilation](https://app.stationx.net/articles/small-business-cybersecurity-statistics), [Qualysec compilation](https://qualysec.com/small-business-cyber-attack-statistics/))

**Takeaway for the product:** these organisations have no analyst to read email headers, judge a lookalike domain, or run an incident. Security Copilot does the detection, explains the verdict in plain language, and walks a non-expert admin through containment and recovery — the role a security team would otherwise play.

---

## 4. The money at stake

- The FBI IC3 logged **US$16.6 billion** in reported losses in 2024, up **33%** on 2023 and the highest it has ever recorded. ([IC3 2024 report](https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf), [Cybersecurity Dive](https://www.cybersecuritydive.com/news/fbi-internet-crime-bec-scams-investment-fraud-losses/746181/))
- **Business Email Compromise** — phishing's most lucrative form, and one aimed squarely at finance and invoicing staff in ordinary businesses — accounted for **US$2.77 billion across 21,442 incidents** in 2024 alone. ([IC3 2024 report](https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf), [Abnormal summary](https://abnormal.ai/blog/2024-fbi-ic3-report))

---

## One-paragraph version (for a pitch)

Phishing is the most common cyber attack reported by businesses — **84% of attacked UK businesses** historically, and still the most disruptive attack for **69%** of those breached in 2025/26 — and it is the **#1 complaint** to the FBI, with phishing-enabled Business Email Compromise costing **$2.77 billion** in 2024. It works because it targets people: the median time to fall for a phishing email is **under a minute**, average simulated click rates sit near **9%**, and **~60% of all breaches involve a human element**. Small businesses are both **more likely to suffer ransomware when breached (88% vs 39%)** and the **least equipped to respond** — fewer than half do risk assessments or hold a cyber policy, and most have no security staff or regular training. Security Copilot targets exactly that gap: automatic detection on every email, plain-language explanations, and a guided incident-response and recovery flow for organisations with no security team.

---

## Sources & caveats

**Most authoritative (use these first):**

- **UK Cyber Security Breaches Survey 2025/26** — UK government official statistics (DSIT/Ipsos), nationally representative. [gov.uk](https://www.gov.uk/government/statistics/cyber-security-breaches-survey-20252026/cyber-security-breaches-survey-20252026)
- **Verizon Data Breach Investigations Report (2024, 2025)** — industry-standard analysis of tens of thousands of real incidents. [2024](https://www.verizon.com/business/resources/reports/2024-dbir-data-breach-investigations-report.pdf) · [2025](https://www.verizon.com/business/resources/reports/2025-dbir-data-breach-investigations-report.pdf) · [2025 SMB snapshot](https://www.verizon.com/business/resources/infographics/2025-dbir-smb-snapshot.pdf)
- **FBI IC3 Internet Crime Report 2024** — official US complaint and loss data. [IC3](https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf)

**Reliable but vendor-published** (large datasets; some figures are marketing-forward, so attribute to the vendor):

- **Proofpoint 2024 State of the Phish** — click rates and user-behaviour figures. [Proofpoint](https://www.proofpoint.com/us/newsroom/press-releases/proofpoints-2024-state-phish-report-68-employees-willingly-gamble)

**Secondary aggregators** (handy summaries that restate other surveys; verify before quoting in anything formal, and prefer the primary source where one exists):

- [StationX — Small Business Cybersecurity Statistics](https://app.stationx.net/articles/small-business-cybersecurity-statistics)
- [Qualysec — Small Business Cyber Attack Statistics](https://qualysec.com/small-business-cyber-attack-statistics/)

Notes:
- Percentages shift year to year and between the UK survey and US-centric reports; where a number drives a decision, cite the specific report and year rather than a round figure.
- "84% of attacked businesses experienced phishing" is from earlier editions of the UK survey; the 2025/26 edition reports phishing as the most common and most disruptive attack and gives the **69% most-disruptive** figure quoted above.
