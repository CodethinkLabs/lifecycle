#!/usr/bin/sh

# TODO: Is it worth the time to rewrite this to generate a docker-compose
# file and insert variables into it, instead of hardcoding usernames
# and passwords?

set -e

# Enable process control so that backgrounded docker-compose can be foregrounded later
set -m

COMMANDS="docker docker-compose openssl jq"
for command in $COMMANDS; do
  if ! command -v "$command" >/dev/null; then
    echo "$command could not be found"
    exit
  fi
done

CURDIR="$(realpath "$(dirname "$0")")"
cd $CURDIR

LIFECYCLE_CONFIG_FILE="suitecrm.yml"
if [ -z "$LIFECYCLE_CONFIG_PATH" ]; then
  LIFECYCLE_CONFIG_PATH="$CURDIR/$LIFECYCLE_CONFIG_FILE"
  echo "LIFECYCLE_CONFIG_PATH not found, defaulting to '$LIFECYCLE_CONFIG_PATH'"
fi

if [ -z "$ERASE_VOLUMES" ]; then
  echo "ERASE_VOLUMES not found, set 'ERASE_VOLUMES=yes' in the environment to erase suitecrm volumes before starting the containers"
fi

echo "Ensuring bitnami docker container is checked-out and patched"
git submodule update --init
cd bitnami-containers
git reset --hard HEAD
git checkout 4d2110be
sed -i 's/php-8.*-debian-11/php-7.4.33-0-linux-${OS_ARCH}-debian-11/' bitnami/suitecrm/7/debian-11/Dockerfile
cd ..

sudo docker-compose down
if [ "x$ERASE_VOLUMES" = "xyes" ]; then
  echo "Erasing old suitecrm volumes"
  sudo docker volume rm suitecrm_mariadb_data suitecrm_suitecrm_data
fi

echo "Starting new suitecrm containers"
sudo docker-compose up >/dev/null 2>&1 &

sleep 5

# Insert OAuth2 keys
KEYDIR="$(sudo docker inspect suitecrm_suitecrm_1 | jq -r .[0].Mounts[0].Source)/Api/V8/OAuth2"
# wait until directory exists
echo "Waiting for "$KEYDIR" to exist..."
while ! sudo test -d "$KEYDIR"; do
  sleep 1
done
echo "Adding new OAuth2 RSA keys"
sudo openssl genrsa -out "$KEYDIR/private.key" 2048
sudo openssl rsa -in "$KEYDIR/private.key" -pubout -out "$KEYDIR/public.key"
sudo chown 1:1 "$KEYDIR/private.key" "$KEYDIR/public.key"
sudo chmod 0660 "$KEYDIR/public.key"

echo "Configuring OAuth2 user entry"
# Configure an OAuth2 user
OAUTH_USER_NAME="user"
OAUTH_CLIENT_ID=c1c3dfd8-2e58-b193-5fcb-63f5fdcd6903
OAUTH_CLIENT_NAME=testuser
OAUTH_CLIENT_SECRET="mysecret"
OAUTH_CLIENT_SECRET_SUM="$(echo -n "$OAUTH_CLIENT_SECRET" | sha256sum | awk '{print $1}')"
sudo docker exec -i suitecrm_mariadb_1 mysql --user=bn_suitecrm --password=bitnami123 --database=bitnami_suitecrm <<EOF
INSERT INTO oauth2clients
(
  id,
  name,
  modified_user_id,
  created_by,
  secret,
  duration_value,
  duration_amount,
  duration_unit
)
VALUES
(
  '${OAUTH_CLIENT_ID}',
  '${OAUTH_CLIENT_NAME}',
  (select id from users where user_name='${OAUTH_USER_NAME}'),
  (select id from users where user_name='${OAUTH_USER_NAME}'),
  '${OAUTH_CLIENT_SECRET_SUM}',
  60,
  1,
  'minute'
)
ON DUPLICATE KEY UPDATE
  name='${OAUTH_CLIENT_NAME}',
  secret='${OAUTH_CLIENT_SECRET_SUM}',
  duration_value=60,
  duration_amount=1,
  duration_unit='minute'
;
EOF

sudo docker restart suitecrm_suitecrm_1

echo "SuiteCRM server started up! Lifecycle Target config written to '$LIFECYCLE_CONFIG_PATH'"

cat >"$LIFECYCLE_CONFIG_PATH" <<EOF
targets:
  - module: SuiteCRM
    url: http://127.0.0.1:8080
    api_username: user
    api_password: bitnami
    api_client_id: ${OAUTH_CLIENT_ID}
    api_client_secret: ${OAUTH_CLIENT_SECRET}
    excluded_usernames:
      - "${OAUTH_USER_NAME}"
EOF

echo "Reattaching docker-compose process, terminate with Ctrl-C"
fg

echo "Tidying up containers"
rm -f "$LIFECYCLE_CONFIG_PATH"
