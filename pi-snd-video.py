import argparse
import socket
import picamera
import time

class Args:
    def __init__(self):
        self.ip = '127.0.0.1'
        self.port = 13367

def parse_args():
    parser = argparse.ArgumentParser(description='Send a video stream from a Pi')
    
    parser.add_argument(
        '--ip',
        help='server\'s IP address',
        default='127.0.0.1')
    parser.add_argument(
        '--port',
        type=int,
        help='server\'s port',
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

def start_client(args):
    sock = socket.socket()
    sock.connect((args.ip, args.port))
    
    conn = sock.makefile('wb')

    try:
        camera = picamera.PiCamera()
        camera.resolution = (640, 480)
        camera.framerate = 24
        camera.start_preview()
        time.sleep(2)
        
        camera.start_recording(conn, format='h264')
        camera.wait_recording(10)
        camera.stop_recording()
    finally:
        conn.close()
        sock.close()

def main():
    args = parse_args()
    print_args(args)
    
    try:
        start_client(args)
    except Exception as exc:
        print('Failed: {0}'.format(exc))

main()
