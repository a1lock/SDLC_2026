import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-automated-tests-0123456789")
os.environ["BCRYPT_ROUNDS"] = "4"
