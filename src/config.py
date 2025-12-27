import os

MODE = os.getenv("MODE", "replay")  # replay | live
DATA_DIR = os.getenv("DATA_DIR", "/data")
SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/snapshots")
REPORT_DIR = os.getenv("REPORT_DIR", "/reports")
