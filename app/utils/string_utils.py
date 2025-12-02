import os

class StringUtils:
    @classmethod
    def get_file_paths(cls, path: str, recursive: bool = False, file_filter: dict = None) -> list:
        file_paths = []

        def matches_filter(file_path):
            if not os.path.exists(file_path):
                return False

            if file_filter is None:
                return True

            if 'extension' in file_filter:
                if not file_path.lower().endswith(file_filter['extension'].lower()):
                    return False

            if 'after_date' in file_filter:
                if os.path.getmtime(file_path) < file_filter['after_date'].timestamp():
                    return False

            if 'before_date' in file_filter:
                if os.path.getmtime(file_path) > file_filter['before_date'].timestamp():
                    return False

            if 'size' in file_filter:
                if os.path.getsize(file_path) > file_filter['size']:
                    return False

            return True

        recursive = False if os.path.isfile(path) else recursive

        if recursive:
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_filter is not None or matches_filter(file_path):
                        file_paths.append(file_path)
        else:
            if os.path.isdir(path):
                for file in os.listdir(path):
                    full_path = os.path.join(path, file)
                    if os.path.isfile(full_path) and (file_filter is None or matches_filter(full_path)):
                        file_paths.append(full_path)
            elif os.path.isfile(path) and (file_filter is None or matches_filter(path)):
                file_paths.append(path)
        return file_paths
