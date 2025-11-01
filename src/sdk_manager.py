import asyncio
import logging
from breez_sdk_spark import (
    BreezSdk,
    connect,
    ConnectRequest,
    default_config,
    Seed
)
from .config import Config

class SDKManager:
    def __init__(self):
        self.config = Config()
        self.sdk: BreezSdk = None

    async def connect(self):
        try:
            seed = Seed.MNEMONIC(mnemonic=self.config.mnemonic, passphrase=None)
            config = default_config(network=self.config.network)
            config.api_key = self.config.api_key

            self.sdk = await connect(
                request=ConnectRequest(
                    config=config,
                    seed=seed,
                    storage_dir=self.config.data_dir
                )
            )
            logging.info("Connected to Breez SDK")
        except Exception as e:
            logging.error(f"Failed to connect: {e}")
            raise

    async def disconnect(self):
        if self.sdk:
            await self.sdk.disconnect()
            logging.info("Disconnected from Breez SDK")

    def get_sdk(self) -> BreezSdk:
        if not self.sdk:
            raise RuntimeError("SDK not connected")
        return self.sdk