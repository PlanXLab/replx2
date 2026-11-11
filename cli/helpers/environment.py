import os


class EnvironmentManager:
    
    @staticmethod
    def load_env_from_rep():
        current_path = os.getcwd()

        while True:
            min_path = os.path.join(current_path, ".vscode", ".replx")
            if os.path.isfile(min_path):
                with open(min_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            os.environ[key.strip()] = value.strip()
                return
            
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:
                return
            current_path = parent_path
