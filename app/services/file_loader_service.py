import logging
import os
import zipfile
import tempfile
from enum import Enum
from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredWordDocumentLoader, \
    UnstructuredExcelLoader, UnstructuredPowerPointLoader
from langchain_core.documents import Document
from typing import List

from app.utils.string_utils import StringUtils


class FILE_TYPE(Enum):
    TEXT = 1
    PDF = 2
    MS_WORD = 3
    MS_EXCEL = 4
    MS_POWERPOINT = 5
    ZIP = 6

class FileLoadService:
    def __init__(self):
        self.default_encoding = 'utf-8'
        self.file_types = {
            FILE_TYPE.TEXT: {"ext": ["txt"]},
            FILE_TYPE.PDF: {"ext": ["pdf"]},
            FILE_TYPE.MS_WORD: {"ext": ["doc", "docx"]},
            FILE_TYPE.MS_EXCEL: {"ext": ["xls", "xlsx"]},
            FILE_TYPE.MS_POWERPOINT: {"ext": ["ppt", "pptx"]},
            FILE_TYPE.ZIP: {"ext": ["zip"]}
        }

        self.ext_types = self._map_to_ext()

    def get_file_type_by_ext(self, ext: str):
        if ext in self.ext_types:
            return self.ext_types[ext]
        return None

    def _map_to_ext(self):
        ext_file_type_map = {}
        for file_type in self.file_types:
            for ext in self.file_types[file_type]['ext']:
                ext_file_type_map[ext] = file_type
                if not ext.startswith('.'):
                    ext_file_type_map[f'.{ext}'] = file_type
        return ext_file_type_map

    def _is_end_with(self, file_type: FILE_TYPE, file_path: str):
        return any(file_path.endswith(ext) for ext in self.file_types[file_type]['ext'])

    def _load_txt(self, file_path: str):
        if self._is_end_with(FILE_TYPE.TEXT, file_path):
            loader = TextLoader(file_path, encoding=self.default_encoding)
            return loader.load()
        else:
            return []

    def _load_pdf(self, file_path):
        if self._is_end_with(FILE_TYPE.TEXT, file_path):
            loader = PyPDFLoader(file_path)
            return loader.load()
        else:
            return []

    def _load_ms_word(self, file_path):
        if self._is_end_with(FILE_TYPE.TEXT, file_path):
            loader = UnstructuredPowerPointLoader(file_path)
            return loader.load()
        else:
            return []

    def _load_ms_excel(self, file_path):
        if self._is_end_with(FILE_TYPE.TEXT, file_path):
            loader = UnstructuredExcelLoader(file_path)
            return loader.load()
        else:
            return []

    def _load_ms_power_point(self, file_path):
        if self._is_end_with(FILE_TYPE.TEXT, file_path):
            loader = UnstructuredPowerPointLoader(file_path)
            return loader.load()
        else:
            return []

    def _load_zip(self, zip_path: str) -> List[Document]:
        if not self._is_end_with(FILE_TYPE.ZIP, zip_path):
            return []

        documents = []
        with tempfile.TemporaryDirectory() as temp_dir:
            logging.info(f'extracting zip file to {temp_dir}')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            documents.extend(self.load_all(temp_dir))
        return documents

    def _load_file(self, file_name):
        root, extension = os.path.splitext(file_name)
        file_type = self.ext_types[extension]
        match file_type:
            case FILE_TYPE.TEXT:
                return self._load_txt(file_name)
            case FILE_TYPE.PDF:
                return self._load_pdf(file_name)
            case FILE_TYPE.MS_WORD:
                return self._load_ms_word(file_name)
            case FILE_TYPE.MS_EXCEL:
                return self._load_ms_excel(file_name)
            case FILE_TYPE.MS_POWERPOINT:
                return self._load_ms_power_point(file_name)
            case FILE_TYPE.ZIP:
                return self._load_zip(file_name)
            case _:
                return []

    def load_all(self, path, recursive=False):
        documents: List[Document] = []

        file_paths = StringUtils.get_file_paths(path, recursive)
        for file_path in file_paths:
            file_path.replace('\\', '/')
            documents.extend(self._load_file(file_path))
        return documents

    def load(self, file_path):
        documents: List[Document] = []

        file_paths = StringUtils.get_file_paths(file_path)
        return self._load_file(file_path)
