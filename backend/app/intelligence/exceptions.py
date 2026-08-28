class IntelligenceError(Exception):
    """Base error for project intelligence operations."""


class RepositoryNotReadyError(IntelligenceError):
    def __init__(self, message: str = "Repository is not available for analysis") -> None:
        self.message = message
        super().__init__(message)


class RepositoryEmptyError(IntelligenceError):
    def __init__(self, message: str = "Repository directory is empty") -> None:
        self.message = message
        super().__init__(message)
