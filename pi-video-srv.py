import argparse
import socket
import picamera
import time

class Args:
    def __init__(self):
        self.ip = '0.0.0.0'
        self.port = 13367

def parse_args():
    parser = argparse.ArgumentParser(description='Send a video stream from a Pi')
    
    parser.add_argument(
        '--ip',
        help='IP address to listen on',
        default='0.0.0.0')
    parser.add_argument(
        '--port',
        type=int,
        help='port to listen on',
        default=13367)
    
    parsed = parser.parse_args()
    
    args = Args()
    args.ip = parsed.ip
    args.port = parsed.port
    
    return args

def print_args(args):
    print('Using arguments:')
    print('  ip: {0}'.format(args.ip))
    print('  port: {0}'.format(args.port))

def start_server(args):
    camera = picamera.PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 24

    srv_sock = socket.socket()
    srv_sock.bind((args.ip, args.port))
    srv_sock.listen(1)
    
    conn_sock, cli_addr = srv_sock.accept()
    print('New connection from {0}'.format(cli_addr))
    
    conn = conn_sock.makefile('wb')
    
    try:
        camera.start_recording(conn, format='h264')
        camera.wait_recording(60)
        camera.stop_recording()
    finally:
        conn.close()
        conn_sock.close()
        srv_sock.close()

def main():
    args = parse_args()
    print_args(args)
    
    try:
        start_server(args)
    except Exception as exc:
        print('Failed: {0}'.format(exc))

main()
