#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-newslens}"
APP_GROUP="${APP_GROUP:-newslens}"
APP_ROOT="${APP_ROOT:-/srv/newslens}"
APP_DIR="${APP_DIR:-${APP_ROOT}/app}"
VENV_DIR="${VENV_DIR:-${APP_ROOT}/venv}"
NLTK_DATA_DIR="${NLTK_DATA_DIR:-${APP_ROOT}/nltk_data}"
ENV_DIR="${ENV_DIR:-/etc/newslens}"
ENV_FILE="${ENV_FILE:-${ENV_DIR}/newslens.env}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root."
  exit 1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  echo "Expected app directory at ${APP_DIR}."
  echo "Clone the NewsLens repo there before running this bootstrap script."
  exit 1
fi

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 is required but not installed."
  echo "Ubuntu 24.04 defaults to Python 3.12, so install Python 3.11 explicitly first."
  exit 1
fi

apt-get update
apt-get install -y nginx git build-essential curl ca-certificates
if ! command -v node >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)' >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

if ! getent group "${APP_GROUP}" >/dev/null; then
  groupadd --system "${APP_GROUP}"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --gid "${APP_GROUP}" --create-home --home-dir "${APP_ROOT}" --shell /bin/bash "${APP_USER}"
fi

mkdir -p "${APP_ROOT}" "${ENV_DIR}" "${NLTK_DATA_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_ROOT}"

python3.11 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
runuser -u "${APP_USER}" -- env NLTK_DATA="${NLTK_DATA_DIR}" \
  "${VENV_DIR}/bin/python" -m nltk.downloader -d "${NLTK_DATA_DIR}" \
  stopwords punkt wordnet vader_lexicon punkt_tab

(
  cd "${APP_DIR}"
  env NLTK_DATA="${NLTK_DATA_DIR}" "${VENV_DIR}/bin/python" -m src.cache_models
)

runuser -u "${APP_USER}" -- npm --prefix "${APP_DIR}/frontend-node" ci
runuser -u "${APP_USER}" -- env NEXT_PUBLIC_NEWS_API_BASE_URL="http://127.0.0.1:9000" \
  npm --prefix "${APP_DIR}/frontend-node" run build

if [[ ! -f "${ENV_FILE}" ]]; then
  install -m 640 -o root -g "${APP_GROUP}" "${APP_DIR}/.env.example" "${ENV_FILE}"
fi

install -m 644 "${APP_DIR}/deploy/droplet/newslens.service" /etc/systemd/system/newslens.service
install -m 644 "${APP_DIR}/deploy/droplet/newslens-api.service" /etc/systemd/system/newslens-api.service
install -m 644 "${APP_DIR}/deploy/droplet/newslens-node.service" /etc/systemd/system/newslens-node.service
install -m 644 "${APP_DIR}/deploy/droplet/nginx.newslens.conf" /etc/nginx/sites-available/newslens

ln -sf /etc/nginx/sites-available/newslens /etc/nginx/sites-enabled/newslens
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable newslens newslens-api newslens-node
systemctl restart newslens
systemctl restart newslens-api
systemctl restart newslens-node
nginx -t
systemctl restart nginx

echo "Bootstrap complete."
echo "Edit ${ENV_FILE} if you want custom RSS settings."
echo "Check status with: systemctl status newslens newslens-api newslens-node --no-pager"
