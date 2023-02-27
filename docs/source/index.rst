User Lifecycle Management
=========================

`lifecycle` is a piece of software intended to help implement the [Single Source of Truth](https://en.wikipedia.org/wiki/Single_source_of_truth) principle across disparate applications and services.  It is intended to be used alongside a single-sign-on authentication system such as SAML or OIDC, and provide lifecycle management for the users in these applications.

Why?
----

Some software we use doesn't have good user lifecycle management.  While we can use SSO to log into
these pieces of software, we end up with ghost users, manual user and role management, and worse of all, users
with non-sso authentication methods.

How?
----

The application is intended to be run in an automated scheduled fashion.  A docker container will be provided where a config volume can be mounted to configure your applications.


Contents
--------

.. toctree::

   api
