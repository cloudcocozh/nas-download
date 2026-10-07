#!/bin/sh
# Only installs into an empty directory or this product's marked directory.
set -eu
umask 077
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
DIR= PORT=7120 BIND=0.0.0.0 MODE=bundled DOWNLOADS=
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || { echo '缺少安装参数' >&2; exit 2; }
  case "$1" in
    --dir) DIR=$2;; --port) PORT=$2;; --bind) BIND=$2;;
    --mode) MODE=$2;; --downloads) DOWNLOADS=$2;;
    *) echo '未知安装参数' >&2; exit 2;;
  esac
  shift 2
done
guard_path() {
  value=$1
  case "$value" in /*) ;; *) echo '需要绝对目录' >&2; exit 2;; esac
  case "$value" in /|*//*|*/./*|*/../*|*/.|*/..|*\$*|*\'*|*\"*|*\`*|*:*|*\\*) echo '目录格式不安全' >&2; exit 2;; esac
  [ "$(printf '%s' "$value" | tr -d '\r\n')" = "$value" ] || { echo '目录不能含换行' >&2; exit 2; }
  current=; saved_ifs=$IFS; IFS=/
  for part in $value; do
    [ -n "$part" ] || continue
    current=$current/$part
    [ ! -L "$current" ] || { echo '安装目录不能经过符号链接' >&2; exit 2; }
    if [ -e "$current" ]; then
      [ -d "$current" ] || { echo '目录路径包含文件' >&2; exit 2; }
      [ "$(readlink -f "$current")" = "$current" ] || { echo '目录实际路径不一致' >&2; exit 2; }
    fi
  done
  IFS=$saved_ifs
}
[ -n "$DIR" ] || { echo '请指定 --dir 安装目录' >&2; exit 2; }
DIR=${DIR%/}; guard_path "$DIR"
case "$MODE" in existing|bundled) ;; *) echo '安装模式无效' >&2; exit 2;; esac
case "$PORT" in ''|*[!0-9]*) echo '端口无效' >&2; exit 2;; esac
[ "$PORT" -ge 1024 ] && [ "$PORT" -le 65534 ] || { echo '端口需为 1024 到 65534' >&2; exit 2; }
case "$BIND" in ''|*[!0-9.]*) echo '绑定地址须为 IPv4 地址' >&2; exit 2;; esac
printf '%s\n' "$BIND" | awk -F. 'NF != 4 {exit 1} {for (i=1;i<=4;i++) if ($i == "" || $i > 255) exit 1}' || { echo '绑定地址无效' >&2; exit 2; }
if [ -d "$DIR" ] && [ -n "$(ls -A "$DIR")" ]; then
  [ ! -L "$DIR/.nas-download-install" ] && [ -f "$DIR/.nas-download-install" ] && [ "$(cat "$DIR/.nas-download-install")" = nas-download-v1 ] || { echo '目标目录已有其他文件，请选择新的空目录' >&2; exit 2; }
fi
if [ -f "$DIR/.nas-download-mode" ] && [ "$(cat "$DIR/.nas-download-mode")" != "$MODE" ]; then
  echo '现有安装模式不同，请选择新的安装目录；不会替换已有下载器' >&2; exit 2
fi
command -v docker >/dev/null || { echo 'NAS 尚未安装 Docker' >&2; exit 3; }
command -v readlink >/dev/null || { echo 'NAS 缺少 readlink' >&2; exit 3; }
docker compose version >/dev/null || { echo 'NAS 尚未安装 Docker Compose' >&2; exit 3; }
docker info >/dev/null || { echo '当前账户没有 Docker 权限' >&2; exit 3; }
for entry in .env .nas-download-mode data engine-config installer-backups server web deploy Dockerfile compose.yaml compose.bundled.yaml .dockerignore; do
  [ ! -L "$DIR/$entry" ] || { echo '安装内容包含符号链接，请先核对目录' >&2; exit 2; }
done
if [ "$MODE" = bundled ] && [ -z "$DOWNLOADS" ] && [ -f "$DIR/.env" ]; then
  DOWNLOADS=$(sed -n "s/^ND_DOWNLOADS='\(.*\)'$/\1/p" "$DIR/.env")
fi
for state in data engine-config; do
  if [ -d "$DIR/$state" ] && [ -n "$(find "$DIR/$state" -type l -print -quit)" ]; then
    echo '持久状态包含符号链接；未停止任何服务' >&2; exit 2
  fi
done
mkdir -p "$DIR"
if ! mkdir "$DIR/.installer-lock" 2>/dev/null; then
  echo '已有安装正在进行，或上次安装中断留下锁；核对进程后再重试' >&2; exit 3
