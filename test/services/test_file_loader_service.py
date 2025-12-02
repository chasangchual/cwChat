from app.services.file_loader_service import FileLoadService, FILE_TYPE


def test_get_ext_by_type():
    file_load_service = FileLoadService()

    # Test valid extensions
    assert file_load_service.get_file_type_by_ext('txt') == FILE_TYPE.TEXT
    assert file_load_service.get_file_type_by_ext('pdf') == FILE_TYPE.PDF
    assert file_load_service.get_file_type_by_ext('doc') == FILE_TYPE.MS_WORD
    assert file_load_service.get_file_type_by_ext('docx') == FILE_TYPE.MS_WORD
    assert file_load_service.get_file_type_by_ext('xls') == FILE_TYPE.MS_EXCEL
    assert file_load_service.get_file_type_by_ext('xlsx') == FILE_TYPE.MS_EXCEL
    assert file_load_service.get_file_type_by_ext('ppt') == FILE_TYPE.MS_POWERPOINT
    assert file_load_service.get_file_type_by_ext('pptx') == FILE_TYPE.MS_POWERPOINT

    # Test invalid extensions
    assert file_load_service.get_file_type_by_ext('invalid') is None
    assert file_load_service.get_file_type_by_ext('') is None

def test_load_zip_file():
    file_load_service = FileLoadService()
    file_load_service.load('/Users/scha/Downloads/OneDrive_2_2025-12-01.zip')
