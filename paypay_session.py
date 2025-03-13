from PayPaython_mobile import PayPay
from config import PAYPAY_PHONE, PAYPAY_PASSWORD
from database.db import get_tokens, save_tokens

class PayPaySession:
    def __init__(self):
        self.tokens = get_tokens()
        self.paypay = None
        self.login()
    
    def login(self):
        if "access_token" in self.tokens:
            self.paypay = PayPay(access_token=self.tokens["access_token"])
        elif "device_uuid" in self.tokens:
            self.paypay = PayPay(PAYPAY_PHONE, PAYPAY_PASSWORD, self.tokens["device_uuid"])
        else:
            url = input("PayPay URL?: ")
            self.paypay = PayPay(PAYPAY_PHONE, PAYPAY_PASSWORD)
            self.paypay.login(url)
            save_tokens(self.paypay.access_token, self.paypay.refresh_token, self.paypay.device_uuid)
    
    def send_money(self, amount, receiver_id):
        return self.paypay.send_money(amount=amount, receiver_id=receiver_id)

paypay_session = PayPaySession()