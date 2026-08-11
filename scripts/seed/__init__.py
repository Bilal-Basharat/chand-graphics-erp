"""Fill a database with believable data to test the app against.

    python -m scripts.seed --help

Nothing is imported here on purpose. The command line has to be able to
point the app at a different database *before* any app module reads its
settings, and an import in this file would be too early to allow that.
"""
