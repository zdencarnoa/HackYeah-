"""Generate synthetic modern emails (2020s style) to fix the dataset's domain gap.

The Kaggle corpora are mostly 2000s conversations: almost every automated
notification in them is spam, so the model learned "notification = phishing".
Here both classes come from the SAME categories (delivery, account security,
file sharing, payroll, invoices, e-signature, ...) with the same footers and
style, so the model has to learn the content difference: informational vs.
urgent pressure to click, pay or confirm credentials.

Person D's demo emails are never used here; they stay the honest test set.

Usage:
    python -m app.ml.synth_emails   # (from backend/) writes data/synthetic/modern_emails.csv
"""
import csv
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "modern_emails.csv"
PER_CATEGORY = 220
SEED = 7

FIRST = ["Anna", "Piotr", "Kasia", "Tomasz", "Marta", "Jakub", "Ewa", "Michał", "Sarah", "David",
         "Laura", "James", "Olga", "Marek", "Julia", "Paweł", "Emma", "Lukas", "Sofia", "Adam"]
LAST = ["Nowak", "Kowalski", "Wiśniewska", "Smith", "Müller", "Zieliński", "Brown", "Lewandowska",
        "Kamińska", "Novak", "Horvat", "Jones", "Wójcik", "Fischer", "Dąbrowski"]
COMPANY = ["Northwind", "Contoso", "Fabrikam", "Brightline Logistics", "Vistula Freight", "Adria Trade",
           "Kestrel Systems", "Bluewave Consulting", "Orion Supplies", "Baltic Cargo"]
COURIER = ["DHL", "DPD", "InPost", "UPS", "GLS", "FedEx", "Poczta Polska"]
CLOUD = ["OneDrive", "Google Drive", "SharePoint", "Dropbox", "Box"]
ACCOUNT = ["Microsoft", "Google", "your company account", "Microsoft 365", "Okta", "Zoom", "Slack", "Adobe"]
SIGN = ["DocuSign", "Adobe Sign", "Dropbox Sign", "PandaDoc"]
MONTH = ["January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"]
DAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
CITY = ["Kraków", "Warsaw", "Gdańsk", "Wrocław", "Poznań", "Berlin", "Vienna", "Prague", "Rotterdam"]
DEVICE = ["Windows PC", "iPhone", "Android phone", "MacBook", "Chrome on Windows", "Edge on Windows"]
WORK_DOC = ["Q3 budget review.xlsx", "Meeting notes - {day}.docx", "Project timeline.pptx",
            "Supplier list 2026.xlsx", "Onboarding checklist.docx", "Warehouse layout.pdf",
            "Sales forecast Q4.xlsx", "Team rota {month}.xlsx", "Client proposal draft.docx"]
LURE_DOC = ["Salary adjustments 2026.pdf", "Confidential - restructuring plan.pdf", "Bonus allocation.xlsx",
            "Termination list Q4.pdf", "Updated payroll details.pdf", "HR disciplinary notice.pdf",
            "Executive compensation review.xlsx", "Pending invoice payment.pdf"]

FOOTERS = ["", "", "This is an automated message. Please do not reply to this email.",
           "You are receiving this email because you have an account with us.",
           "To manage your notification settings, visit your account preferences.",
           "Privacy Statement | Terms of Use", "Sent from my iPhone",
           "This email and any attachments are confidential and intended solely for the addressee."]
GREET = ["Hi {first},", "Hello {first},", "Dear {first},", "Hi,", "Hello,", "Dear customer,", "Dear user,", ""]


def r(rng, options):
    return rng.choice(options)


def fill(rng, text):
    first, last = r(rng, FIRST), r(rng, LAST)
    sender_first = r(rng, FIRST)
    return text.format(
        first=first, last=last, name=f"{first} {last}", sender=f"{sender_first} {r(rng, LAST)}",
        sender_first=sender_first, company=r(rng, COMPANY), courier=r(rng, COURIER), cloud=r(rng, CLOUD),
        account=r(rng, ACCOUNT), sign=r(rng, SIGN), month=r(rng, MONTH), day=r(rng, DAY), city=r(rng, CITY),
        device=r(rng, DEVICE), n=rng.randint(10000, 999999), amount=f"{rng.randint(12, 9800)}.{rng.randint(0, 99):02d}",
        fee=f"{rng.choice([1, 1, 2, 2, 3, 4])}.{rng.choice([49, 99, 50, 95])}", hours=rng.choice([12, 24, 48, 72]),
        days=rng.choice([3, 5, 7, 14, 30]), doc=r(rng, WORK_DOC).format(day=r(rng, DAY), month=r(rng, MONTH)),
        lure=r(rng, LURE_DOC), url=r(rng, ["https://portal.example/l/", "https://app.example/s/",
                                            "http://secure-login.example/v/", "https://bit.ly/3x"]) + str(rng.randint(100, 999)),
    )


