import redis
from multiprocessing import Process
import argparse
import zmq
import time
import json


class Monitor():
    """
        Redis monitor class
        all credit goes to: SO answer here - http://stackoverflow.com/questions/10458146/how-can-i-mimic-the-redis-monitor-command-in-a-python-script-using-redis-py
    """
    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
        self.connection = None

    def __del__(self):
        try:
            self.reset()
        except:
            pass

    def reset(self):
        if self.connection:
            self.connection_pool.release(self.connection)
            self.connection = None

    def monitor(self):
        if self.connection is None:
            self.connection = self.connection_pool.get_connection('monitor', None)
        self.connection.send_command("monitor")
        return self.listen()

    def parse_response(self):
        return self.connection.read_response()

    def listen(self):
        while True:
            yield self.parse_response()


class RedisEmitterProcess(Process):
    """
        Class to monitor a redis instance and emit the observed commands
    """

    def __init__(self, redis_port=7171, command_server_port=5559, emit_port=5556, name="MonitorProcess"):
        Process.__init__(self, name=name)

        self.redis_port = redis_port
        self.emit_port = emit_port
        self.command_server_port = command_server_port

    def run(self):
        context = zmq.Context()

        # register this emitter
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://localhost:{}".format(self.command_server_port))
        socket.send('register {}'.format(self.redis_port))
        ret = socket.recv()

        # already have an emitter so dont startup
        if ret != 'True':
            return False

        pool = redis.ConnectionPool(host='localhost', port=self.redis_port, db=0)
        monitor = Monitor(pool)
        commands = monitor.monitor()

        # setup the publish
        sender = context.socket(zmq.PUSH)
        sender.connect("tcp://localhost:{}".format(self.emit_port))

        for c in commands:
            if c == 'OK':
                continue
            sender.send("({}) - {}".format(self.redis_port, c))


class CommandServer(Process):
    """
        Listens to redis emitters and answers queries on observed redis
        actions performed on them
    """

    def __init__(self, emit_in_port=5556, admin_port=5559, name="CommandProcess"):
        Process.__init__(self, name=name)
        self.emit_in_port = emit_in_port
        self.admin_port = admin_port
        self.l_commands = {}
        self.command_stack = []

    def run(self):
        context = zmq.Context()

        # attempt to listen on command interface
        admin = context.socket(zmq.REP)
        try:
            admin.bind("tcp://*:{}".format(self.admin_port))
        except Exception, e:
            return False

        # Connect to monitoring server
        receiver = context.socket(zmq.PULL)
        receiver.bind("tcp://*:{}".format(self.emit_in_port))

        # Initialize poll set
        poller = zmq.Poller()
        poller.register(admin, zmq.POLLIN)
        poller.register(receiver, zmq.POLLIN)

        while True:
            socks = dict(poller.poll())

            if admin in socks and socks[admin] == zmq.POLLIN:
                message = admin.recv()
                admin.send(self.serve_command(message))

            if receiver in socks and socks[receiver] == zmq.POLLIN:
                message = receiver.recv()

                redis_instance = self.determine_redis_instance(message)
                message = self.clean_message(message)

                if redis_instance not in self.l_commands:
                    self.l_commands[redis_instance] = []

                # record all commands in stack
                self.command_stack.append(message)

                # record commands by instance
                self.l_commands[redis_instance].append(message)

    def determine_redis_instance(self, message):
        return message[0:message.index(')')+1].strip('()')

    def clean_message(self, message):

        return message[message.index(']')+1:].strip(' "').replace('" ', ' ').replace(' "', ' ')

    def serve_command(self, command_raw):

        command_args = command_raw.strip().split(' ')
        command = command_args[0]

        if (command == 'register'):
            return self.register_emitter(command_args[1])

        if (command == 'last'):
            return self.get_last()

        if (command == 'last_by_instance'):
            return self.get_last_by_instance(command_args[1])

        if (command == 'all'):
            return self.list_all()

        if (command == 'reset'):
            return self.reset()

        if (command == 'ping'):
            return 'pong'

        return "COMMAND_UNKNOWN"

    def register_emitter(self, redis_port):

        if redis_port in self.l_commands:
            return 'False'
        else:
            self.l_commands[redis_port] = []
            return 'True'

    def list_all(self):
        return json.dumps(self.command_stack)

    def reset(self):
        self.command_stack = []
        self.l_commands = []
        return 'True'

    def get_last(self):

        if (len(self.command_stack) < 1):
            return ""

        last = self.command_stack.pop()
        self.command_stack.append(last)
        return last

    def get_last_by_instance(self, port):

        if (port not in self.l_commands):
            return ""

        if (len(self.l_commands[port]) < 1):
            return ""

        last = self.l_commands[port].pop()
        self.l_commands[port].append(last)
        return last

    def get_counts_by_instance(self):
        sums = []
        for k, v in self.l_commands.items():
            sums[k] = len(v)
        return json.dumps(sums)


class RedisMonitor(object):
    """
        Python interface class for communicating with the CommandServer
    """

    def __init__(self, redis_ports=[7171]):

        # start the command server
        command_server = CommandServer()
        command_server.start()

        self.setup_server_connection()
        self.shutdown_admin_server = command_server

        if not command_server.is_alive():
            # validate the command server is actually running
            self.socket.send("ping")
            if self.socket.recv() != 'pong':
                raise Exception('admin server port in use')
            else:
                self.shutdown_admin_server = None

        # start the emitters
        list_of_monitors = []
        for r_port in redis_ports:
            monitor_process = RedisEmitterProcess(redis_port=r_port)
            monitor_process.start()
            list_of_monitors.append(monitor_process)

        self.started_emitters = list_of_monitors

    def shutdown(self):

        if self.shutdown_admin_server:
            self.shutdown_admin_server.terminate()

        for mp in self.started_emitters:
            mp.terminate()

        return True

    def setup_server_connection(self):
        context = zmq.Context()

        self.socket = context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5559")

    def poll(self, time_in_seconds=10):

        for x in xrange(1, time_in_seconds):
            self.socket.send("list")
            message = self.socket.recv()
            print message

            time.sleep(1)

    def get_last_command(self):
        self.socket.send("last")
        message = self.socket.recv()
        return message

    def get_last_command_by_instance(self, port):
        self.socket.send("last_by_instance {}".format(port))
        message = self.socket.recv()
        return message

    def get_all_commands(self):
        self.socket.send("all")
        message = self.socket.recv()
        return json.loads(message)

    def reset(self):
        self.socket.send('reset')
        message = self.socket.recv()
        return True if message == 'True' else False


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Start a redis watcher')
    parser.add_argument('-rp', '--redis_port', dest='redis_ports', help='port on which to connect to redis', default=[7171], nargs='+', type=int)

    script_args = parser.parse_args()

    # start a simple poll
    rm = RedisMonitor(redis_ports=script_args.redis_ports)
    rm.poll()