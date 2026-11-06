class CustomException(Exception):
    status_code: int
    error_code: str
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class InternalServerError(CustomException):
    status_code = 500
    error_code = "INTERNAL_SERVER_ERROR"