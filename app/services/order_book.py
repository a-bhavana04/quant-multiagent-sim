from collections import deque
from sortedcontainers import SortedDict
import time

class Order:
    def __init__(self, agent_name, side, price, quantity, timestamp=None):
        self.agent_name = agent_name
        self.side = side  # "BUY" or "SELL"
        self.price = price
        self.quantity = quantity
        self.timestamp = timestamp or time.time()

    def __repr__(self):
        return f"{self.side} {self.quantity}@{self.price} by {self.agent_name}"

class OrderBook:
    def __init__(self):
        # SortedDict: price → queue of orders (FIFO at each price level)
        self.bids = SortedDict(lambda x: -x)  # descending price
        self.asks = SortedDict()              # ascending price
        self.trade_history = []

    def place_order(self, order: Order):
        if order.side == "BUY":
            self._match_buy(order)
            if order.quantity > 0:
                self._add_to_book(self.bids, order)
        else:
            self._match_sell(order)
            if order.quantity > 0:
                self._add_to_book(self.asks, order)

    def _add_to_book(self, book, order):
        if order.price not in book:
            book[order.price] = deque()
        book[order.price].append(order)

    def _match_buy(self, buy_order):
        while buy_order.quantity > 0 and self.asks:
            best_ask_price = next(iter(self.asks))
            if buy_order.price < best_ask_price:
                break  # limit price not enough to match best ask

            sell_queue = self.asks[best_ask_price]
            sell_order = sell_queue[0]

            traded_qty = min(buy_order.quantity, sell_order.quantity)
            self._record_trade(buy_order, sell_order, best_ask_price, traded_qty)

            buy_order.quantity -= traded_qty
            sell_order.quantity -= traded_qty

            if sell_order.quantity == 0:
                sell_queue.popleft()
                if not sell_queue:
                    del self.asks[best_ask_price]

    def _match_sell(self, sell_order):
        while sell_order.quantity > 0 and self.bids:
            best_bid_price = next(iter(self.bids))
            if sell_order.price > best_bid_price:
                break  # limit price not enough to match best bid

            buy_queue = self.bids[best_bid_price]
            buy_order = buy_queue[0]

            traded_qty = min(sell_order.quantity, buy_order.quantity)
            self._record_trade(buy_order, sell_order, best_bid_price, traded_qty)

            sell_order.quantity -= traded_qty
            buy_order.quantity -= traded_qty

            if buy_order.quantity == 0:
                buy_queue.popleft()
                if not buy_queue:
                    del self.bids[best_bid_price]

    def _record_trade(self, buy_order, sell_order, price, quantity):
        trade = {
            "buyer": buy_order.agent_name,
            "seller": sell_order.agent_name,
            "price": price,
            "quantity": quantity,
            "timestamp": time.time(),
        }
        self.trade_history.append(trade)
        print(f"[MATCH] {buy_order.agent_name} buys from {sell_order.agent_name} {quantity} @ {price:.2f}")

    def get_top_of_book(self):
        top_bid = next(iter(self.bids)) if self.bids else None
        top_ask = next(iter(self.asks)) if self.asks else None
        return {"bid": top_bid, "ask": top_ask}

    def get_book_depth(self, levels=5):
        depth = {"bids": [], "asks": []}
        for i, (price, orders) in enumerate(self.bids.items()):
            if i >= levels: break
            qty = sum(o.quantity for o in orders)
            depth["bids"].append((price, qty))
        for i, (price, orders) in enumerate(self.asks.items()):
            if i >= levels: break
            qty = sum(o.quantity for o in orders)
            depth["asks"].append((price, qty))
        return depth
