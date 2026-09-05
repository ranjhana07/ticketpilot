---
id: api-tokens
title: API tokens
category: security
---

# API tokens

Personal API tokens let scripts and integrations act as you.

## Create a token

Open **Profile > API tokens** and choose **New token**. Give it a name and the narrowest scope that works. The token is shown once, so copy it straight away.

## Revoke a token

Select **Revoke** next to the token. It stops working within a minute. Revoke every token you are unsure about, then create new ones.

## A token was exposed

If a token was committed to a public repository or pasted in a chat:

1. Revoke it immediately. Removing the commit is not enough, because the value stays in the history.
2. Create a replacement and update the services that used it.
3. Check the audit log for requests you do not recognise.

Tokens begin with `lw_` so that secret scanners can detect them. Loomwork rotates tokens it detects in public GitHub repositories and emails the owner.
