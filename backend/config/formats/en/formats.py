TIME_FORMAT = 'g:i A'
DATETIME_FORMAT = 'N j, Y, g:i A'
SHORT_DATETIME_FORMAT = 'm/d/Y g:i A'
# The first format also drives Django admin's time widget and Now shortcuts.
TIME_INPUT_FORMATS = ['%I:%M:%S %p', '%I:%M %p', '%H:%M:%S', '%H:%M:%S.%f', '%H:%M']
