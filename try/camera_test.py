from time import sleep
from picamera import PiCamera

options = [
    #'off',
    'auto',
    #'sun',
    #'cloudshade',
    'tungsten',
    'fluorescent',
    'incandescent',
    'flash',
    'horizon'
]

camera = PiCamera()
try:
    #camera.resolution = (1024, 768)
    camera.start_preview()
    # Camera warm-up time
    sleep(2)
    
    for o in options:
        print('Using awb mode {0}'.format(o))
        camera.awb_mode = o
        sleep(4)
        camera.capture('test-' + o + '.jpg')
        sleep(2)
except Exception as exc:
    print(exc)
camera.stop_preview()
