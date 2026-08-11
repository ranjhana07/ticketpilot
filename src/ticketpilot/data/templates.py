from __future__ import annotations

ORDER_INTENTS = ("billing_refund", "order_status", "invoice_request")

SUBJECTS: dict[str, list[str]] = {
    "billing_refund": ["Refund request", "Charged twice", "Wrong charge on my card", "Please refund {order}"],
    "order_status": ["Where is my order?", "Order {order} still pending", "Add-on not activated", "Status of {order}"],
    "invoice_request": ["Invoice needed", "Receipt for {order}", "Invoice with VAT number", "Past invoices"],
    "password_reset": ["Can't log in", "Password reset not arriving", "Reset link expired", "Locked out, forgot password"],
    "account_locked": ["Account locked", "Account suspended message", "Team locked out", "2FA not working"],
    "cancel_subscription": ["Cancel subscription", "Please cancel our plan", "Stop renewal", "Closing our account"],
    "change_plan": ["Upgrade question", "Plan change", "Downgrade request", "Switch to annual"],
    "bug_report": ["Bug: board crashes", "Export is broken", "Duplicate notifications", "Something is wrong with search"],
    "feature_request": ["Feature request", "Idea for the roadmap", "Request: Gantt view", "SSO support?"],
    "data_export": ["Data export", "Need a copy of our data", "Migration help", "Export times out"],
    "security_report": ["Suspicious activity", "Leaked API token", "Phishing email", "Possible vulnerability"],
    "general_question": ["Quick question", "Question about plans", "Pre-sales question", "Support hours?"],
}

CORES_EN: dict[str, list[str]] = {
    "billing_refund": [
        "I was charged {amount} for order {order} and I want that refunded.",
        "Please refund {amount} on {order}, the add-on was bought by mistake.",
        "We got billed twice for {order}. Can you reverse the duplicate charge?",
        "Requesting a refund for {order}. The extra seats were never provisioned.",
        "The charge of {amount} for {order} looks wrong, I would like my money back.",
        "refund request: {order}, {amount}",
    ],
    "order_status": [
        "Where is the seat pack I ordered? Order {order} still shows pending.",
        "Can you tell me the status of {order}? It has been processing for days.",
        "My add-on purchase {order} was paid but nothing changed in the workspace.",
        "Checking in on {order}, it still says awaiting fulfilment.",
        "{order} has not been activated yet. When will it go live?",
        "Order {order} confirmation arrived but the extra storage is not there.",
    ],
    "invoice_request": [
        "Could you send me the invoice for {order}? Finance needs it for the books.",
        "I need a PDF invoice with our VAT number for {order}.",
        "Please resend the receipt for {order}, the email never arrived.",
        "Our accountant is asking for invoices for the last quarter. How can I download them?",
        "The company name on the invoice for {order} is wrong, please reissue it.",
        "Where can I find past invoices?",
    ],
    "password_reset": [
        "I can't log in and the reset email never shows up.",
        "Please reset my password, I have forgotten it.",
        "The password reset link says it has expired. I need a new one.",
        "I forgot my password and I am not sure which email I signed up with.",
        "reset link not working, please send another",
        "I changed phones and now I can't sign in, I need a password reset.",
    ],
    "account_locked": [
        "My account is locked after too many sign-in attempts.",
        "I keep getting 'account suspended' when I try to log in.",
        "Our whole team is locked out of the workspace since this morning.",
        "Two-factor codes are rejected and now the account is locked.",
        "Sign in fails with a security lock message, please unlock the account.",
        "We got an email saying our account was disabled. Why, and how do we fix it?",
    ],
    "cancel_subscription": [
        "I would like to cancel my subscription before the next renewal.",
        "Please cancel our Team plan, we are moving to another tool.",
        "How do I stop the subscription from renewing? I want to cancel today.",
        "Cancel my plan effective immediately, we no longer need it.",
        "We want to close the subscription at the end of this billing period.",
        "cancel please, budget got cut",
    ],
    "change_plan": [
        "We'd like to upgrade from Team to Business, what happens to billing?",
        "Can you move us to the {plan} plan?",
        "Please downgrade our subscription to {plan}, we only have a few active users.",
        "I want to switch to annual billing on the {plan} plan.",
        "What is the difference between Team and Business? We might upgrade.",
        "Switching plans: put me on {plan} starting next cycle.",
    ],
    "bug_report": [
        "The board view crashes when I drag a card into a filtered column.",
        "Exports to CSV are missing the last column since yesterday's update.",
        "Notifications are arriving twice for every comment.",
        "The timeline shows the wrong dates after I change the time zone.",
        "File uploads over 20 MB fail with a generic error.",
        "Search stopped returning results for archived projects.",
    ],
    "feature_request": [
        "It would be great if you supported recurring tasks with custom intervals.",
        "Is there a plan to add dark mode to the mobile app?",
        "Feature request: let us pin projects to the top of the sidebar.",
        "Could you add a Gantt view? We would use it daily.",
        "Please add SSO with Okta, our security team requires it.",
        "Any chance of a Slack integration for status changes?",
    ],
    "data_export": [
        "I need a full export of our workspace data for an audit.",
        "How can I export all projects and comments before we close the account?",
        "Please send me a copy of all the personal data you hold about me.",
        "Can you produce a JSON export of the workspace? The built-in export times out.",
        "We have to migrate our data to another tool, how do we get everything out?",
        "Requesting an archive of all attachments in our workspace.",
    ],
    "security_report": [
        "I think someone else accessed our workspace, there are logins from a country where we have no staff.",
        "We found an API token posted in a public repo, please revoke it.",
        "I received a phishing email pretending to be from your company.",
        "An unknown device signed in to my account last night.",
        "Found a vulnerability in the share-link feature, who should I send the details to?",
        "Our admin account shows changes we did not make.",
    ],
    "general_question": [
        "What are your support hours?",
        "Do you offer discounts for non-profits?",
        "Does Loomwork integrate with Google Calendar?",
        "Where is customer data stored, and is it in the EU?",
        "How many guests can I invite on the Team plan?",
        "Is there a student plan?",
    ],
}

INTENTS = tuple(CORES_EN)
