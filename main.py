import random

from src.models import User, TradingObject, OrderType
from src.connect import connect

if __name__ == '__main__':
    connect()

    user = ~User.find_one(User.name == "test2", fetch_links=True)

    btc = ~TradingObject.find_one(TradingObject.name == "test_object", fetch_links=True)

    # SELL > BUY

    # order2 = user.create_order(btc, 1, 105, OrderType.BUY)
    # order1 = user.create_order(btc, 1, 105, OrderType.SELL)

    # order1.close()
    # order2.close()
