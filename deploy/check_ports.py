"""Verify host port availability without leaving a listening process."""
import os
import socket
import sys

opened = []
try:
    ports = [(os.environ['ND_BIND'], int(os.environ['ND_PORT']), socket.SOCK_STREAM)]
    if sys.argv[1] == 'bundled':
        ports += [('0.0.0.0', int(os.environ['ND_PEER_PORT']), kind)
                  for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM)]
    for address, port, kind in ports:
        sock = socket.socket(socket.AF_INET, kind)
        opened.append(sock)
        sock.bind((address, port))
except OSError as exc:
    print(f'端口检查失败: {address}:{port}: {exc}', file=sys.stderr)
    sys.exit(3)
finally:
    for sock in opened:
        sock.close()
