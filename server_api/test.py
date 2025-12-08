from server_api.utils import validate_and_clean_symbol

print(validate_and_clean_symbol("ZEUSUSDT.P"))
print(validate_and_clean_symbol("BTCUSDT"))
print(validate_and_clean_symbol("BTCUSDT.P"))
print(validate_and_clean_symbol("BTCUSDT.PERP"))
print(validate_and_clean_symbol("BTCUSDT.PERP"))