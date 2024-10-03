import os, time, pickle
class Default:
    def __init__(self, settings, logger, http_client):
        self.settings = settings
        self.logger = logger
        self.http_client = http_client

    def global_depends(self):
        ...

    async def allow_access_slide(self, auth_payload, slide_id, manager, plugin, slide=None):
        # Gather data into a dictionary
        data = {
            "auth_payload": repr(auth_payload),
            "slide_id": slide_id,
            "plugin": repr(plugin),
            "slide": repr(slide)
        }

        # Get the `data_dir` from settings and create a subfolder for the auth data
        data_dir = os.path.join(self.settings.data_dir, "auth_logs")
        os.makedirs(data_dir, exist_ok=True)

        # Create a filename using Unix time with hundredths of a second
        timestamp = time.time()  # Get the Unix timestamp
        filename = os.path.join(data_dir, f"auth_data_{timestamp:.3f}.pkl")

        # Pickle the data and save it to the file
        with open(filename, 'wb') as f:
            pickle.dump(data, f)

        # Allow access for now
        return True
