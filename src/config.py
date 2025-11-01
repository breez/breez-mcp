import os
from dotenv import load_dotenv
from breez_sdk_spark import Network

load_dotenv()

class Config:
    def __init__(self):
        self.api_key = os.getenv("BREEZ_API_KEY")
        self.mnemonic = os.getenv("BREEZ_MNEMONIC")
        self.network = Network.TESTNET if os.getenv("BREEZ_NETWORK", "mainnet").lower() == "testnet" else Network.MAINNET
        self.data_dir = os.getenv("BREEZ_DATA_DIR", "./data")

        if not all([self.api_key, self.mnemonic]):
            raise ValueError("Missing required environment variables: BREEZ_API_KEY, BREEZ_MNEMONIC")