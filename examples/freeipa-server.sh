#!/bin/bash
set -eux

# This is a basic script that will create a freeipa server in a container,
# populate it with some testing data, then run lifecycle against it.

# It relies on podman and pipenv, but doesn't guarantee a headache-free,
# self-contained testing experience, and is more useful as a starting point
# for testing Lifecycle in something more closely resembling the real world
# than a unit test.

if ! command -v podman &>/dev/null; then
    echo "podman could not be found"
    exit
fi

if ! command -v pipenv &>/dev/null; then
    "pipenv could not be found. Check the contents of CONTRIBUTING.md"
    exit
fi

# Delete the old data, if it exists
sudo rm -rf /var/lib/ipa-data
sudo mkdir /var/lib/ipa-data

# Generate a random password
PASSWORD="$(tr -dc A-Za-z0-9 </dev/urandom | head -c 13)"

echo "This container's admin password is ${PASSWORD}"

LAST_CHECKED="$(date +%s)"

# Start the freeipa server container and leave it to start up in the background
CONTAINER="$(sudo podman run --detach -h ipa.example.test --read-only \
    -v /var/lib/ipa-data:/data:Z \
    -e PASSWORD=${PASSWORD} \
    docker.io/freeipa/freeipa-server:rocky-9 ipa-server-install -U -r EXAMPLE.TEST --no-ntp)"


sleep 1

# The container doesn't exit once it's finished setting up, so watch for it to finish configuring
set +x
echo "Waiting for container setup to finish..."
while [ "x$(sudo podman exec -it "${CONTAINER}" systemctl is-active ipa-server-configure-first.service | tr -d '\r')" = xactivating ]; do
    sudo podman logs --since="${LAST_CHECKED}" "${CONTAINER}"
    LAST_CHECKED="$(date +%s)"
    sleep 1
done
set -x

echo "Restarting the container because kerberos is a bit fragile"
sudo podman restart "${CONTAINER}"

sleep 5

echo "Configuring FreeIPA users"
sudo podman exec -it "${CONTAINER}" /bin/bash -c "echo ${PASSWORD} | kinit admin && ipa user-add testuser --first=Test --last=User"
sudo podman exec -it "${CONTAINER}" /bin/bash -c "echo ${PASSWORD} | kinit admin && ipa user-add testuser2 --first=Test2 --last=User"
sudo podman exec -it "${CONTAINER}" /bin/bash -c "echo ${PASSWORD} | kinit admin && ipa group-add testgroup"
sudo podman exec -it "${CONTAINER}" /bin/bash -c "echo ${PASSWORD} | kinit admin && ipa group-add-member testgroup --users=testuser"

sleep 5

CONTAINER_IP="$( sudo podman inspect --format '{{ .NetworkSettings.IPAddress }}' "${CONTAINER}" )"
echo "Testing LDAP server"
#ldapsearch -H ldap://${CONTAINER_IP} -D uid=admin,cn=users,cn=accounts,dc=example,dc=test -w "${PASSWORD}" '(objectclass=organizationalPerson)'

CONFIGFILE="$(mktemp)"

cat >"${CONFIGFILE}" <<EOF
source:
  module: LDAP3
  url: ldap://${CONTAINER_IP}
  base_dn: cn=accounts,dc=example,dc=test
  bind_dn: uid=admin,cn=users,cn=accounts,dc=example,dc=test
  bind_password: ${PASSWORD}
EOF

pipenv run lifecycle --debug -f "${CONFIGFILE}"
