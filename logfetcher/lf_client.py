import socket
import sys

HOST, PORT = "130.211.140.178", 10109

data = " ".join(sys.argv[1])

if ('p' in data) :
  outfile = " ".join(sys.argv[2:])

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def watch():
  try:
    sock.connect((HOST, PORT))
    sock.sendall(data + "\n")

    while (True):
      buffer = sock.recv(1024)
      if (len(buffer) == 0):
        break
      print buffer,

  finally:
    sock.close()

def pull():
  try:
    sock.connect((HOST, PORT))
    sock.sendall(data + "\n")

    with open(outfile, 'w') as f:
      while (True):
        buffer = sock.recv(4096)
        if (len(buffer) == 0):
          break
        f.write(buffer)

  finally:
    sock.close()

if ('p' in data):
  pull()
elif ('w' in data):
  watch()
else:
  print "Usage: lf_client p(ull)|w(atch)[r(elay)] [output-filename-for-pull]"
  exit()
