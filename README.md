# Trading Sumilaton API

### QuickStart
```python
from src.models import User, TradingObject, Wallet, TradingOrder, OrderType
from src.exceptions import NotEnoughtObjectsError, NotEnoughtMoneyError, OrderNotExistsError, OrderIntersectionError
from src.connect import connect

def quick_start():
    # connect mongodb
    connect()
    
    # create trading object 
    btc = TradingObject(name="Bitcoin").insert()
    
    # create users
    user_fabien = User(name="Fabien", wallet=Wallet().insert()).insert()
    user_alex = User(name="Alex", wallet=Wallet().insert()).insert()
    
    # give some money and objects to users
    user_fabien.edit_money(10000)
    user_fabien.edit_objects(btc, 10000)
    
    user_alex.edit_money(10000)
    user_alex.edit_objects(btc, 10000)
    
    # create order
    try:
        order = user_alex.create_order(btc, 1, 100, OrderType.SELL)
    except (NotEnoughtObjectsError, NotEnoughtMoneyError, OrderIntersectionError) as err:
        raise err
    
    # use order
    try:
        user_fabien.use_order(order)
    except (NotEnoughtObjectsError, NotEnoughtMoneyError, OrderNotExistsError) as err:
        raise err

```