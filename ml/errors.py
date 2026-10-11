class PipelineError(Exception):
    """An actionable, safe-to-display pipeline failure."""

    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
