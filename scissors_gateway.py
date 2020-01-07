#
# Scissors gateway code running on the Pi on the Scissors.
#
# author: aleksandar
#

import argparse
import datetime
import logging
import logging.config
import socket
import select
import picamera
import time
import sys
import traceback

#
# Constants.
#
NsInMs = 1000000
LogTraceLevel = 1
MaxMsgSize = 1000

#
# Logger.
#
logging.config.fileConfig(fname='scissors_gateway_log.conf', disable_existing_loggers=True)
logger = logging.getLogger(__name__)

def log_trace(msg):
    logger.log(LogTraceLevel, msg)

#
# Arguments.
#
def parse_args():
    parser = argparse.ArgumentParser(description='Scissors gateway script')
    
    parser.add_argument(
        '--host',
        help='IP address to listen on',
        default='0.0.0.0')
    parser.add_argument(
        '--camport',
        type=int,
        help='TCP port to stream video on',
        default=13367)
    parser.add_argument(
        '--cmdport',
        type=int,
        help='UDP port to receive commands on',
        default=13368)
    parser.add_argument(
        '--statsport',
        type=int,
        help='UDP port to send stats on on',
        default=13369)
    parser.add_argument(
        '--vidwidth',
        type=int,
        help='Width of the video in pixels',
        default=1200)
    parser.add_argument(
        '--vidheight',
        type=int,
        help='Height of the video in pixels',
        default=800)
    parser.add_argument(
        '--vidframerate',
        type=int,
        help='Video framerate',
        default=24)
    parser.add_argument(
        '--statsperiod',
        type=int,
        help='Period (in ms) between sending stats to clients',
        default=200)
    parser.add_argument(
        '--logall',
        action='store_true',
        help='Log everything',
        default=False)

    return parser.parse_args()

def log_args(args):
    logger.info(
        'Using arguments:\n'
        '  host: {0}\n'
        '  camport: {1}\n'
        '  cmdport: {2}\n'
        '  statsport: {3}\n'
        '  vidwidth: {4}\n'
        '  vidheight: {5}\n'
        '  vidframerate: {6}\n'
        '  statsperiod {7}'.format(
            args.host,
            args.camport,
            args.cmdport,
            args.statsport,
            args.vidwidth,
            args.vidheight,
            args.vidframerate,
            args.statsperiod))

#
# Helpers.
#
def addr_to_str(addr):
    return str(addr[0]) + ':' + str(addr[1])

#
# Camera.
#
class GatewayCam:
    def __init__(self, args):
        self.cam = None
        self.sock_listen = None
        self.sock = None
        self.out_file = None
        self.recording = False

        self.__init(args)

    def __init(self, args):
        self.cam = picamera.PiCamera()
        self.cam.resolution = (args.vidwidth, args.vidheight)
        self.cam.framerate = args.vidframerate

        self.sock_listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_listen.bind((args.host, args.camport))
        self.sock_listen.listen(1)
        logger.info("Listening for camera connections on {0}:{1}".format(args.host, args.camport))

    def close(self):
        self.__disconnect()

        if self.cam is not None:
            self.cam.close()
            self.cam = None
        
        if self.sock_listen is not None:
            self.sock_listen.close()
            self.sock_listen = None

    def get_socket(self):
        return self.sock_listen if self.sock is None else None

    def process_socket(self):
        self.sock, cli_addr = self.sock_listen.accept()
        logger.info('Camera client {0} connected'.format(addr_to_str(cli_addr)))
    
        self.out_file = self.sock.makefile('wb')

        self.recording = True
        self.cam.start_recording(self.out_file, format='h264')

    def process_periodic(self):
        if not self.recording:
            return

        try:
            self.cam.wait_recording(0)
        except Exception as e:
            logger.error('Camera error {0}'.format(e))
            self.__disconnect()

    def __disconnect(self):
        logger.info('Disconnecting camera client')
        
        if self.recording:
            self.__stop_cam_recording()
            self.recording = False

        if self.out_file is not None:
            self.out_file.close()
            self.out_file = None

        if self.sock is not None:
            self.sock.close()
            self.sock = None 
            
    def __stop_cam_recording(self):
        try:
            self.cam.stop_recording()
        except:
            pass

