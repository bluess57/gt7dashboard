class LapFile:
    def __init__(self):
        self.name = None
        self.path = None
        self.size = None

    @staticmethod
    def human_readable_size(size, decimal_places=3):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                break
            size /= 1024.0
        return f"{size:.{decimal_places}f} {unit}"

    def __str__(self):
        return "%s - %s" % (
            self.name,
            self.human_readable_size(self.size, decimal_places=0),
        )
