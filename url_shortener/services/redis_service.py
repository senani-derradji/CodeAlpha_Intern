import redis

from config.settings import Info


class RedisClient:

    def __init__(self):

        self.expiration_seconds = (
            Info.URL_EXPIRATION_TIME_IN_SECONDS
        )

        self.redis_client = redis.Redis(
            host=Info.REDIS_HOST,
            port=Info.REDIS_PORT,
            username=Info.REDIS_USERNAME,
            password=Info.REDIS_PASSWORD,
            decode_responses=True,
        )

    def add_short_url(
        self,
        short_url: str,
        original_url: str,
        expiration_seconds: int = None
    ):

        expiration = (
            expiration_seconds
            or self.expiration_seconds
        )

        self.redis_client.set(
            short_url,
            original_url,
            ex=expiration
        )

        self.redis_client.set(
            f"clicks:{short_url}",
            0,
            ex=expiration
        )

    def check_short_url(
        self,
        short_url: str
    ):

        return self.redis_client.get(
            short_url
        )

    def delete_short_url(
        self,
        short_url: str
    ):

        self.redis_client.delete(
            short_url
        )

        self.redis_client.delete(
            f"clicks:{short_url}"
        )

    def increment_clicks(
        self,
        short_url: str,
        # ip: str,
        # user_agent: str,
        # browser: str,
        # platform: str
    ):

        self.redis_client.incr(
            f"clicks:{short_url}",
            # f"ip:{ip}"
            # f"user_agent:{user_agent}"
            # f"browser:{browser}"
            # f"platform:{platform}"
        )

    def get_clicks(
        self,
        short_url: str,
        # ip: str,
        # user_agent: str,
        # browser: str,
        # platform: str
    ):

        clicks = self.redis_client.get(
            f"clicks:{short_url}",
            # f"ip:{ip}",
            # f"user_agent:{user_agent}",
            # f"browser:{browser}",
            # f"platform:{platform}"
        )

        return int(clicks) if clicks else 0

    def get_ttl(
        self,
        short_url: str
    ):

        return self.redis_client.ttl(
            short_url
        )

    def ping(self):

        return self.redis_client.ping()