import hashlib


class ClipService:
    def image_similarity(self, amazon_image_url: str, candidate_image_url: str) -> float:
        if amazon_image_url == candidate_image_url:
            return 0.96

        digest = hashlib.sha256(f"{amazon_image_url}|{candidate_image_url}".encode()).hexdigest()
        bucket = int(digest[:4], 16) / 0xFFFF
        return round(0.58 + bucket * 0.28, 4)


clip_service = ClipService()
