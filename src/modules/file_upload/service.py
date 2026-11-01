from src.modules.vector_database.vector_db import VectorDatabaseSingleton
from fastapi import HTTPException
from starlette import status
import shutil
import uuid
import os

class FileUploadService():
    vector_db = VectorDatabaseSingleton.get()

    @staticmethod
    async def upload_file(file, mimetype, fileurl, course_name):
        try:
            # 1. Lưu file tạm thời
            temp_dir = "file_vector_db"
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

        except Exception as e:
            print(f"Có lỗi khi xử lý file upload: {e}")
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail = f"Có lỗi khi xử lý file upload: {e}"
            )