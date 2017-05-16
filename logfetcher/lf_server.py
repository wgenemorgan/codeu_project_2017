#!/usr/bin/python

# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import fileinput
import os
import Queue
import SocketServer
import subprocess
import sys
import threading
import time

# Keep a single thread at a time.
class ThreadState(object) :

  def __init__(self) :
    self.thread_active = False
    self.curr_thread = None
    self.sub_handle = None

  def setSubHandle(self, sub_handle) :
    self.sub_handle = sub_handle

  def startThread(self, curr_thread) :
    self.curr_thread = curr_thread
    self.curr_thread.daemon = True
    self.curr_thread.start()
    self.thread_active = True
    print ("INFO: thread started")

  def activeThread(self) :
    return self.thread_active

  def shutdownThread(self) :
    if self.thread_active :
      self.sub_handle.terminate()
      self.curr_thread.join()
      self.thread_active = False
      print("INFO: thread shutdown")
    else :
      print("INFO: thread not active")

# Socket Server for fetching the log.
# Support two basic commands -
#   pull - the client pulls the entire log and exits.
#   watch - the client performs the equivalent of "tail -f" on the log.
#

# Runs in thread to receive input from logfile and place into queue
def handleRead(filename, q, TS) :
  sub_handle = subprocess.Popen(['tail', '-F', '--bytes=4K', filename],\
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
  TS.setSubHandle(sub_handle)
  while True :
    line = sub_handle.stdout.readline()   # blocking call
    if len(line) == 0 :
      print("INFO: readline aborted")
      return
    q.put(line)

class LogFetchTcpHandler(SocketServer.StreamRequestHandler) :

  # Write the entire file back to the client.
  def pull(self, filename) :
    for line in fileinput.input([filename]):
      self.wfile.write(line)

  # Read the tail of the file and write back to the client.
  # If no one is writing to the file, the readline() will block.
  # If readline stays blocked for 30 seconds, stop and clean up.
  def watch(self, filename) :
    global TS
    if os.path.isfile(filename) :
      if TS.activeThread() :
        TS.shutdownThread()
      q = Queue.Queue()
      curr_thread = threading.Thread(target=handleRead, args=(filename, q, TS))
      TS.startThread(curr_thread)

      idle_time = time.time()
      while True :
        if q.empty() :
          # check for timeout
          if (time.time() - idle_time) > 30 :
            try:
              self.wfile.write("no activity for 30 seconds - timing out")
            except e:
              TS.shutdownThread()
            return
          time.sleep(1)
        else :
          line = q.get()
          idle_time = time.time()
          try:
            self.wfile.write(line)
          except e:
            TS.shutdownThread()

  # Socket Server handler.
  # Read a command from the client ( p|w[r] )
  #   p = pull, w = watch, r, if present, use relay log.
  def handle(self) :
    global PATH	    
    self.command = self.rfile.readline().strip()
    filename = 'chat_relay_log.log' if ('r' in self.command) \
					else 'chat_server_log.log'
    filename = PATH + filename
    print "CMD: ", self.command, ":", filename
    if ('p' in self.command) :
      self.pull(filename)
    elif ('w' in self.command) :
      self.watch(filename)

class MySocketServer(SocketServer.TCPServer) :

  def __init__(self, addr, handler, thread_state) :
    self.ts = thread_state
    SocketServer.TCPServer.__init__(self, addr, handler)


  def handle_error(self, request, address) :
    self.ts.shutdownThread()
    SocketServer.TCPServer.handle_error(self, request, address)

def main(args) :
  port = 2009

  HOST, PORT = "localhost", port
  global PATH
  global TS
  TS = ThreadState()
  PATH = '/bin/'

  # This allows the server script to be started while a previous
  # run is still holding resources. But it doesn't always work.
  SocketServer.allow_reuse_address = True

  server = MySocketServer((HOST, PORT), LogFetchTcpHandler, TS)
  #SocketServer.TCPServer((HOST, PORT), LogFetchTcpHandler)

  # Process client requests until stopped
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    server.shutdown()
    server.socket.close()
  finally:
    server.server_close()

if __name__ == "__main__" :
   main(sys.argv[1:])
