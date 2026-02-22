# Lazy import to avoid hard failures when heavy dependencies (pandas, langchain) are absent.
# The v2.4 nodes package is designed to be lightweight and importable independently.
try:
    from biomni.agent.a1 import A1  # noqa: F401
except ImportError:
    pass