# Each category: (subjects, body sentence pools). A body is built by picking one
# sentence from each pool in order, so templates combine into many variants.
LEGIT = {
    "delivery": (
        ["Your parcel {n} has been shipped", "Your {courier} parcel is out for delivery today",
         "Delivered: your package {n}", "{courier}: your shipment {n} is on its way", "Your order has shipped"],
        [["Good news! Your parcel from {company} is on its way.", "Your {courier} shipment {n} is out for delivery today.",
          "Your package {n} was delivered to your parcel locker in {city}.", "Your order has left our warehouse."],
         ["Estimated delivery: {day} between 9:00 and 17:00.", "The courier will deliver it today.",
          "You can collect it within {days} days.", "Expected delivery date: {day}."],
         ["You can follow the delivery in the {courier} app.", "Track your shipment: {url}", "No action is needed from you.",
          "If you are not at home, the parcel will be left at the nearest pickup point."],
         ["Thank you for shopping with {company}.", "{courier} Customer Service", "Have a nice day!", ""]],
    ),
    "account_security": (
        ["New sign-in to {account}", "A new app was connected to your account", "Your password was changed",
         "Security info added to your {account} account", "New device signed in"],
        [["We noticed a new sign-in to your {account} account from a {device} in {city}.",
          "The app 'Calendar Sync' was connected to your {account} account.",
          "The password for your {account} account was changed on {day}.",
          "A new phone number was added as a security method on your account."],
         ["If this was you, you can safely ignore this email.", "If you made this change, no further action is needed.",
          "This is a routine notification to keep your account secure."],
         ["If you don't recognise this activity, open your account settings directly and review recent activity.",
          "You can review connected apps at any time in your security settings.",
          "If this wasn't you, contact your IT helpdesk."],
         ["The {account} account team", "Thanks, {account} Security", "IT Service Desk", ""]],
    ),
    "file_share": (
        ["{sender} shared \"{doc}\" with you", "{sender} invited you to edit \"{doc}\"", "Shared with you: {doc}",
         "{sender} shared a folder with you"],
        [["{sender} shared a file with you on {cloud}.", "{sender} invited you to collaborate on a document.",
          "Here is the file we discussed in today's meeting.", "{sender} shared a folder: Team documents."],
         ["\"{doc}\"", "Message from {sender_first}: here are the notes from {day}, feel free to add comments.",
          "Message from {sender_first}: please review before our call on {day}.", "Message from {sender_first}: as promised."],
         ["Open in {cloud}: {url}", "You can find it under 'Shared with me'.", "Open"],
         ["{cloud}", "Microsoft respects your privacy.", ""]],
    ),
    "payroll_hr": (
        ["Your {month} payslip is available", "Reminder: benefits enrolment closes on {day}",
         "Annual leave request approved", "HR newsletter - {month}", "Your timesheet for {month} was approved"],
        [["Your payslip for {month} is now available in the HR portal.", "Your annual leave request for {day} has been approved.",
          "Open enrolment for health benefits closes on {day}.", "Your timesheet for {month} has been approved by your manager."],
         ["You can view it when you next sign in to the HR portal as usual.", "No action is required.",
          "If you have questions, contact the HR team.", "Details are available in the HR portal."],
         ["Best regards, HR Team", "People & Culture, {company}", "Payroll Department", "Thanks, HR"]],
    ),
    "invoice_order": (
        ["Invoice {n} for {month}", "Your receipt from {company}", "Order {n} confirmed",
         "Purchase order {n} received", "Your subscription has been renewed"],
        [["Please find attached invoice {n} for services delivered in {month}.", "Thank you for your order {n}.",
          "We have received your purchase order {n}.", "Your annual subscription was renewed successfully."],
         ["Amount: {amount} EUR. Payment terms: {days} days, as agreed in our contract.", "Total paid: {amount} PLN.",
          "Delivery is planned for {day}.", "The amount of {amount} EUR was charged to your card on file."],
         ["Our bank details remain unchanged.", "No action is needed.", "Let me know if you have any questions.",
          "You can download the receipt from your account."],
         ["Kind regards, {sender}", "Accounts Receivable, {company}", "{company} Billing", ""]],
    ),
    "esign": (
        ["{sender} sent you a document to review: NDA", "Completed: {doc}", "Please review: service agreement {company}"],
        [["{sender} sent you a document via {sign}, as discussed on our call.", "All parties have signed the document.",
          "Following our meeting, here is the service agreement for review."],
         ["Please review it at your convenience this week.", "A copy of the completed document is attached for your records.",
          "There is no rush, let me know if you would like any changes."],
         ["Review document: {url}", "You can access it from your {sign} account.", ""],
         ["Best, {sender}", "{sign}", ""]],
    ),
    "it_notice": (
        ["Planned maintenance on {day}", "Your password will expire in {days} days", "IT: new VPN client available",
         "Mailbox storage at 80%"],
        [["Planned maintenance of the file server will take place on {day} from 22:00 to 23:00.",
          "Your company password will expire in {days} days.", "A new version of the VPN client is available.",
          "Your mailbox is using 80% of its storage."],
         ["You can change it any time via the usual self-service portal.", "Services may be briefly unavailable.",
          "It will be installed automatically overnight.", "Consider archiving older messages."],
         ["No action is needed from you.", "If you have questions, contact the IT Service Desk.", "Thank you for your patience."],
         ["IT Service Desk", "IT Operations, {company}", ""]],
    ),
    "meeting": (
        ["Meeting moved to {day}", "Invitation: weekly sync @ {day} 10:00", "Agenda for {day}", "Lunch on {day}?"],
        [["Hi team, the weekly sync is moved to {day} at 10:00.", "Here is the agenda for {day}'s meeting.",
          "Are you free for lunch on {day}?", "Quick reminder about the all-hands on {day}."],
         ["Topics: Q4 budget, hiring plan and the {city} warehouse.", "Room 2B, or join online.",
          "I'll book a table for 12:30.", "Please bring your updates."],
         ["Thanks, {sender_first}", "See you there, {sender_first}", "Cheers, {sender_first}"]],
    ),
}

