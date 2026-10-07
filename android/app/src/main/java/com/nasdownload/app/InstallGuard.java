package com.nasdownload.app;
public final class InstallGuard {
 private InstallGuard(){}
 public static String command(String raw) {
  String dir=UrlPolicy.absoluteDir(raw);
  return "set -eu; target="+UrlPolicy.quote(dir)+"; current=\"$target\"; "
   +"while [ \"$current\" != / ]; do [ ! -L \"$current\" ] || { echo 'Symlink install target or parent refused' >&2; exit 41; }; if [ -e \"$current\" ]; then [ -d \"$current\" ] || exit 42; resolved=$(readlink -f -- \"$current\"); [ \"$resolved\" = \"$current\" ] || exit 43; fi; current=${current%/*}; [ -n \"$current\" ] || current=/; done; "
   +"if [ -e \"$target\" ]; then [ -d \"$target\" ] || exit 44; entries=$(ls -A -- \"$target\") || exit 45; if [ -n \"$entries\" ]; then [ ! -L \"$target/.nas-download-install\" ] && [ -f \"$target/.nas-download-install\" ] && [ \"$(cat -- \"$target/.nas-download-install\")\" = nas-download-v1 ] || { echo 'Occupied directory is not a Nas Download installation' >&2; exit 46; }; fi; fi";
 }
}
