from gt7helper import human_readable_size

class LapFile:
    def __init__(self):
        self.name = None
        self.path = None
        self.size = None

    def __str__(self):
        return "%s - %s" % (self.name, human_readable_size(self.size, decimal_places=0))