#
# Commands.
#
class GatewayCmd:
    def __init__(self, args):
        self.sock = None
        self.__init(args)

    def __init(self, args):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((args.host, args.cmdport))
        logger.info("Waiting for commands on {0}:{1}".format(args.host, args.cmdport))

    def get_socket(self):
        return self.sock

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def process_socket(self):
        msg, addr = self.sock.recvfrom(MaxMsgSize)
        msg = msg.decode('utf8')
        logger.debug("Received cmd message from {0}\n{1}".format(addr_to_str(addr), msg))

#
# Statistics
#
class GatewayStats:
    def __init__(self, args):
        self.sock = None
        self.rcv_list = []

        self.__init(args)

    def __init(self, args):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((args.host, args.statsport))
        logger.info("Waiting for stats on {0}:{1}".format(args.host, args.statsport))
        
        self.last_send_time = time.perf_counter_ns()
        self.period_ms = args.statsperiod * NsInMs

    def get_socket(self):
        return self.sock

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def process_socket(self):
        msg, addr = self.sock.recvfrom(MaxMsgSize)
        msg = msg.decode('utf8')
        logger.debug("Received stats message from {0}\n{1}".format(addr_to_str(addr), msg))

        if msg == 'subscribe':
            if addr not in self.rcv_list:
                self.rcv_list.append(addr)
            logger.info('{0} subscribed for stats'.format(addr_to_str(addr)))
        elif msg == 'unsubscribe':
            if addr in self.rcv_list:
                self.rcv_list.remove(addr)
            else:
                logger.info('Removing unknown client {0}'.format(addr_to_str(addr)))
            logger.info('{0} unsibscribed for stats'.format(addr_to_str(addr)))
        else:
            logger.info('Unknown stats message {0} from {1}'.format(msg, addr_to_str(addr)))

    def process_periodic(self):
        if len(self.rcv_list) == 0:
            log_trace('Skipping stats processing as there are no receivers')
            return

        now = time.perf_counter_ns()

        if now - self.last_send_time < self.period_ms:
            log_trace('Too soon to send stats')
            return

        self.last_send_time = now

        stats = self.__get_stats()
        
        for stats_cli in self.rcv_list:
            self.sock.sendto(stats, stats_cli)

    def __get_stats(self):
        stats = "Stats at {0}".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
        logger.debug('Sending stats:\n{0}'.format(stats))
        return stats.encode('utf-8')

# Gateway / processing loop.
class Gateway:
    # init and cleanup
    def __init__(self, args):
        self.cam = None
        self.cmd = None
        self.stats = None

        self.args = args

        self.exit_requested = False
    
    def __enter__(self):
        self.cam = GatewayCam(self.args)
        self.cmd = GatewayCmd(self.args)
        self.stats = GatewayStats(self.args)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cam is not None:
            self.cam.close()

        if self.cmd is not None:
            self.cmd.close()

        if self.stats is not None:
            self.stats.close()

    # loop
    def execute(self):
        while not self.exit_requested:
            self.__loop_iter()

        logger.info("Exiting the event loop")

    def __loop_iter(self):
        cmd_sock = self.cmd.get_socket()
        stats_sock = self.stats.get_socket()

        listen_sockets = [ cmd_sock, stats_sock ]

        cam_sock = self.cam.get_socket()

        if cam_sock is not None:
            listen_sockets.append(cam_sock)

        ready_list, _, _ = select.select(listen_sockets, [], [], 0.1)
        log_trace('select returned {0}'.format(len(ready_list)))

        for ready in ready_list:
            if ready == cam_sock:
                self.cam.process_socket()
            elif ready == stats_sock:
                self.stats.process_socket()
            elif ready == cmd_sock:
                self.cmd.process_socket()
            else:
                logger.error('Unexpected socket ready')

        self.stats.process_periodic()
        self.cam.process_periodic()

def main():
    args = parse_args()
    log_args(args)

    if args.logall:
        logger.setLevel(1)

    try:
        with Gateway(args) as gateway:
            gateway.execute()
    except KeyboardInterrupt:
        logger.info("Interrupted from keyboard. Exiting...")
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())

main()