PHISH = {
    "delivery": (
        ["Delivery failed: action required", "{courier}: your parcel is on hold", "Final notice: parcel {n} will be returned",
         "Unpaid customs fee for shipment {n}"],
        [["We were unable to deliver your parcel {n} because of an incomplete address.",
          "Your {courier} parcel is on hold due to an unpaid shipping fee.",
          "Your shipment {n} is waiting for a customs payment."],
         ["To reschedule delivery, pay a small fee of {fee} EUR within {hours} hours.",
          "Please confirm your address and card details to release the parcel.",
          "If no payment is received, the package will be returned to the sender."],
         ["Pay now: {url}", "Confirm delivery details here: {url}", "Click here to reschedule: {url}"],
         ["{courier} Delivery Services", "Customer Support", ""]],
    ),
    "account_security": (
        ["URGENT: your account will be suspended", "Unusual sign-in activity detected - verify now",
         "Action required: confirm your identity within {hours} hours", "Your {account} account has been locked",
         "Security alert: verify your account"],
        [["We detected unusual sign-in activity on your {account} account from {city}.",
          "Your {account} account has been temporarily locked for security reasons.",
          "Due to a recent security update, all users must verify their accounts."],
         ["Your account will be permanently suspended within {hours} hours unless you verify your identity.",
          "To avoid losing access to your email and files, confirm your credentials immediately.",
          "Failure to verify will result in deactivation of your account."],
         ["Verify your account now: {url}", "Sign in here to restore access: {url}", "Click below to confirm your password: {url}"],
         ["{account} Security Team", "Account Protection Team", "IT Security", ""]],
    ),
    "file_share": (
        ["{sender} shared \"{lure}\" with you", "Confidential document shared with you", "You have 3 pending documents",
         "{sender} shared a secure file - sign in to view"],
        [["{sender} shared a confidential document with you on {cloud}.", "You have received a secure document.",
          "Important files are waiting for your review."],
         ["\"{lure}\"", "For security reasons, you must sign in again with your email password to view this file.",
          "This link expires in {hours} hours.", "The document is protected; verify your email to access it."],
         ["Open document: {url}", "Sign in to view: {url}", "View secure file: {url}"],
         ["{cloud}", "Secure File Transfer", ""]],
    ),
    "payroll_hr": (
        ["Action required: update your payroll details", "Your {month} salary payment is on hold",
         "HR: confirm your bank account before payroll cutoff", "Important: salary review documents"],
        [["Your {month} salary payment could not be processed.", "HR is updating employee payroll records before the cutoff.",
          "Your salary review is ready, but your profile is incomplete."],
         ["Confirm your bank account details within {hours} hours to avoid a delay in payment.",
          "Please sign in with your company credentials to update your direct deposit information.",
          "Failure to update will result in your salary being delayed."],
         ["Update details here: {url}", "Access the employee portal: {url}", "Confirm now: {url}"],
         ["Payroll Department", "HR Team", ""]],
    ),
    "invoice_order": (
        ["Overdue invoice {n} - immediate payment required", "Change of bank details", "Updated bank details - invoice {n}",
         "Payment reminder: final notice"],
        [["Please note our bank account has changed due to an audit.", "Invoice {n} is now overdue.",
          "Our accounting department has updated our banking information."],
         ["Kindly send today's payment of {amount} EUR to the new account below.",
          "Please process the payment urgently to avoid legal action and late fees.",
          "Do not use the old account details; payments there will be rejected."],
         ["New IBAN: PL{n}{n}. Please confirm once paid.", "Please treat this as urgent and confidential.",
          "Download the updated invoice: {url}"],
         ["Regards, Finance, {company}", "Accounts Department", "{sender}"]],
    ),
    "esign": (
        ["Please sign: urgent agreement", "Document expiring today - signature required", "{sign}: review and sign immediately"],
        [["You have received a document that requires your signature via {sign}.", "An agreement is awaiting your urgent signature."],
         ["The document will expire today if not signed.", "Please review and sign within {hours} hours.",
          "Sign in with your email password to access the document."],
         ["Review and sign: {url}", "Access document: {url}"],
         ["{sign}", "Contracts Department", ""]],
    ),
    "it_notice": (
        ["Your mailbox is full - messages will be deleted", "Password expires today - keep your current password",
         "IT: re-register your authenticator app", "Action required: MFA re-enrolment"],
        [["Your mailbox has exceeded its storage limit.", "Your password expires today.",
          "Due to a system upgrade, all users must re-register multi-factor authentication."],
         ["Incoming messages will be rejected unless you verify your account.",
          "Click below to keep your current password and avoid losing access.",
          "Enter your password and the code from your authenticator app to complete re-enrolment."],
         ["Verify mailbox: {url}", "Keep current password: {url}", "Re-register now: {url}"],
         ["IT Helpdesk", "System Administrator", "IT Service Desk"]],
    ),
    "ceo_fraud": (
        ["Quick favour", "Are you available?", "Urgent request - confidential", "Need your help today"],
        [["Hi {first}, are you at your desk? I need a quick favour.", "I'm in a meeting and can't talk, but I need something done today.",
          "I need you to handle a confidential task for me."],
         ["Please buy 5 gift cards of 100 EUR each for a client and send me the codes.",
          "I need you to process a payment of {amount} EUR to a new supplier before end of day.",
          "Keep this between us for now, I will explain later."],
         ["Reply to me directly, not to my office email.", "Let me know as soon as it's done.", "It's urgent."],
         ["Sent from my iPhone", "{sender}", "Thanks"]],
    ),
}


def generate(rng, spec, label):
    rows = []
    for category, (subjects, pools) in spec.items():
        for _ in range(PER_CATEGORY):
            parts = [fill(rng, r(rng, GREET))] + [fill(rng, r(rng, pool)) for pool in pools] + [r(rng, FOOTERS)]
            sep = r(rng, ["\n", "\n\n", " "])
            rows.append({"subject": fill(rng, r(rng, subjects)), "body": sep.join(p for p in parts if p),
                         "label": label, "category": category})
    return rows


def main() -> None:
    rng = random.Random(SEED)
    rows = generate(rng, LEGIT, 0) + generate(rng, PHISH, 1)
    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["subject", "body", "label", "category"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} emails ({sum(r['label'] == 0 for r in rows)} legit, "
          f"{sum(r['label'] == 1 for r in rows)} phishing) to {OUT}")


if __name__ == "__main__":
    main()
