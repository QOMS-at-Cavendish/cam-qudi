import time
import logging

def log_info(connectors, log_text=''):
    """Log an information message.

    Args:
        log_text (str): Message to log
    """
    logging.info(log_text)
    return 'Completed'

def acquire_confocal_scan(connectors):
    """Acquire confocal x,y map
    
    Blocks until complete.
    """
    confocal = connectors['confocal']()
    if confocal is None:
        raise NameError('Please connect confocal logic module to automation')

    confocal.start_scanning()
    while True:
        time.sleep(1)
        if confocal.module_state() != 'locked':
            break
    
    return 'Completed'