fi
trap 'rmdir "$DIR/.installer-lock" 2>/dev/null || true' EXIT
IMAGE=nas-download:1.3.0
case "$(uname -m)" in x86_64|amd64) ;; *) echo '此发布包仅验证 x86_64 NAS' >&2; exit 3;; esac
if [ -f "$SOURCE_DIR/nas-download-image.tar.gz" ]; then
  docker load -i "$SOURCE_DIR/nas-download-image.tar.gz" >/dev/null
else
  docker build -t "$IMAGE" "$SOURCE_DIR"
fi
mkdir -p "$DIR/data"
[ -w "$DIR/data" ] || { echo '不能写入服务数据目录' >&2; exit 3; }
UID_VALUE=$(id -u); GID_VALUE=$(id -g)
PROJECT=nasdownload_$(printf '%s' "$DIR" | sha256sum | cut -c1-12)
BOOT=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
ENGINE_PASSWORD=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
if [ -f "$DIR/.env" ]; then
  previous=$(sed -n 's/^ND_SETUP_TOKEN=\([a-f0-9]*\)$/\1/p' "$DIR/.env")
  [ -z "$previous" ] || BOOT=$previous
  previous=$(sed -n 's/^ND_ENGINE_PASSWORD=\([a-f0-9]*\)$/\1/p' "$DIR/.env")
  [ -z "$previous" ] || ENGINE_PASSWORD=$previous
fi
if [ "$MODE" = bundled ]; then
  [ -n "$DOWNLOADS" ] || DOWNLOADS=$DIR/downloads
  DOWNLOADS=${DOWNLOADS%/}; guard_path "$DOWNLOADS"
  case "$DOWNLOADS/" in "$DIR/"|"$DIR/data/"*|"$DIR/engine-config/"*|"$DIR/installer-backups/"*) echo '下载目录不能与程序状态目录重叠' >&2; exit 2;; esac
  case "$DIR/" in "$DOWNLOADS/"*) echo '安装目录不能位于下载目录内' >&2; exit 2;; esac
  mkdir -p "$DOWNLOADS" "$DIR/engine-config"
  probe=$DOWNLOADS/.nas-download-write-test.$$
  (set -C; : > "$probe") 2>/dev/null || { echo '当前账户不能写入下载目录' >&2; exit 3; }
  rm -f "$probe"
fi
# A transaction snapshots only stopped state; it never rewinds downloaded files.
BACKUP= OLD=0 SWITCHED=0 STOPPED=0 RUNNING=
compose() {
  if [ "$MODE" = bundled ]; then
    docker compose -p "$PROJECT" -f "$DIR/compose.yaml" -f "$DIR/compose.bundled.yaml" "$@"
  else
    docker compose -p "$PROJECT" -f "$DIR/compose.yaml" "$@"
  fi
}
rollback() {
  result=$?
  trap - EXIT HUP INT TERM
  if [ "$result" -ne 0 ] && [ "$STOPPED" = 1 ]; then
    echo '验证失败，恢复安装前的配套状态…' >&2
    if [ "$SWITCHED" = 1 ]; then
      if ! compose stop --timeout 180; then
        echo '新进程未确认停止，保留现场，不覆盖运行中的状态' >&2; exit "$result"
      fi
      if [ "$OLD" = 1 ]; then
        mkdir -p "$BACKUP/failed-state"
        for entry in data engine-config; do
          [ ! -d "$DIR/$entry" ] || mv "$DIR/$entry" "$BACKUP/failed-state/$entry"
          [ ! -d "$BACKUP/state/$entry" ] || cp -a "$BACKUP/state/$entry" "$DIR/$entry"
        done
        for entry in .env compose.yaml compose.bundled.yaml Dockerfile .dockerignore install.sh server web deploy; do
          if [ -e "$BACKUP/$entry" ]; then
            [ ! -e "$DIR/$entry" ] || mv "$DIR/$entry" "$BACKUP/failed-state/$entry"
            cp -a "$BACKUP/$entry" "$DIR/$entry"
          fi
        done
      else
        echo '首次安装失败，容器已停止；目录保留供修复' >&2
      fi
    fi
    if [ "$OLD" = 1 ] && [ -n "$RUNNING" ]; then
      if [ -f "$BACKUP/rollback.images.yaml" ]; then
        compose -f "$BACKUP/rollback.images.yaml" up -d --no-build $RUNNING
      else
        compose up -d --no-build $RUNNING
      fi || echo '旧版本恢复启动失败，请保留备份' >&2
    fi
  fi
  rmdir "$DIR/.installer-lock" 2>/dev/null || true
  exit "$result"
}
if [ -f "$DIR/.env" ] && [ -f "$DIR/compose.yaml" ]; then
  OLD=1
  BACKUP=$DIR/installer-backups/$(date +%Y%m%d-%H%M%S)-$$
  mkdir -p "$BACKUP/state"
  for entry in .env compose.yaml compose.bundled.yaml Dockerfile .dockerignore install.sh server web deploy; do
    [ ! -e "$DIR/$entry" ] || cp -a "$DIR/$entry" "$BACKUP/$entry"
  done
  RUNNING=$(compose ps --services --status running)
  for service in nas-download qbittorrent; do
    cid=$(compose ps -aq "$service" 2>/dev/null || true)
    if [ -n "$cid" ]; then
      image_id=$(docker inspect --format '{{.Image}}' "$cid")
      case "$image_id" in sha256:*) ;; *) echo '无法固定旧版本镜像，停止升级' >&2; exit 3;; esac
      [ -f "$BACKUP/rollback.images.yaml" ] || printf 'services:\n' > "$BACKUP/rollback.images.yaml"
      printf '  %s:\n    image: %s\n' "$service" "$image_id" >> "$BACKUP/rollback.images.yaml"
    fi
  done
  trap rollback EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  STOPPED=1
  compose stop --timeout 180
  for entry in data engine-config; do
    if [ -d "$DIR/$entry" ]; then
      cp -a "$DIR/$entry" "$BACKUP/state/$entry"
      diff -qr "$DIR/$entry" "$BACKUP/state/$entry" >/dev/null
    fi
  done
  printf '%s\n' "$RUNNING" > "$BACKUP/previously-running"
