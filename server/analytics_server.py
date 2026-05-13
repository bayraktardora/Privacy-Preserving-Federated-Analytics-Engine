from typing import Optional

class AnalyticsServer:
    _instance: Optional["AnalyticsServer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            print("AnalyticsServer initialized (Singleton)")