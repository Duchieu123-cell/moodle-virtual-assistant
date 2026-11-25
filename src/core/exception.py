class AppException(Exception):
    status_code: int
    
    def __init__(self, message: str = "An error occurred", type: str = "app_exception"):
        self.detail = {
            "type": type,
            "message": message
        }
        super().__init__(message)

class InternalServerError(AppException):
    status_code = 500

class NotFoundError(AppException):
    status_code = 404