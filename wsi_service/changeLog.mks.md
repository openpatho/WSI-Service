# Impactful Changes 
When migrating from `Frozen` to `Current` slide Server the below changes are worthy of noting

## Custom Classes, not Strings for API calls:
Queries to the `/slides/info` endpoint, and probably others now take a `IdQuery` Class parameter, not just a slide ID String. This should be handled by xopat viewer innately, but might not be by our code:

    from fastapi import Query

    IdQuery = Query(
        ...,
        example="b10648a7-340d-43fc-a2d9-4d91cc86f33f",
        description="""Provide id.""",
    )

## Batch Endpoints names changed
Instead of `/batch/info` it's now `/files/info` etc. The code within the endpoints appears to be the same

The old endpoints still exist, but are flagged for future removal

