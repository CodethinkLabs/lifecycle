Usage
=====

Installation
------------

For use
~~~~~~~

To install this project for general use, run::

    pip install --user git+https://github.com/CodethinkLabs/lifecycle

It can then be run with::

    lifecycle <args...>

For testing
~~~~~~~~~~~

To set up this project for testing locally::

    git clone https://github.com/CodethinkLabs/lifecycle

    cd lifecycle

    python3 -m venv .venv
    . .venv/bin/activate && \
        pip install pipenv && \
        pipenv install && \
        pre-commit install

It can then be run with::

    pipenv run lifecycle <args...>


Config
------

Configuration can be read from a single file, or a directory containing multiple .yml files.


One config file
~~~~~~~~~~~~~~~

A single config file name config.yml might contain::

    groups_patterns:
        - "^.*$$"
    source:
      module: StaticConfig
      groups:
        - name: foobar
      users:
        - username: johnsmith
          fullname: "John Smith"
          groups: ["foobar"]
          email: ["john.smith@example.org", "john.smith@example.test"]
        - username: jimsmyth
          fullname: "Jim Griff"
          email: ["jim.smyth@example.org"]
    targets:
      - module: SuiteCRM
        url: http://127.0.0.1:8080
        api_username: user
        api_password: password
        api_client_id: ffff-dddd-c0fe
        api_client_secret: mysecret
        excluded_usernames:
          - "user"

This can be used by running::

    lifecycle -f config.yml

Multiple config files
~~~~~~~~~~~~~~~~~~~~~

As multiple files, this might be:
config/static_source.yml::

    groups_patterns:
        - "^.*$$"
    source:
      module: StaticConfig
      groups:
        - name: foobar
      users:
        - username: johnsmith
          fullname: "John Smith"
          groups: ["foobar"]
          email: ["john.smith@example.org", "john.smith@example.test"]
        - username: jimsmyth
          fullname: "Jim Griff"
          email: ["jim.smyth@example.org"]

config/suitecrm_target.yml::

    targets:
      - module: SuiteCRM
        url: http://127.0.0.1:8080
        api_username: user
        api_password: password
        api_client_id: ffff-dddd-c0fe
        api_client_secret: mysecret
        excluded_usernames:
          - "user"

This can be used by running::

    lifecycle -f config/

Config from environment
~~~~~~~~~~~~~~~~~~~~~~~

Environment variable substitutions will be performed into config files.

For example, a config file name config.yml::

    groups_patterns:
        - "^.*$$"
    source:
      module: StaticConfig
      groups:
        - name: foobar
      users:
        - username: johnsmith
          fullname: "John Smith"
          groups: ["foobar"]
          email: ["john.smith@example.org", "john.smith@example.test"]
        - username: jimsmyth
          fullname: "Jim Griff"
          email: ["jim.smyth@example.org"]
    targets:
      - module: SuiteCRM
        url: ${SUITECRM_URL}
        api_username: user
        api_password: ${SUITECRM_PASSWORD}
        api_client_id: ${SUITECRM_CLIENT_ID}
        api_client_secret: ${SUITECRM_SECRET}
        excluded_usernames:
          - "user"

This can be used by running::

    export SUITECRM_URL=http://127.0.0.1:8080
    export SUITECRM_PASSWORD=password
    export SUITECRM_CLIENT_ID=ffff-dddd-c0fe
    export SUITECRM_SECRET=secret
    lifecycle -f config.yml
