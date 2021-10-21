# User Lifecycle Management

`lifecycle` is a piece of software intended to help implement the [Single Source of Truth](https://en.wikipedia.org/wiki/Single_source_of_truth) principle across disparate applications and services.  It is intended to be used alongside a single-sign-on authentication system such as SAML or OIDC, and provide lifecycle management for the users in these applications.

## Why?

Some software we use doesn't have good user lifecycle management.  While we can use SSO to log into
these pieces of software, we end up with ghost users, manual user and role management, and worse of all, users
with non-sso authentication methods.

## How?

The application is intended to be run in an automated scheduled fashion.  A docker container will be provided where a config volume can be mounted to configure your applications. 

## Layout

A typical workflow for `lifecycle` will have one `source`, such as LDAP or a CSV file, and multiple `targets`, such as Google Apps or SuiteCRM.  The entire user and group list will be extracted from the `source`, and used to set up the `target` in a matching way.  This can include adding and removing users, changing contact details and disabling user accounts.

Ideally if a target has an access-level system thats vaguely sensible, we can manage a user's access too - a `target` will manage `roles` within its application, and make sure users are in the correct `roles` as specified in `source`

# User Stories

## User Creation

1) Alice starts at company, and has an LDAP account created for them by Bob.
2) When lifecycle is next run, it pulls Alice's account details from LDAP, and uses them to create a matching user for them in SuiteCRM.
3) Alice is able to log into SuiteCRM immediately via SAML, and has the correct permissions and access.

## User Disablement

1) Charlie decides to move on from company, and on their final day their LDAP account is disabled.
2) When lifecycle is next run, it notices Charlie's LDAP account is disabled, and disables their SuiteCRM access.
3) Charlie is no longer able to authenticate to SuiteCRM, and they no longer show up as a valid user for other SuiteCRM users.

## User Access Change

1) David moves from the engineering department to the sales department, and is added to the sales group
2) When lifecycle is next run, it will modify David's roles to give them access to sales specific functionality within SuiteCRM.
3) David is able to log into SuiteCRM and has correct access.