else
  trap rollback EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
fi
SWITCHED=1
if [ "$SOURCE_DIR" != "$DIR" ]; then
  for entry in server web deploy; do
    if [ -d "$DIR/$entry" ]; then
      mkdir -p "$DIR/installer-backups/replaced-$$"
      mv "$DIR/$entry" "$DIR/installer-backups/replaced-$$/$entry"
    fi
    cp -R "$SOURCE_DIR/$entry" "$DIR/"
  done
  for entry in Dockerfile compose.yaml compose.bundled.yaml .dockerignore install.sh; do cp "$SOURCE_DIR/$entry" "$DIR/$entry"; done
fi
printf '%s\n' nas-download-v1 > "$DIR/.nas-download-install"
printf '%s\n' "$MODE" > "$DIR/.nas-download-mode"
cat > "$DIR/.env" <<EOF
ND_UID=$UID_VALUE
ND_GID=$GID_VALUE
ND_BIND=$BIND
ND_PORT=$PORT
ND_SETUP_TOKEN=$BOOT
ND_ENGINE_PASSWORD=$ENGINE_PASSWORD
ND_PEER_PORT=$((PORT + 1))
ND_DOWNLOADS='$DOWNLOADS'
EOF
chmod 600 "$DIR/.env"
compose config --quiet
docker run --rm --network host --env-file "$DIR/.env" -v "$DIR/deploy/check_ports.py:/check_ports.py:ro" "$IMAGE" python /check_ports.py "$MODE" || { echo '安装端口被占用或绑定地址不可用' >&2; exit 3; }
printf '%s\n' installing > "$DIR/data/.install-maintenance"
STOPPED=1
compose up -d --no-build nas-download
healthy=0
for attempt in $(seq 1 45); do
  if compose exec -T nas-download python -c "import urllib.request,json; h=json.load(urllib.request.urlopen('http://127.0.0.1:7120/api/v1/health',timeout=3)); assert h.get('ok') is True and h.get('name') == 'Nas Download' and h.get('version') == '1.3.0'" >/dev/null 2>&1; then healthy=1; break; fi
  sleep 2
done
[ "$healthy" = 1 ] || { echo '服务或引擎未就绪，未启用自动任务' >&2; exit 4; }
rm -f "$DIR/data/.install-maintenance"
rmdir "$DIR/.installer-lock"
trap - EXIT HUP INT TERM
[ -z "$BACKUP" ] || printf 'NAS_DOWNLOAD_BACKUP=%s\n' "$BACKUP"
printf 'NAS_DOWNLOAD_READY=http://%s:%s\n' "$BIND" "$PORT"
printf 'NAS_DOWNLOAD_SETUP_CODE=%s\n' "$BOOT"
printf 'NAS_DOWNLOAD_PROJECT=%s\n' "$PROJECT"
