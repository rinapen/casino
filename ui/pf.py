import hmac
import hashlib
import secrets

class ProvablyFairParams:
    def __init__(self, client_seed=None, server_seed=None, nonce=0):
        self.client_seed = client_seed or secrets.token_hex(8)
        self.server_seed = server_seed or secrets.token_hex(32)
        self.server_seed_hash = hashlib.sha256(self.server_seed.encode()).hexdigest()
        self.nonce = nonce

    def get_card_index(self, cursor: int) -> int:
        msg = f"{self.client_seed}:{self.nonce}:{cursor}".encode()
        digest = hmac.new(self.server_seed.encode(), msg, hashlib.sha256).digest()
        number = int.from_bytes(digest, 'big') / 2**256
        return int(number * 52)

    def get_card(self, cursor: int):
        suits = ["S", "H", "D", "C"]
        ranks = ["A"] + [str(n) for n in range(2, 11)] + ["J", "Q", "K"]
        idx = self.get_card_index(cursor)
        return ranks[idx % 13] + suits[idx // 13], ranks[idx % 13]

    def get_pf_embed_field(self):
        return (
            f"Hash: `{self.server_seed_hash}`\n"
            f"Seed: `{self.server_seed}`\n"
            f"Client: `{self.client_seed}`\n"
            f"Nonce: `{self.nonce}`"
        )