import os, time, pickle
from fastapi import Header, Depends


class Default:
        
    def global_depends(self):
        ...

    async def allow_access_slide(self, auth_payload, slide_id, manager, plugin, slide=None):
        ...
