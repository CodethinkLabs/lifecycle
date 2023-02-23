# Contributing to lifecycle

tl;dr: Open an issue, send a MR.  If it isn't getting looked at poke in #lifecycle.

If something isn't part of the project spec, or hasn't been discussed beforehand
it might not get merged, beware!

Chat to us in #lifecycle if you've got any ideas you're interested in contributing.

## Development

### Python Environment

To set up a local development environment, create a python virtual environment,
using `venv` or similar, e.g.:

    python3 -m venv .venv

To then configure the development environment run:

    . .venv/bin/activate && \
        pip install pipenv && \
        pipenv install && \
        pre-commit install && \

### FreeIPA or LDAP

When developing code to use with a FreeIPA server, the script in
examples/freeipa-server.sh will be a useful starting point in having
a small FreeIPA or LDAP server to test against.

### SuiteCRM

Docker-compose instructions for SuiteCRM have been provided in examples/suitecrm.
That starts a web server accessible via localhost, where suitecrm can
be logged into with username 'user' and password 'bitnami'.

The script examples/suitecrm/suitecrm.sh will build the container from scratch
and populate it with data.

Because we have experienced issues with suitecrm in the container crashing, and
no guarantees that the REST API is stable, the suitecrm.sh script changes the
container's PHP version, and uses a very specific commit.
If you experience difficulties using the SuiteCRM target module, it may be
because of suitecrm API changes.

## Merge Requests

* Must have `black` run against every commit.  This is enforced by CI.
* Must pass pylint linting
* Should have tests where possible
* Should have their history rewritten to group things nicely together.
* Should have inline documentation such that readthedocs or similar documentation
  sites can generate documentation
