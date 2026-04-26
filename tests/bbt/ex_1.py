from bybit_logic.bybit_func import session, position, market, calculator, orders

def ex_1():
    http_session = session.create_session()
    max_lev = position.get_max_leverage(http_session, "HIGHUSDT")
    print(max_lev)

if __name__ == "__main__":
    ex_1()