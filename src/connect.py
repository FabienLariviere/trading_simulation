from bunnet import init_bunnet
from pymongo import MongoClient

from src.config import MONGODB
from src.models import User, Wallet, TradingOrder, TradingObject


def connect():
    client = MongoClient(MONGODB)
    init_bunnet(client.trading, document_models=[User, Wallet, TradingObject, TradingOrder])