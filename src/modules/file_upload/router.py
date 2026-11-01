from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from src.modules.file_upload.service import FileUploadService

router = APIRouter(
    tags=["File Upload"]
)

@router.post("/ingest/file")
async def file_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mimetype: str = Form(...),
    fileurl: str = Form(...),
    course_name: str = Form("")
):
    # 3. Xử lý background (để API trả về kết quả ngay, không bắt Moodle chờ)
    background_tasks.add_task(FileUploadService.upload_file, file, mimetype, fileurl, course_name)

    return {
        "status" : "success",
        "message": "File received and processing started"
    }