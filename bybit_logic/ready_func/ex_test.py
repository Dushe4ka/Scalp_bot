from bybit_logic.bybit_func import session, position

def ex_test():
    http_session = session.create_session()
    positions = position.get_positions_by_symbol(http_session, "LUNA2USDT")
    print(positions)

ex_test()