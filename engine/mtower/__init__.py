"""MTower Studio production engine.

Reads a production's pre-production files (config, casting, shot lists), resolves
every ID from the studio library, composes prompts, estimates cost, and — only when
explicitly confirmed — calls AI providers through their APIs.
"""

__version__ = "1.0.0"
