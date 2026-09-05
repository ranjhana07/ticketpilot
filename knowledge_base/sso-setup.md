---
id: sso-setup
title: Set up single sign-on
category: security
---

# Set up single sign-on

Single sign-on (SSO) is available on Business and Enterprise plans and works with any SAML 2.0 provider, including Okta, Microsoft Entra ID and Google Workspace.

## Steps

1. In **Settings > Security > Single sign-on** copy the ACS URL and entity ID.
2. Create a SAML app in your identity provider and paste both values.
3. Upload the identity provider metadata or paste its metadata URL.
4. Test with the **Test connection** button before enforcing.
5. Turn on **Require SSO** when you are ready. Members must then sign in through the provider.

## Notes

- Owners keep a password fallback so that a configuration mistake cannot lock everyone out.
- SCIM provisioning is available on Enterprise.
- The Team plan does not include SSO. See [Plans and pricing](plans-overview.md).
