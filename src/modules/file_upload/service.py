from src.modules.vector_database.vector_db import VectorDatabaseSingleton
from src.core.exception import InternalServerError
from starlette import status
import shutil
import uuid
import os
import logging

logger = logging.getLogger(__name__)

class FileUploadService():
    vector_db = VectorDatabaseSingleton.get()

    @staticmethod
    async def upload_file(file, mimetype, fileurl, course_name):
        try:
            # Lưu file tạm thời
            temp_dir = "files/file_vector_db"
            os.makedirs(temp_dir, exist_ok=True)
            unique_name = f"{uuid.uuid4()}_{file.filename}"
            temp_file_path = f"{temp_dir}/{unique_name}"
            
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            metadata = {
                "filename": file.filename,
                "mimetype": mimetype,
                "fileurl" : fileurl,
                "course_name": course_name
            }
            
            await FileUploadService.vector_db.add_file_to_index(temp_file_path, metadata)
            
            # Xóa file tạm sau khi đã xử lý xong
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
            logger.info("File uploaded and processed successfully")

        except Exception as e:
            logger.exception("Failed to process file upload")
            raise InternalServerError(
                message=f"Failed to process file upload: {str(e)}",
                type="file_upload_error"
            )