Redis Monitor Server
====================

Redis Monior is a stand alone server written to monitor one or multiple redis servers. Its primary use is to allow you to automate the testing of applications that interface directly with [Redis](http://www.redis.io)

## Contents
 * [Download] (https://github.com/ninjapenguin/redis-monitor-server/#download)
 * [Installation] (https://github.com/ninjapenguin/redis-monitor-server/#installation)
 * [Quickstart] (https://github.com/ninjapenguin/redis-monitor-server/#quickstart)

## Download

Download one liner:

```bash
git clone https://github.com/ninjapenguin/redis-monitor-server.git
````

## Installation

To install dependencies

 ```bash
 pip install -r requirements.txt
 ````

## Quickstart

### Option 1: Bootstrapping via python RedisMonitor class

```python
rm = RedisMonitor(redis_ports=[6997,6998])

# do a test
rm.get_last_command()	# returns the last command run accross all instances
rm.get_last_command_by_instance(6997)	# returns the last command run on instance @ port 6997
rm.get_all_commands()	# returns all commands run to date

rm.reset()	# reset the current lists..

# do another test...

rm.shutdown()
````

### Option 2: Run the server manually and connect externally

To start the redis monitoring server listening on two local ports:

```bash
python monitor.py --redis_port 6997 6998
````

You are then able to communicate with server using zmq REQ socket directly:

#### Python

```python
import zmq
context = zmq.Context()

socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5559")
socket.send('last')
response = socket.recv()
# response == u'keys *'
````

#### Lua

```lua
require "zmq"
local context = zmq.init(1)
local socket = context:socket(zmq.REQ)
socket:connect("tcp://localhost:5559")
socket:send('last')
local response = socket:recv()
````