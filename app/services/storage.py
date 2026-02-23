import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO

import boto3
from botocore.client import Config

from app.core.config import settings


class Storage(ABC):
    @abstractmethod
    async def upload(self, key: str, data: BinaryIO) -> str: ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, path_or_key: str) -> None: ...


# MinIO implementation (sync boto3 used via threads for simplicity)
executor = ThreadPoolExecutor(4)


class MinioStorage(Storage):
    def __init__(self):
        self.s3 = boto3.resource(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_root_user,
            aws_secret_access_key=settings.minio_root_password,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.bucket = settings.minio_bucket
        # ensure bucket exists
        try:
            self.s3.create_bucket(Bucket=self.bucket)
        except Exception:
            pass

    async def upload(self, key: str, data: BinaryIO) -> str:
        loop = asyncio.get_running_loop()

        def put():
            self.s3.Bucket(self.bucket).put_object(Key=key, Body=data.read())
            return f"s3://{self.bucket}/{key}"

        return await loop.run_in_executor(executor, put)

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_running_loop()

        def get():
            obj = self.s3.Object(self.bucket, key).get()
            return obj["Body"].read()

        return await loop.run_in_executor(executor, get)

    async def delete(self, path_or_key: str) -> None:
        loop = asyncio.get_running_loop()

        def delete():
            key = path_or_key
            if path_or_key.startswith("s3://"):
                key = path_or_key.split("/", 3)[-1]
            self.s3.Object(self.bucket, key).delete()

        await loop.run_in_executor(executor, delete)


class LocalStorage(Storage):
    def __init__(self, base_path="/data/files"):
        import os

        os.makedirs(base_path, exist_ok=True)
        self.base_path = base_path

    async def upload(self, key: str, data: BinaryIO) -> str:
        path = f"{self.base_path}/{key}"
        with open(path, "wb") as f:
            f.write(data.read())
        return path

    async def download(self, key: str) -> bytes:
        path = f"{self.base_path}/{key}"
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, path_or_key: str) -> None:
        import os

        path = path_or_key
        if not path_or_key.startswith("/"):
            path = f"{self.base_path}/{path_or_key}"
        if os.path.exists(path):
            os.remove(path)


# Factory
def get_storage() -> Storage:
    if settings.storage_backend == "minio":
        return MinioStorage()
    return LocalStorage()
