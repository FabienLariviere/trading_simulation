import enum
import statistics
from typing import Union

from bunnet import Document, Link, BackLink
from pydantic import Field
from datetime import datetime

from src.models import NotEnoughtMoneyError, NotEnoughtObjectsError, OrderNotExistsError
from src.exceptions import OrderIntersectionError


class TradingObject(Document):
    name: str
    orders: list[BackLink["TradingOrder"]] = Field(original_field="trading_object")
    fee: float = 0.1

    def get_avg_price(self, order_type: "OrderType") -> float | None:
        self.fetch_all_links()

        try:
            mean = statistics.mean(
                map(
                    lambda order: order.price,
                    filter(lambda order: order.order_type == order_type and order.status == TradingStatus.ACTIVE, self.orders)
                )
            )
        except statistics.StatisticsError:
            mean = None

        return mean


class TradingStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class OrderType(str, enum.Enum):
    SELL = "SELL"
    BUY = "BUY"

    def __neg__(self):
        return self.SELL if self.BUY else self.BUY


class TradingOrder(Document):
    amount: int = Field(ge=0)
    price: float = Field(gt=0)
    order_type: OrderType
    trading_object: Link[TradingObject]
    creator: Link["User"]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None

    status: TradingStatus = TradingStatus.ACTIVE

    def close(self):
        self.fetch_all_links()

        # возвращаем отданое
        if self.order_type is OrderType.BUY:
            self.creator.edit_money(abs(self.amount * self.price))
        else:
            self.creator.edit_objects(self.trading_object, self.amount)

        # отменяем ордер
        self.status = TradingStatus.CANCELED
        self.save()

    def complete(self, amount: int):
        self.fetch_all_links()

        # отдаем ордер
        if self.order_type is OrderType.BUY:
            self.creator.edit_objects(self.trading_object, amount)
        else:
            self.creator.edit_money(abs(amount * self.price))

        # завершаем ордер
        self.amount -= amount
        if self.amount == 0:
            self.status = TradingStatus.COMPLETED

        self.creator.wallet.save()
        self.save()


class User(Document):
    name: str
    wallet: Link["Wallet"]
    orders: list[BackLink["TradingOrder"]] = Field(original_field="creator")

    def transfer(self, to_user: "User", amount):
        self.fetch_all_links()
        to_user.fetch_link(User.wallet)

        if self.wallet.money < amount:
            raise NotEnoughtMoneyError

        self.edit_money(-amount)
        to_user.edit_money(amount)

    def create_order(self, trading_object: "TradingObject", amount: int, price: float, order_type: OrderType) -> Union["TradingOrder", None]:
        self.fetch_all_links()
        abs_price = abs(amount * price)

        print()

        # ограничение на создание пересекающей цены
        if order_type is OrderType.BUY:
            query = TradingOrder.find_many(TradingOrder.order_type == order_type.SELL, TradingOrder.status == TradingStatus.ACTIVE).sort("-price").limit(1)
        else:
            query = TradingOrder.find_many(TradingOrder.order_type == order_type.BUY, TradingOrder.status == TradingStatus.ACTIVE).sort("+price").limit(1)

        # сравниваем ордера
        if intersection_order := (~query)[0]:
            # цена ордера покупки больше чем максимальная цена продажи
            # цена ордера продажи меньше чем максимальная цена покупки
            if (order_type is OrderType.BUY and intersection_order.price < price) or (order_type is OrderType.SELL and intersection_order.price > price):
                raise OrderIntersectionError

            # если цена у нас совпадает, мы можем выполнить ордер
            if intersection_order.price == price:
                self.use_order(intersection_order, amount)
                return None

        # если с ценой все в проядке дальше создаем новый ордер

        if order_type is OrderType.BUY:
            if self.wallet.money < abs_price:
                raise NotEnoughtMoneyError
            self.edit_money(-abs_price)
        else:
            if self.wallet.get_object(trading_object) < amount:
                raise NotEnoughtObjectsError
            self.edit_objects(trading_object, -amount)

        self.edit_money(-(abs_price * trading_object.fee))

        return TradingOrder(trading_object=trading_object.to_ref(), amount=amount, price=price, creator=self.to_ref(), order_type=order_type).insert()

    def use_order(self, order: "TradingOrder", amount: int = None):
        self.fetch_all_links()
        order.fetch_all_links()

        if order.creator.id == self.id:
            raise ValueError("Нельзя выполнить свой ордер")

        if order.status is not TradingStatus.ACTIVE:
            raise OrderNotExistsError

        if amount is None:
            amount = order.amount

        normalized_price = abs(order.price)

        if order.order_type is OrderType.BUY:
            if self.wallet.get_object(order.trading_object) < amount:
                raise NotEnoughtObjectsError
            self.edit_objects(order.trading_object, -amount)
            self.edit_money(abs(order.price * amount))
        else:
            if self.wallet.money < normalized_price * amount:
                raise NotEnoughtMoneyError
            self.edit_objects(order.trading_object, amount)
            self.edit_money(-abs(order.price * amount))

        order.complete(amount)

        # сохраняем пользователя
        self.wallet.save()

    def edit_money(self, amount: float):
        self.fetch_all_links()

        if 0 > amount > self.wallet.money:
            raise NotEnoughtMoneyError

        self.wallet.money += amount
        self.wallet.save()

        return self.wallet.money

    def edit_objects(self, trading_object: "TradingObject", amount):
        self.fetch_all_links()
        self.wallet.edit_objects(trading_object, amount)
        return self.wallet.objects_wallet


class Wallet(Document):
    money: float = Field(0, ge=0)
    objects_wallet: dict[str, int] = dict()

    user: BackLink[User] = Field(original_field="wallet")

    def edit_objects(self, trading_object: "TradingObject", amount):
        object_id = str(trading_object.id)
        if object_id not in self.objects_wallet.keys():
            self.objects_wallet[object_id] = 0
        self.objects_wallet[object_id] += amount
        self.save()

    def get_object(self, trading_object: "TradingObject") -> int:
        object_id = str(trading_object.id)
        return self.objects_wallet.get(object_id, 0)
