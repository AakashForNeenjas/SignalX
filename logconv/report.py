
class ConversionReport:
    def __init__(self):
        self.entries = []

    def add_error(self, input_path, message):
        self.entries.append({"input": input_path, "status": "error", "message": message})

    def add_warning(self, input_path, message):
        self.entries.append({"input": input_path, "status": "warning", "message": message})

    def add_success(self, input_path, output_path, warnings=None):
        self.entries.append(
            {
                "input": input_path,
                "output": output_path,
                "status": "success",
                "warnings": warnings or [],
            }
        )
