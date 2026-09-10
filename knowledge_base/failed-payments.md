---
id: failed-payments
title: Failed payments and retries
category: billing
---

# Failed payments and retries

When a renewal fails we retry automatically and keep your workspace running while we do.

## Retry schedule

- Day 0: the payment fails and the billing contact gets an email.
- Day 3 and day 7: we try again.
- Day 10: the workspace becomes read-only.
- Day 30: the workspace is archived. Data is kept for another 60 days.

## Common causes

- The card expired or was replaced.
- The bank declined an online payment. Ask the bank to allow charges from Loomwork.
- Not enough funds at the time of the attempt.

## Fix it

Update the card under **Settings > Billing > Payment method**. A new attempt starts within the hour and, when it succeeds, the workspace is restored immediately. See [Update your payment method](update-payment-method.md).
