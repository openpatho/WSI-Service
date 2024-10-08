import os, time, pickle
from fastapi import Header, Depends
from wsi_service.api.v3.integrations.default import Default
import traceback
import inspect

from typing import Optional

class DebugAuth(Default):
    def __init__(self, settings, logger, http_client):
        self.settings = settings
        self.logger = logger
        self.http_client = http_client
        print("Finished initialising the debugging 'pickleAuth' addin")
        
    @staticmethod
    def global_depends(self):
        # This function returns another function that FastAPI can use as a dependency
        async def dependency(authorization: str = Header(None)):
            # You can process the 'authorization' header here if needed
            return authorization
        return Depends(dependency)

    async def allow_access_slide(self, auth_payload, slide_id, manager, plugin, slide=None):
        # Gather data into a dictionary
        try:
            stack = inspect.stack()
            caller = stack[1]  # Caller is the function that called this one (stack[1])
            calling_function = caller.function
            calling_filename = caller.filename
            calling_lineno = caller.lineno
            callString = f"Called by function: {calling_function} in file: {calling_filename} at line: {calling_lineno}"
            data = {
                "auth_payload": repr(auth_payload),
                "requested_page": callString,
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
        except:
            print("this is where the error was")
            traceback.print_exc()
            return True
