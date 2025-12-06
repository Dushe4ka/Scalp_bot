from pyngrok import ngrok
from config import NGROK_TOKEN

def get_ngrok_url(port: int = 8000):
    """
    Получаем URL ngrok для сервера
    """
    ngrok.set_auth_token(NGROK_TOKEN)
    public_url = ngrok.connect(port)
    return public_url