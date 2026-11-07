"""SafeFile backup engine (no GUI code).

- core.py       folder scanning, hashing, manifests, retention rules
- stores.py     LocalStore (any folder/drive) and CloudStore (Mini Cloud client)
- minicloud.py  the free, self-hosted Mini Cloud server (standard library only)
- engine.py     BackupEngine: backup, verify, restore, retention
"""
