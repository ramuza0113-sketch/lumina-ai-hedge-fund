class WordPressPublisher:
    """Stub publisher for open-source repository"""
    def __init__(self, *args, **kwargs):
        pass

    def publish_post(self, *args, **kwargs):
        return {"success": False, "message": "WordPress publishing is not configured in this standalone environment."}
